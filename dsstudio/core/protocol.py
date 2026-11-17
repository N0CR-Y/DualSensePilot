"""DualSense HID protokolü: giriş raporu çözümleme ve çıkış raporu oluşturma.

Kaynaklar: Linux hid-playstation sürücüsü, pydualsense, DS4Windows, nondebug/dualsense.
USB:  giriş 0x01 (64 bayt), çıkış 0x02 (48 bayt)
BT:   giriş 0x31 (78 bayt, CRC32), çıkış 0x31 (78 bayt, CRC32)
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

SONY_VID = 0x054C
DUALSENSE_PID = 0x0CE6
DUALSENSE_EDGE_PID = 0x0DF2
SUPPORTED_PIDS = (DUALSENSE_PID, DUALSENSE_EDGE_PID)

# Rapor kimlikleri
REPORT_IN_USB = 0x01
REPORT_IN_BT = 0x31
REPORT_OUT_USB = 0x02
REPORT_OUT_BT = 0x31
FEATURE_CALIBRATION = 0x05
FEATURE_PAIRING_INFO = 0x09
FEATURE_FIRMWARE_INFO = 0x20

OUT_REPORT_LEN_USB = 48
OUT_REPORT_LEN_BT = 78
IN_REPORT_LEN_USB = 64
IN_REPORT_LEN_BT = 78
BT_CRC_SEED_OUTPUT = 0xA2
BT_CRC_SEED_INPUT = 0xA1

# valid_flag0 bitleri
FLAG0_COMPAT_VIBRATION = 0x01
FLAG0_HAPTICS_SELECT = 0x02
FLAG0_RIGHT_TRIGGER = 0x04
FLAG0_LEFT_TRIGGER = 0x08
FLAG0_HEADPHONE_VOLUME = 0x10
FLAG0_SPEAKER_VOLUME = 0x20
FLAG0_MIC_VOLUME = 0x40
FLAG0_AUDIO_CONTROL = 0x80
# valid_flag1 bitleri
FLAG1_MIC_MUTE_LED = 0x01
FLAG1_POWER_SAVE = 0x02
FLAG1_LIGHTBAR = 0x04
FLAG1_RELEASE_LEDS = 0x08
FLAG1_PLAYER_LEDS = 0x10
FLAG1_LED_BRIGHTNESS = 0x40
# valid_flag2 bitleri
FLAG2_LIGHTBAR_SETUP = 0x01
FLAG2_COMPAT_VIBRATION2 = 0x02

LIGHTBAR_SETUP_LIGHT_ON = 0x01
LIGHTBAR_SETUP_LIGHT_OUT = 0x02

POWER_SAVE_MIC_MUTE = 0x10

# Oyuncu LED bit desenleri (bit0 = en sol, bit4 = en sağ)
PLAYER_LED_PATTERNS = {
    0: 0x00,
    1: 0x04,
    2: 0x0A,
    3: 0x15,
    4: 0x1B,
    5: 0x1F,
}

TOUCHPAD_W = 1920
TOUCHPAD_H = 1080
GYRO_RES_PER_DEG_S = 1024.0
ACC_RES_PER_G = 8192.0

DPAD_TABLE = {
    0: (0, 1, 0, 0),  # N  -> up
    1: (0, 1, 1, 0),  # NE -> up, right
    2: (0, 0, 1, 0),  # E
    3: (0, 0, 1, 1),  # SE
    4: (0, 0, 0, 1),  # S
    5: (1, 0, 0, 1),  # SW
    6: (1, 0, 0, 0),  # W
    7: (1, 1, 0, 0),  # NW
    8: (0, 0, 0, 0),  # bırakıldı
}


@dataclass
class TouchPoint:
    active: bool = False
    id: int = 0
    x: int = 0
    y: int = 0


@dataclass
class InputState:
    """Çözümlenmiş bir giriş raporu."""
    lx: int = 128
    ly: int = 128
    rx: int = 128
    ry: int = 128
    l2: int = 0
    r2: int = 0
    seq: int = 0
    # yüz tuşları
    square: bool = False
    cross: bool = False
    circle: bool = False
    triangle: bool = False
    # dpad
    dpad_left: bool = False
    dpad_up: bool = False
    dpad_right: bool = False
    dpad_down: bool = False
    dpad_raw: int = 8
    # omuz / tetik
    l1: bool = False
    r1: bool = False
    l2_btn: bool = False
    r2_btn: bool = False
    create: bool = False
    options: bool = False
    l3: bool = False
    r3: bool = False
    ps: bool = False
    touch_btn: bool = False
    mic_btn: bool = False
    # Edge
    fn_left: bool = False
    fn_right: bool = False
    paddle_left: bool = False
    paddle_right: bool = False
    # sensörler (ham)
    gyro: tuple = (0, 0, 0)
    accel: tuple = (0, 0, 0)
    sensor_timestamp: int = 0
    touch: tuple = field(default_factory=lambda: (TouchPoint(), TouchPoint()))
    # tetik efekt durumu
    r2_feedback: int = 0
    l2_feedback: int = 0
    # pil
    battery_level: int = 0       # 0-10 ham
    battery_percent: int = 0
    charging: bool = False
    battery_full: bool = False
    battery_error: bool = False
    # ses
    headphones: bool = False
    mic: bool = False
    mic_muted: bool = False
    usb_data: bool = False
    usb_power: bool = False

    def buttons_pressed(self) -> list[str]:
        names = []
        for n in ("square", "cross", "circle", "triangle", "dpad_left", "dpad_up", "dpad_right",
                  "dpad_down", "l1", "r1", "l2_btn", "r2_btn", "create", "options", "l3", "r3",
                  "ps", "touch_btn", "mic_btn"):
            if getattr(self, n):
                names.append(n)
        return names


def parse_input_report(buf: bytes) -> InputState | None:
    """Ham HID tamponunu çözümler. BT basit mod raporu (10 bayt) için None döner."""
    if not buf:
        return None
    rid = buf[0]
    if rid == REPORT_IN_USB and len(buf) >= IN_REPORT_LEN_USB:
        data = buf[1:64]
    elif rid == REPORT_IN_BT and len(buf) >= IN_REPORT_LEN_BT:
        data = buf[2:65]
    else:
        return None
    return _parse_common(data)


def _parse_common(d: bytes) -> InputState:
    s = InputState()
    s.lx, s.ly, s.rx, s.ry, s.l2, s.r2, s.seq = d[0], d[1], d[2], d[3], d[4], d[5], d[6]
    b0, b1, b2 = d[7], d[8], d[9]
    s.dpad_raw = b0 & 0x0F
    s.dpad_left, s.dpad_up, s.dpad_right, s.dpad_down = DPAD_TABLE.get(s.dpad_raw, (0, 0, 0, 0))
    s.square = bool(b0 & 0x10)
    s.cross = bool(b0 & 0x20)
    s.circle = bool(b0 & 0x40)
    s.triangle = bool(b0 & 0x80)
    s.l1 = bool(b1 & 0x01)
    s.r1 = bool(b1 & 0x02)
    s.l2_btn = bool(b1 & 0x04)
    s.r2_btn = bool(b1 & 0x08)
    s.create = bool(b1 & 0x10)
    s.options = bool(b1 & 0x20)
    s.l3 = bool(b1 & 0x40)
    s.r3 = bool(b1 & 0x80)
    s.ps = bool(b2 & 0x01)
    s.touch_btn = bool(b2 & 0x02)
    s.mic_btn = bool(b2 & 0x04)
    s.fn_left = bool(b2 & 0x10)
    s.fn_right = bool(b2 & 0x20)
    s.paddle_left = bool(b2 & 0x40)
    s.paddle_right = bool(b2 & 0x80)
    gx, gy, gz, ax, ay, az, ts = struct.unpack_from("<hhhhhhI", d, 15)
    s.gyro = (gx, gy, gz)
    s.accel = (ax, ay, az)
    s.sensor_timestamp = ts
    pts = []
    for off in (32, 36):
        c = d[off]
        pts.append(TouchPoint(
            active=not (c & 0x80),
            id=c & 0x7F,
            x=((d[off + 2] & 0x0F) << 8) | d[off + 1],
            y=(d[off + 3] << 4) | ((d[off + 2] & 0xF0) >> 4),
        ))
    s.touch = tuple(pts)
    s.r2_feedback = d[41]
    s.l2_feedback = d[42]
    status = d[52]
    s.battery_level = status & 0x0F
    chg = (status >> 4) & 0x0F
    s.charging = chg == 0x01
    s.battery_full = chg == 0x02
    s.battery_error = chg in (0x0A, 0x0B, 0x0F)
    s.battery_percent = 100 if s.battery_full else min(s.battery_level * 10 + 5, 100)
    st2 = d[53]
    s.headphones = bool(st2 & 0x01)
    s.mic = bool(st2 & 0x02)
    s.mic_muted = bool(st2 & 0x04)
    s.usb_data = bool(st2 & 0x08)
    s.usb_power = bool(st2 & 0x10)
    return s


@dataclass
class OutputState:
    """Kola gönderilecek tüm çıkış durumu (ışık, titreşim, tetikler...)."""
    motor_left: int = 0      # güçlü (düşük frekans) motor 0-255
    motor_right: int = 0     # zayıf (yüksek frekans) motor 0-255
    mic_led: int = 0         # 0 kapalı, 1 açık, 2 yanıp sönen
    mic_mute: bool = False
    lightbar: tuple = (0, 0, 255)
    led_brightness: int = 0  # 0 yüksek, 1 orta, 2 düşük
    player_leds: int = 0x04
    player_led_fade: bool = False
    right_trigger: bytes = bytes(11)
    left_trigger: bytes = bytes(11)
    headphone_volume: int | None = None
    speaker_volume: int | None = None
    use_vibration_v2: bool = False
    lightbar_setup: int = 0  # 0 yok, 1 aç, 2 söndür (bir kez)

    def build_common(self) -> bytearray:
        c = bytearray(47)
        f0 = FLAG0_HAPTICS_SELECT | FLAG0_RIGHT_TRIGGER | FLAG0_LEFT_TRIGGER
        f1 = FLAG1_MIC_MUTE_LED | FLAG1_POWER_SAVE | FLAG1_LIGHTBAR | FLAG1_PLAYER_LEDS | FLAG1_LED_BRIGHTNESS
        f2 = 0
        if self.use_vibration_v2:
            f2 |= FLAG2_COMPAT_VIBRATION2
        else:
            f0 |= FLAG0_COMPAT_VIBRATION
        if self.headphone_volume is not None:
            f0 |= FLAG0_HEADPHONE_VOLUME
            c[4] = max(0, min(255, self.headphone_volume))
        if self.speaker_volume is not None:
            f0 |= FLAG0_SPEAKER_VOLUME
            c[5] = max(0, min(255, self.speaker_volume))
        if self.lightbar_setup:
            f2 |= FLAG2_LIGHTBAR_SETUP
            c[41] = self.lightbar_setup
        c[0] = f0
        c[1] = f1
        c[2] = max(0, min(255, self.motor_right))
        c[3] = max(0, min(255, self.motor_left))
        c[8] = self.mic_led & 0x03
        c[9] = POWER_SAVE_MIC_MUTE if self.mic_mute else 0
        rt = bytes(self.right_trigger)[:11].ljust(11, b"\0")
        lt = bytes(self.left_trigger)[:11].ljust(11, b"\0")
        c[10:21] = rt
        c[21:32] = lt
        c[38] = f2
        c[42] = self.led_brightness & 0x03
        c[43] = (self.player_leds & 0x1F) | (0x20 if self.player_led_fade else 0)
        r, g, b = self.lightbar
        c[44] = max(0, min(255, int(r)))
        c[45] = max(0, min(255, int(g)))
        c[46] = max(0, min(255, int(b)))
        return c


def build_output_report_usb(state: OutputState) -> bytes:
    buf = bytearray(OUT_REPORT_LEN_USB)
    buf[0] = REPORT_OUT_USB
    buf[1:48] = state.build_common()
    return bytes(buf)


def build_output_report_bt(state: OutputState, seq: int) -> bytes:
    buf = bytearray(OUT_REPORT_LEN_BT)
    buf[0] = REPORT_OUT_BT
    buf[1] = (seq & 0x0F) << 4
    buf[2] = 0x10
    buf[3:50] = state.build_common()
    crc = zlib.crc32(bytes([BT_CRC_SEED_OUTPUT]) + bytes(buf[:74])) & 0xFFFFFFFF
    struct.pack_into("<I", buf, 74, crc)
    return bytes(buf)


def verify_bt_input_crc(buf: bytes) -> bool:
    if len(buf) < IN_REPORT_LEN_BT:
        return False
    expected = struct.unpack_from("<I", buf, 74)[0]
    calc = zlib.crc32(bytes([BT_CRC_SEED_INPUT]) + bytes(buf[:74])) & 0xFFFFFFFF
    return calc == expected


def parse_firmware_info(buf: bytes) -> dict:
    """Özellik raporu 0x20 içeriğini çözümler."""
    info = {}
    try:
        info["build_date"] = bytes(buf[1:12]).decode("ascii", "ignore").strip("\0 ")
        info["build_time"] = bytes(buf[12:20]).decode("ascii", "ignore").strip("\0 ")
        info["hw_version"] = struct.unpack_from("<I", buf, 24)[0]
        info["fw_version"] = struct.unpack_from("<I", buf, 28)[0]
        info["update_version"] = struct.unpack_from("<H", buf, 44)[0]
    except Exception:
        pass
    return info


def parse_mac_from_pairing_info(buf: bytes) -> str | None:
    try:
        mac = buf[1:7]
        return ":".join(f"{b:02X}" for b in reversed(mac))
    except Exception:
        return None
