"""DualSense HID cihaz katmanı: bulma, açma, okuma iş parçacığı, yazma, yeniden bağlanma."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

import hid

from . import protocol as P

log = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    path: bytes
    serial: str
    product: str
    pid: int
    is_bluetooth: bool
    interface_number: int = -1

    @property
    def label(self) -> str:
        return f"{self.product or 'DualSense'} ({'Bluetooth' if self.is_bluetooth else 'USB'})"

    @property
    def instance_path(self) -> str:
        """HidHide için Windows cihaz örnek yolunu üretir."""
        p = self.path.decode("utf-8", "ignore")
        p = p.replace("\\\\?\\", "").replace("\\\\.\\", "")
        marker = p.rfind("#{")
        if marker == -1:
            log.warning("cihaz yolunda '#{' işaretçisi bulunamadı, HidHide yolu hatalı olabilir: %r", p)
            p = p[:-1] if p else p
        else:
            p = p[:marker]
        return p.replace("#", "\\").upper()


def enumerate_devices() -> list[DeviceInfo]:
    out = []
    seen = set()
    for d in hid.enumerate(P.SONY_VID, 0):
        if d.get("product_id") not in P.SUPPORTED_PIDS:
            continue
        path = d["path"]
        if path in seen:
            continue
        # Yalnızca oyun kolu koleksiyonu (usage page 1, usage 5) ya da BT HID yolu
        up, us = d.get("usage_page", 0), d.get("usage", 0)
        if up not in (0, 1) and up < 0xFF00:
            continue
        if up == 1 and us not in (0, 4, 5):
            continue
        seen.add(path)
        pstr = path.decode("utf-8", "ignore").lower()
        is_bt = ("{00001124" in pstr) or (d.get("bus_type") == 2) or ("bthenum" in pstr)
        out.append(DeviceInfo(
            path=path,
            serial=d.get("serial_number") or "",
            product=d.get("product_string") or "DualSense Wireless Controller",
            pid=d.get("product_id", 0),
            is_bluetooth=bool(is_bt),
            interface_number=d.get("interface_number", -1),
        ))
    return out


class DualSenseDevice:
    """Tek bir DualSense bağlantısı. Okuma iş parçacığı çalıştırır."""

    def __init__(self, info: DeviceInfo,
                 on_input: Callable[[P.InputState], None],
                 on_disconnect: Callable[[Exception | None], None]):
        self.info = info
        self._on_input = on_input
        self._on_disconnect = on_disconnect
        self._dev: hid.device | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._write_lock = threading.Lock()
        self._bt_seq = 0
        self.firmware: dict = {}
        self.mac: str | None = None
        self.is_bluetooth = info.is_bluetooth
        self.report_rate = 0.0
        self._rate_count = 0
        self._rate_t0 = time.monotonic()
        self.last_state: P.InputState | None = None
        self.connected = False

    # -- yaşam döngüsü ---------------------------------------------------
    def open(self):
        dev = hid.device()
        dev.open_path(self.info.path)
        dev.set_nonblocking(0)
        self._dev = dev
        try:
            fw = dev.get_feature_report(P.FEATURE_FIRMWARE_INFO, 64)
            if fw:
                self.firmware = P.parse_firmware_info(bytes(fw))
        except Exception as e:  # noqa: BLE001
            log.debug("firmware bilgisi okunamadı: %s", e)
        try:
            # BT'de 0x05 kalibrasyon raporunu okumak kolu tam (0x31) rapor moduna geçirir
            dev.get_feature_report(P.FEATURE_CALIBRATION, 41)
        except Exception as e:  # noqa: BLE001
            log.debug("kalibrasyon raporu okunamadı: %s", e)
        try:
            pi = dev.get_feature_report(P.FEATURE_PAIRING_INFO, 20)
            if pi:
                self.mac = P.parse_mac_from_pairing_info(bytes(pi))
        except Exception as e:  # noqa: BLE001
            log.debug("eşleşme bilgisi okunamadı: %s", e)
        self.connected = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._read_loop, name="ds-read", daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        self.connected = False
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)
            if thread.is_alive():
                # Okuma iş parçacığı hâlâ dev.read() içinde olabilir (örn. BT
                # bağlantısı takıldıysa). Aynı HID handle'ını burada kapatmak,
                # başka bir iş parçacığı ondan okuma yaparken hidapi'nin Windows
                # tarafında tanımsız davranışa (çökme) yol açabilir. Bu yüzden
                # gerçek kapatmayı, okuma iş parçacığı kendiliğinden bitene kadar
                # arka planda erteliyoruz; bu nesneyi ise hemen "kapalı" gösteriyoruz
                # (self._dev = None), böylece write_output() ve yeni bir açma denemesi
                # güvenle ilerleyebilir.
                log.warning("okuma iş parçacığı zamanında bitmedi; cihaz kapatma geri plana erteleniyor")
                dev = self._dev
                self._dev = None
                self._thread = None

                def _deferred_close(t=thread, d=dev):
                    t.join()
                    if d is not None:
                        with self._write_lock:
                            try:
                                d.close()
                            except Exception:  # noqa: BLE001
                                pass

                threading.Thread(target=_deferred_close, daemon=True, name="ds-close-defer").start()
                return
        with self._write_lock:
            if self._dev is not None:
                try:
                    self._dev.close()
                except Exception:  # noqa: BLE001
                    pass
                self._dev = None
        self._thread = None

    @property
    def use_vibration_v2(self) -> bool:
        return self.firmware.get("update_version", 0) >= 0x0224

    # -- okuma -----------------------------------------------------------
    def _read_loop(self):
        err: Exception | None = None
        empty_reads = 0
        while not self._stop.is_set():
            try:
                buf = self._dev.read(128, timeout_ms=200)
            except Exception as e:  # noqa: BLE001
                err = e
                break
            if not buf:
                empty_reads += 1
                # BT'de uzun süre veri gelmezse bağlantı kopmuş say (~6 sn)
                if empty_reads > 30:
                    err = TimeoutError("Koldan veri gelmiyor")
                    break
                continue
            empty_reads = 0
            if buf[0] == P.REPORT_IN_USB and len(buf) <= 10:
                # BT basit mod; tam moda geçmek için 0x05'i yeniden iste
                try:
                    self._dev.get_feature_report(P.FEATURE_CALIBRATION, 41)
                except Exception:  # noqa: BLE001
                    pass
                continue
            if buf[0] == P.REPORT_IN_BT:
                self.is_bluetooth = True
                if not P.verify_bt_input_crc(bytes(buf)):
                    # Bozuk/kesilmiş Bluetooth raporu: hatalı tuş/pil durumuna
                    # dönüşmeden at.
                    continue
            elif buf[0] == P.REPORT_IN_USB:
                self.is_bluetooth = False
            state = P.parse_input_report(bytes(buf))
            if state is None:
                continue
            self.last_state = state
            self._rate_count += 1
            now = time.monotonic()
            if now - self._rate_t0 >= 1.0:
                self.report_rate = self._rate_count / (now - self._rate_t0)
                self._rate_count = 0
                self._rate_t0 = now
            try:
                self._on_input(state)
            except Exception:  # noqa: BLE001
                log.exception("giriş işleyici hatası")
        self.connected = False
        if not self._stop.is_set():
            try:
                self._on_disconnect(err)
            except Exception:  # noqa: BLE001
                log.exception("disconnect işleyici hatası")

    # -- yazma -----------------------------------------------------------
    def write_output(self, state: P.OutputState) -> bool:
        with self._write_lock:
            if self._dev is None:
                return False
            state.use_vibration_v2 = self.use_vibration_v2
            if self.is_bluetooth:
                rep = P.build_output_report_bt(state, self._bt_seq)
                self._bt_seq = (self._bt_seq + 1) & 0x0F
            else:
                rep = P.build_output_report_usb(state)
            try:
                n = self._dev.write(rep)
                return n > 0
            except Exception as e:  # noqa: BLE001
                log.warning("çıkış raporu yazılamadı: %s", e)
                return False


class DeviceWatcher:
    """Kol bağlanana kadar belirli aralıklarla cihaz arar."""

    def __init__(self, on_found: Callable[[DeviceInfo], None], interval: float = 1.0):
        self._on_found = on_found
        self._interval = interval
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ds-watch", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def pause(self):
        self._pause.set()

    def resume(self):
        self._pause.clear()

    def _loop(self):
        while not self._stop.is_set():
            if not self._pause.is_set():
                try:
                    devs = enumerate_devices()
                except Exception as e:  # noqa: BLE001
                    log.debug("enumerate hatası: %s", e)
                    devs = []
                if devs:
                    # USB'yi BT'ye tercih et
                    devs.sort(key=lambda d: d.is_bluetooth)
                    try:
                        self._on_found(devs[0])
                    except Exception:  # noqa: BLE001
                        log.exception("on_found hatası")
            self._stop.wait(self._interval)
