"""Uygulama çekirdeği: cihaz, çıkış durumu, emülasyon ve profilleri birleştirir."""
from __future__ import annotations

import colorsys
import logging
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

from . import protocol as P
from . import triggers
from .device import DeviceInfo, DeviceWatcher, DualSenseDevice
from .emulator import Emulator, vigem_available
from .foreground import foreground_exe
from .profiles import Profile, ProfileStore

log = logging.getLogger(__name__)


class ControllerService(QObject):
    device_connected = Signal(str)          # etiket
    device_disconnected = Signal(str)       # neden
    emulation_changed = Signal(str)         # none | x360 | ds4
    profile_changed = Signal(str)           # etkin profil adı
    auto_profile_changed = Signal(str)      # otomatik geçiş bildirimi ("" = geri dönüldü)
    log_message = Signal(str)
    rumble_received = Signal(int, int)
    _disconnected_internal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store = ProfileStore()
        self.profile: Profile = self.store.active.clone()
        self._manual_profile_name = self.profile.name
        self._auto_profile_name: str | None = None
        self.output = P.OutputState()
        self.device: DualSenseDevice | None = None
        self._dirty = True
        self._lock = threading.Lock()
        self._rumble_game = (0, 0)
        self._rumble_test = (0, 0)
        self._rumble_test_until = 0.0
        self._game_lightbar: tuple | None = None
        self._rainbow_phase = 0.0
        self._first_write_pending = True
        self._last_input_time = 0.0
        self.emulator = Emulator(on_rumble=self._on_game_rumble, on_lightbar=self._on_game_lightbar)
        self.emulator.profile = self.profile
        self.watcher = DeviceWatcher(self._on_device_found)
        self._connect_lock = threading.Lock()
        self._pending_info: DeviceInfo | None = None

        self._disconnected_internal.connect(self._handle_disconnect)

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(16)
        self._flush_timer.timeout.connect(self._tick)
        self._flush_timer.start()

        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(1000)
        self._auto_timer.timeout.connect(self._auto_profile_tick)
        self._auto_timer.start()

        self._connect_timer = QTimer(self)
        self._connect_timer.setInterval(100)
        self._connect_timer.timeout.connect(self._maybe_connect)
        self._connect_timer.start()

        self.apply_profile(self.profile, save_active=False)
        self.watcher.start()

    # ------------------------------------------------------------------ cihaz
    def _on_device_found(self, info: DeviceInfo):
        # watcher iş parçacığından gelir; bağlantıyı Qt iş parçacığına ertele
        if self.device is not None and self.device.connected:
            return
        self._pending_info = info

    def _maybe_connect(self):
        info = self._pending_info
        if info is None or (self.device is not None and self.device.connected):
            return
        self._pending_info = None
        self.watcher.pause()
        dev = DualSenseDevice(info, on_input=self._on_input, on_disconnect=self._on_disconnect)
        try:
            dev.open()
        except Exception as e:  # noqa: BLE001
            self.log_message.emit(f"Kol açılamadı: {e}")
            self.watcher.resume()
            return
        self.device = dev
        self._first_write_pending = True
        self._dirty = True
        fw = dev.firmware.get("update_version")
        fw_txt = f" FW 0x{fw:04X}" if fw else ""
        self.log_message.emit(f"Bağlandı: {info.label}{fw_txt}")
        self.device_connected.emit(info.label)
        if self.store.settings.auto_emulation and self.profile.emulation != "none":
            self.start_emulation(self.profile.emulation)

    def _on_disconnect(self, err):
        reason = str(err) if err else "bağlantı kapandı"
        self._disconnected_internal.emit(reason)

    def _handle_disconnect(self, reason: str):
        if self.device is not None:
            self.device.close()
            self.device = None
        self.stop_emulation()
        self.log_message.emit(f"Bağlantı koptu: {reason}")
        self.device_disconnected.emit(reason)
        self.watcher.resume()

    def disconnect_device(self):
        if self.device is not None:
            self._handle_disconnect("kullanıcı tarafından kapatıldı")

    def _on_input(self, s: P.InputState):
        self._last_input_time = time.monotonic()
        # Emulator.feed() profildeki (deadzone, ters çevirme, çubuk değiştirme,
        # tetik eşiği...) alanları okur; bunlar UI iş parçacığından
        # set_profile_attr() ile aynı kilit altında değiştirilir, böylece
        # yarım güncellenmiş bir profil okunmaz.
        with self._lock:
            self.emulator.feed(s)

    def set_profile_attr(self, key: str, value) -> None:
        """Profildeki tek bir alanı UI iş parçacığından thread-safe değiştirir.

        HID okuma iş parçacığındaki _on_input()/Emulator.feed() ile aynı kilidi
        kullanır, böylece yarım güncellenmiş bir profil okunmaz.
        """
        with self._lock:
            setattr(self.profile, key, value)

    @property
    def last_state(self) -> P.InputState | None:
        return self.device.last_state if self.device else None

    @property
    def connected(self) -> bool:
        return self.device is not None and self.device.connected

    # -------------------------------------------------------------- emülasyon
    def start_emulation(self, kind: str) -> bool:
        if kind == "none":
            self.stop_emulation()
            return True
        ok, err = vigem_available()
        if not ok:
            self.log_message.emit(f"ViGEmBus bulunamadı: {err}")
            return False
        try:
            self.emulator.profile = self.profile
            self.emulator.start(kind)
        except Exception as e:  # noqa: BLE001
            self.log_message.emit(f"Sanal kol başlatılamadı: {e}")
            return False
        self.emulation_changed.emit(kind)
        self.log_message.emit("Sanal kol aktif: " + ("Xbox 360" if kind == "x360" else "DualShock 4"))
        return True

    def stop_emulation(self):
        if self.emulator.active:
            self.emulator.stop()
            self._rumble_game = (0, 0)
            self._game_lightbar = None
            self._dirty = True
            self.emulation_changed.emit("none")

    def _on_game_rumble(self, large: int, small: int):
        self._rumble_game = (large, small)
        self.rumble_received.emit(large, small)
        # düşük gecikme: doğrudan yaz
        self._push(force=True)

    def _on_game_lightbar(self, r: int, g: int, b: int):
        self._game_lightbar = (r, g, b)
        self._dirty = True

    # ------------------------------------------------------------------ profil
    def update_outputs(self):
        """Profil alanlarından çıkış durumunu yeniden hesaplar (sinyal yaymaz)."""
        p = self.profile
        self.emulator.profile = p
        self.output.right_trigger = triggers.build_effect(p.right_trigger.mode, p.right_trigger.params)
        self.output.left_trigger = triggers.build_effect(p.left_trigger.mode, p.left_trigger.params)
        self.output.led_brightness = p.lightbar_brightness
        self.output.player_leds = p.player_leds
        self.output.player_led_fade = p.player_led_fade
        self.output.mic_led = p.mic_led
        self.output.mic_mute = p.mic_mute
        self._dirty = True

    def apply_profile(self, p: Profile, save_active: bool = True, from_auto: bool = False):
        self.profile = p
        self.update_outputs()
        if not from_auto:
            self._manual_profile_name = p.name
            self._auto_profile_name = None
            if save_active:
                self.store.settings.active_profile = p.name
                self.store.save_settings()
        if self.connected:
            want = p.emulation if self.store.settings.auto_emulation else self.emulator.kind
            if want != self.emulator.kind:
                self.start_emulation(want)
        self.profile_changed.emit(p.name)

    def refresh_from_profile(self):
        """UI profil nesnesini yerinde değiştirdiğinde çağrılır."""
        self.apply_profile(self.profile, save_active=False)

    def set_trigger(self, side: str, mode: str, params: dict):
        tc = self.profile.left_trigger if side == "left" else self.profile.right_trigger
        tc.mode = mode
        tc.params = dict(params)
        eff = triggers.build_effect(mode, params)
        if side == "left":
            self.output.left_trigger = eff
        else:
            self.output.right_trigger = eff
        self._dirty = True

    def _auto_profile_tick(self):
        if not self.store.settings.auto_switch:
            return
        exe = foreground_exe()
        match = self.store.find_for_exe(exe)
        if match is not None:
            if match.name != self.profile.name:
                self._auto_profile_name = match.name
                self.apply_profile(match.clone(), from_auto=True)
                self.auto_profile_changed.emit(match.name)
                self.log_message.emit(f"Otomatik profil: {match.name} ({exe})")
        elif self._auto_profile_name is not None:
            base = self.store.get(self._manual_profile_name)
            self._auto_profile_name = None
            if base is not None:
                self.apply_profile(base.clone(), save_active=False)
                self.auto_profile_changed.emit("")
                self.log_message.emit(f"Profil geri alındı: {base.name}")

    # -------------------------------------------------------------- titreşim
    def test_rumble(self, left: int, right: int, duration_ms: int = 600):
        self._rumble_test = (left, right)
        self._rumble_test_until = time.monotonic() + duration_ms / 1000.0
        self._push(force=True)

    def stop_rumble(self):
        self._rumble_test = (0, 0)
        self._rumble_test_until = 0.0
        self._push(force=True)

    # ------------------------------------------------------------------ çıkış
    def _compute_lightbar(self) -> tuple[int, int, int]:
        p = self.profile
        mode = p.lightbar_mode
        if mode == "off":
            return (0, 0, 0)
        if mode == "battery":
            st = self.last_state
            pct = st.battery_percent if st else 50
            if st and st.charging:
                return (255, 200, 0)
            if pct > 60:
                return (0, 220, 60)
            if pct > 30:
                return (255, 170, 0)
            return (255, 30, 30)
        if mode == "rainbow":
            speed = max(1, min(100, p.rainbow_speed)) / 100.0
            self._rainbow_phase = (self._rainbow_phase + 0.004 * speed * 3) % 1.0
            r, g, b = colorsys.hsv_to_rgb(self._rainbow_phase, 1.0, 1.0)
            return (int(r * 255), int(g * 255), int(b * 255))
        if mode == "game" and self._game_lightbar is not None:
            return self._game_lightbar
        c = p.lightbar_color
        return (int(c[0]), int(c[1]), int(c[2]))

    def _tick(self):
        if not self.connected:
            return
        p = self.profile
        if p.lightbar_mode == "rainbow":
            self._dirty = True
        elif p.lightbar_mode == "battery":
            lb = self._compute_lightbar()
            if lb != self.output.lightbar:
                self._dirty = True
        if self._rumble_test_until and time.monotonic() > self._rumble_test_until:
            self._rumble_test = (0, 0)
            self._rumble_test_until = 0.0
            self._dirty = True
        if self._dirty:
            self._push()

    def _push(self, force: bool = False):
        dev = self.device
        if dev is None or not dev.connected:
            return
        with self._lock:
            p = self.profile
            self.output.lightbar = self._compute_lightbar()
            gl, gr = self._rumble_game
            if p.rumble_passthrough and self.emulator.active:
                scale = max(0, min(200, p.rumble_scale)) / 100.0
                gl = int(min(255, gl * scale))
                gr = int(min(255, gr * scale))
                if p.rumble_min:
                    gl = max(gl, p.rumble_min) if gl > 0 else 0
                    gr = max(gr, p.rumble_min) if gr > 0 else 0
            else:
                gl = gr = 0
            tl, tr = self._rumble_test
            self.output.motor_left = max(gl, tl)
            self.output.motor_right = max(gr, tr)
            if self._first_write_pending:
                # varsayılan mavi ışığı kapat ki renk komutları hemen etkili olsun
                self.output.lightbar_setup = P.LIGHTBAR_SETUP_LIGHT_OUT
            else:
                self.output.lightbar_setup = 0
            ok = dev.write_output(self.output)
            if ok and self._first_write_pending:
                self._first_write_pending = False
                # ikinci bir yazımla normal duruma geç
                self.output.lightbar_setup = 0
                dev.write_output(self.output)
            self._dirty = not ok

    # ------------------------------------------------------------------ kapanış
    def shutdown(self):
        self._flush_timer.stop()
        self._auto_timer.stop()
        self._connect_timer.stop()
        self.watcher.stop()
        self.stop_emulation()
        if self.device is not None:
            try:
                # Kolu nötr duruma getir: tetikler kapalı, titreşim yok, ışık söndür
                self.output.left_trigger = triggers.off()
                self.output.right_trigger = triggers.off()
                self.output.motor_left = self.output.motor_right = 0
                self.device.write_output(self.output)
            except Exception:  # noqa: BLE001
                pass
            self.device.close()
            self.device = None
