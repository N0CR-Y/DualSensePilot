"""ViGEmBus üzerinden sanal Xbox 360 / DualShock 4 kolu emülasyonu."""
from __future__ import annotations

import logging
import threading
from typing import Callable

from . import protocol as P
from .profiles import Profile

log = logging.getLogger(__name__)

_vg = None
_vg_error: str | None = None


def vgamepad_module():
    """vgamepad'i tembel yükler (import anında ViGEmBus'a bağlanır)."""
    global _vg, _vg_error
    if _vg is None and _vg_error is None:
        try:
            import vgamepad  # noqa: WPS433
            _vg = vgamepad
        except Exception as e:  # noqa: BLE001
            _vg_error = str(e)
            log.warning("vgamepad yüklenemedi: %s", e)
    return _vg


def vigem_available() -> tuple[bool, str]:
    vg = vgamepad_module()
    if vg is None:
        return False, _vg_error or "bilinmeyen hata"
    return True, ""


def _apply_deadzone(x: int, y: int, dz_percent: int) -> tuple[float, float]:
    """0-255 eksenleri -1..1 aralığına çevirir, dairesel ölü bölge uygular."""
    fx = (x - 128) / 127.0
    fy = (y - 128) / 127.0
    fx = max(-1.0, min(1.0, fx))
    fy = max(-1.0, min(1.0, fy))
    dz = max(0, min(90, dz_percent)) / 100.0
    mag = (fx * fx + fy * fy) ** 0.5
    if mag < dz:
        return 0.0, 0.0
    if dz > 0 and mag > 0:
        scale = (mag - dz) / (1.0 - dz) / mag
        fx *= scale
        fy *= scale
    return max(-1.0, min(1.0, fx)), max(-1.0, min(1.0, fy))


class Emulator:
    """Tek sanal kol; DualSense girişini eşler, oyundan gelen titreşimi geri verir."""

    def __init__(self, on_rumble: Callable[[int, int], None], on_lightbar: Callable[[int, int, int], None] | None = None):
        self._on_rumble = on_rumble
        self._on_lightbar = on_lightbar
        self._pad = None
        self.kind: str = "none"
        self._lock = threading.Lock()
        self.profile: Profile = Profile()
        self.last_rumble = (0, 0)
        self.updates = 0
        self.errors = 0

    @property
    def active(self) -> bool:
        return self._pad is not None

    def start(self, kind: str) -> bool:
        vg = vgamepad_module()
        if vg is None:
            raise RuntimeError(f"ViGEmBus istemcisi yüklenemedi: {_vg_error}")
        self.stop()
        with self._lock:
            if kind == "x360":
                pad = vg.VX360Gamepad()

                def cb(client, target, large_motor, small_motor, led_number, user_data):
                    self._rumble(large_motor, small_motor)
                pad.register_notification(callback_function=cb)
            elif kind == "ds4":
                pad = vg.VDS4Gamepad()

                def cb(client, target, large_motor, small_motor, lightbar_color, user_data):
                    self._rumble(large_motor, small_motor)
                    if self._on_lightbar is not None:
                        try:
                            self._on_lightbar(lightbar_color.red, lightbar_color.green, lightbar_color.blue)
                        except Exception:  # noqa: BLE001
                            pass
                pad.register_notification(callback_function=cb)
            else:
                return False
            self._pad = pad
            self.kind = kind
            # XInput yeni gelen kol için ilk DEĞİŞEN rapora kadar çöp değer gösterir;
            # ViGEm değişmeyen raporu iletmediği için küçük bir dürtme gönderip sıfırlıyoruz.
            try:
                if kind == "x360":
                    pad.report.sThumbLX = 1
                else:
                    pad.report.bThumbLX = 129
                pad.update()
                pad.reset()
                pad.update()
            except Exception:  # noqa: BLE001
                pass
            log.info("sanal kol başlatıldı: %s", kind)
            return True

    def stop(self):
        with self._lock:
            if self._pad is not None:
                try:
                    self._pad.reset()
                    self._pad.update()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    self._pad.unregister_notification()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    del self._pad
                except Exception:  # noqa: BLE001
                    pass
                self._pad = None
                self.kind = "none"
                log.info("sanal kol durduruldu")

    def _rumble(self, large: int, small: int):
        self.last_rumble = (int(large), int(small))
        try:
            self._on_rumble(int(large), int(small))
        except Exception:  # noqa: BLE001
            log.exception("rumble işleyici hatası")

    # -- giriş eşleme ----------------------------------------------------
    def feed(self, s: P.InputState):
        pad = self._pad
        if pad is None:
            return
        prof = self.profile
        vg = _vg
        lx, ly, rx, ry = s.lx, s.ly, s.rx, s.ry
        if prof.swap_sticks:
            lx, ly, rx, ry = rx, ry, lx, ly
        flx, fly = _apply_deadzone(lx, ly, prof.stick_deadzone)
        frx, fry = _apply_deadzone(rx, ry, prof.stick_deadzone)
        if prof.invert_left_y:
            fly = -fly
        if prof.invert_right_y:
            fry = -fry
        thr = prof.trigger_threshold
        l2 = s.l2 if s.l2 >= thr else 0
        r2 = s.r2 if s.r2 >= thr else 0
        try:
            with self._lock:
                if self._pad is None:
                    return
                if self.kind == "x360":
                    B = vg.XUSB_BUTTON
                    mask = 0
                    if s.dpad_up: mask |= B.XUSB_GAMEPAD_DPAD_UP
                    if s.dpad_down: mask |= B.XUSB_GAMEPAD_DPAD_DOWN
                    if s.dpad_left: mask |= B.XUSB_GAMEPAD_DPAD_LEFT
                    if s.dpad_right: mask |= B.XUSB_GAMEPAD_DPAD_RIGHT
                    if s.options: mask |= B.XUSB_GAMEPAD_START
                    if s.create or (prof.touchpad_as_back and s.touch_btn): mask |= B.XUSB_GAMEPAD_BACK
                    if s.l3: mask |= B.XUSB_GAMEPAD_LEFT_THUMB
                    if s.r3: mask |= B.XUSB_GAMEPAD_RIGHT_THUMB
                    if s.l1: mask |= B.XUSB_GAMEPAD_LEFT_SHOULDER
                    if s.r1: mask |= B.XUSB_GAMEPAD_RIGHT_SHOULDER
                    if s.ps: mask |= B.XUSB_GAMEPAD_GUIDE
                    if s.cross: mask |= B.XUSB_GAMEPAD_A
                    if s.circle: mask |= B.XUSB_GAMEPAD_B
                    if s.square: mask |= B.XUSB_GAMEPAD_X
                    if s.triangle: mask |= B.XUSB_GAMEPAD_Y
                    rep = pad.report
                    rep.wButtons = int(mask)
                    rep.bLeftTrigger = l2
                    rep.bRightTrigger = r2
                    rep.sThumbLX = int(flx * 32767)
                    rep.sThumbLY = int(-fly * 32767)
                    rep.sThumbRX = int(frx * 32767)
                    rep.sThumbRY = int(-fry * 32767)
                    pad.update()
                else:
                    B = vg.DS4_BUTTONS
                    mask = 0
                    if s.square: mask |= B.DS4_BUTTON_SQUARE
                    if s.cross: mask |= B.DS4_BUTTON_CROSS
                    if s.circle: mask |= B.DS4_BUTTON_CIRCLE
                    if s.triangle: mask |= B.DS4_BUTTON_TRIANGLE
                    if s.l1: mask |= B.DS4_BUTTON_SHOULDER_LEFT
                    if s.r1: mask |= B.DS4_BUTTON_SHOULDER_RIGHT
                    if l2 > 0 or s.l2_btn: mask |= B.DS4_BUTTON_TRIGGER_LEFT
                    if r2 > 0 or s.r2_btn: mask |= B.DS4_BUTTON_TRIGGER_RIGHT
                    if s.create: mask |= B.DS4_BUTTON_SHARE
                    if s.options: mask |= B.DS4_BUTTON_OPTIONS
                    if s.l3: mask |= B.DS4_BUTTON_THUMB_LEFT
                    if s.r3: mask |= B.DS4_BUTTON_THUMB_RIGHT
                    dpad = s.dpad_raw if s.dpad_raw <= 8 else 8
                    special = 0
                    if s.ps: special |= vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS
                    if s.touch_btn: special |= vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD
                    rep = pad.report
                    rep.wButtons = (int(mask) & ~0xF) | dpad
                    rep.bSpecial = int(special)
                    rep.bTriggerL = l2
                    rep.bTriggerR = r2
                    rep.bThumbLX = int(128 + flx * 127)
                    rep.bThumbLY = int(128 + fly * 127)
                    rep.bThumbRX = int(128 + frx * 127)
                    rep.bThumbRY = int(128 + fry * 127)
                    pad.update()
                self.updates += 1
        except Exception as e:  # noqa: BLE001
            self.errors += 1
            if self.errors <= 3:
                log.warning("sanal kol güncellenemedi: %s", e)
