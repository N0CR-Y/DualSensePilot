"""Adaptif tetik efekt üreticileri.

Nielk1'in TriggerEffectGenerator (MIT) çalışmasının Python portu:
https://gist.github.com/Nielk1/6d54cc2c00d2201ccb8c2720ad7538db
Her fonksiyon 11 baytlık efekt bloğu döner (mod + 10 parametre).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Mod baytları
MODE_OFF = 0x05
MODE_FEEDBACK = 0x21
MODE_WEAPON = 0x25
MODE_VIBRATION = 0x26
MODE_BOW = 0x22
MODE_GALLOPING = 0x23
MODE_MACHINE = 0x27
MODE_SIMPLE_FEEDBACK = 0x01
MODE_SIMPLE_WEAPON = 0x02
MODE_SIMPLE_VIBRATION = 0x06
MODE_LIMITED_FEEDBACK = 0x11
MODE_LIMITED_WEAPON = 0x12


def _block(mode: int, *params: int) -> bytes:
    b = bytearray(11)
    b[0] = mode & 0xFF
    for i, p in enumerate(params[:10]):
        b[1 + i] = int(p) & 0xFF
    return bytes(b)


def off() -> bytes:
    return _block(MODE_OFF)


def feedback(position: int, strength: int) -> bytes:
    """Başlangıç bölgesinden sonra sabit direnç. position 0-9, strength 0-8."""
    position = _clamp(position, 0, 9)
    strength = _clamp(strength, 0, 8)
    if strength == 0:
        return off()
    force = (strength - 1) & 0x07
    force_zones = 0
    active = 0
    for i in range(position, 10):
        force_zones |= force << (3 * i)
        active |= 1 << i
    return _block(MODE_FEEDBACK, active & 0xFF, (active >> 8) & 0xFF,
                  force_zones & 0xFF, (force_zones >> 8) & 0xFF,
                  (force_zones >> 16) & 0xFF, (force_zones >> 24) & 0xFF, 0, 0, 0, 0)


def weapon(start: int, end: int, strength: int) -> bytes:
    """Silah tetiği: start 2-7, end start+1..8, strength 0-8."""
    start = _clamp(start, 2, 7)
    end = _clamp(end, start + 1, 8)
    strength = _clamp(strength, 0, 8)
    if strength == 0:
        return off()
    zones = (1 << start) | (1 << end)
    return _block(MODE_WEAPON, zones & 0xFF, (zones >> 8) & 0xFF, strength - 1)


def vibration(position: int, amplitude: int, frequency: int) -> bytes:
    """Titreşim: position 0-9, amplitude 0-8, frequency 0-255 Hz."""
    position = _clamp(position, 0, 9)
    amplitude = _clamp(amplitude, 0, 8)
    frequency = _clamp(frequency, 0, 255)
    if amplitude == 0 or frequency == 0:
        return off()
    sv = (amplitude - 1) & 0x07
    amp_zones = 0
    active = 0
    for i in range(position, 10):
        amp_zones |= sv << (3 * i)
        active |= 1 << i
    return _block(MODE_VIBRATION, active & 0xFF, (active >> 8) & 0xFF,
                  amp_zones & 0xFF, (amp_zones >> 8) & 0xFF,
                  (amp_zones >> 16) & 0xFF, (amp_zones >> 24) & 0xFF, 0, 0, frequency, 0)


def multiple_position_feedback(strengths: list[int]) -> bytes:
    """10 bölge için ayrı direnç (her biri 0-8)."""
    strengths = list(strengths)[:10] + [0] * max(0, 10 - len(strengths))
    if not any(s > 0 for s in strengths):
        return off()
    force_zones = 0
    active = 0
    for i, s in enumerate(strengths):
        s = _clamp(s, 0, 8)
        if s > 0:
            force_zones |= ((s - 1) & 0x07) << (3 * i)
            active |= 1 << i
    return _block(MODE_FEEDBACK, active & 0xFF, (active >> 8) & 0xFF,
                  force_zones & 0xFF, (force_zones >> 8) & 0xFF,
                  (force_zones >> 16) & 0xFF, (force_zones >> 24) & 0xFF, 0, 0, 0, 0)


def slope_feedback(start: int, end: int, start_strength: int, end_strength: int) -> bytes:
    """Doğrusal artan/azalan direnç. start 0-8, end start+1..9, kuvvetler 1-8."""
    start = _clamp(start, 0, 8)
    end = _clamp(end, start + 1, 9)
    start_strength = _clamp(start_strength, 1, 8)
    end_strength = _clamp(end_strength, 1, 8)
    strengths = [0] * 10
    slope = (end_strength - start_strength) / (end - start)
    for i in range(start, 10):
        if i <= end:
            strengths[i] = int(round(start_strength + slope * (i - start)))
        else:
            strengths[i] = end_strength
    return multiple_position_feedback(strengths)


def multiple_position_vibration(frequency: int, amplitudes: list[int]) -> bytes:
    amplitudes = list(amplitudes)[:10] + [0] * max(0, 10 - len(amplitudes))
    frequency = _clamp(frequency, 0, 255)
    if frequency == 0 or not any(a > 0 for a in amplitudes):
        return off()
    zones = 0
    active = 0
    for i, a in enumerate(amplitudes):
        a = _clamp(a, 0, 8)
        if a > 0:
            zones |= ((a - 1) & 0x07) << (3 * i)
            active |= 1 << i
    return _block(MODE_VIBRATION, active & 0xFF, (active >> 8) & 0xFF,
                  zones & 0xFF, (zones >> 8) & 0xFF, (zones >> 16) & 0xFF, (zones >> 24) & 0xFF,
                  0, 0, frequency, 0)


def bow(start: int, end: int, strength: int, snap_force: int) -> bytes:
    """Yay: start 0-8, end start+1..8, strength 0-8, snap_force 0-8."""
    start = _clamp(start, 0, 7)
    end = _clamp(end, start + 1, 8)
    strength = _clamp(strength, 0, 8)
    snap_force = _clamp(snap_force, 0, 8)
    if strength == 0 or snap_force == 0:
        return off()
    zones = (1 << start) | (1 << end)
    pair = ((strength - 1) & 0x07) | (((snap_force - 1) & 0x07) << 3)
    return _block(MODE_BOW, zones & 0xFF, (zones >> 8) & 0xFF, pair & 0xFF, (pair >> 8) & 0xFF)


def galloping(start: int, end: int, first_foot: int, second_foot: int, frequency: int) -> bytes:
    """Dörtnala: start 0-8, end start+1..9, first 0-6, second first+1..7, frequency 0-255."""
    start = _clamp(start, 0, 8)
    end = _clamp(end, start + 1, 9)
    first_foot = _clamp(first_foot, 0, 6)
    second_foot = _clamp(second_foot, first_foot + 1, 7)
    frequency = _clamp(frequency, 0, 255)
    if frequency == 0:
        return off()
    zones = (1 << start) | (1 << end)
    time_ratio = (second_foot & 0x07) | ((first_foot & 0x07) << 3)
    return _block(MODE_GALLOPING, zones & 0xFF, (zones >> 8) & 0xFF, time_ratio & 0xFF, frequency)


def machine(start: int, end: int, amp_a: int, amp_b: int, frequency: int, period: int) -> bytes:
    """Makine: start 0-8, end start+1..9, amp 0-7, frequency 0-255, period 0-255 (0.1 s)."""
    start = _clamp(start, 0, 8)
    end = _clamp(end, start + 1, 9)
    amp_a = _clamp(amp_a, 0, 7)
    amp_b = _clamp(amp_b, 0, 7)
    frequency = _clamp(frequency, 0, 255)
    period = _clamp(period, 0, 255)
    if frequency == 0:
        return off()
    zones = (1 << start) | (1 << end)
    pair = (amp_a & 0x07) | ((amp_b & 0x07) << 3)
    return _block(MODE_MACHINE, zones & 0xFF, (zones >> 8) & 0xFF, pair & 0xFF, frequency, period)


def simple_feedback(position: int, strength: int) -> bytes:
    return _block(MODE_SIMPLE_FEEDBACK, _clamp(position, 0, 255), _clamp(strength, 0, 255))


def simple_weapon(start: int, end: int, strength: int) -> bytes:
    return _block(MODE_SIMPLE_WEAPON, _clamp(start, 0, 255), _clamp(end, 0, 255), _clamp(strength, 0, 255))


def simple_vibration(position: int, amplitude: int, frequency: int) -> bytes:
    if frequency <= 0 or amplitude <= 0:
        return off()
    return _block(MODE_SIMPLE_VIBRATION, _clamp(frequency, 0, 255), _clamp(amplitude, 0, 255), _clamp(position, 0, 255))


def raw(values: list[int]) -> bytes:
    return _block(*([int(v) & 0xFF for v in values[:11]] + [0] * max(0, 11 - len(values))))


def _clamp(v, lo, hi):
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Mod tanımları (UI ve profil için)
# ---------------------------------------------------------------------------

@dataclass
class ParamSpec:
    key: str
    label: str
    min: int
    max: int
    default: int
    unit: str = ""


@dataclass
class ModeSpec:
    key: str
    label: str
    description: str
    params: list[ParamSpec] = field(default_factory=list)
    builder: object = None
    array_param: str | None = None   # 10 değerli dizi alanı (ör. bölgeler)
    array_label: str = ""
    array_max: int = 8


MODES: dict[str, ModeSpec] = {}


def _reg(spec: ModeSpec):
    MODES[spec.key] = spec
    return spec


_reg(ModeSpec("off", "Kapalı (Normal)", "Efekt yok, tetik serbest.", [], lambda p: off()))
_reg(ModeSpec("feedback", "Direnç (Feedback)",
              "Belirlenen konumdan sonra sabit direnç uygular.",
              [ParamSpec("position", "Başlangıç konumu", 0, 9, 0),
               ParamSpec("strength", "Kuvvet", 0, 8, 5)],
              lambda p: feedback(p.get("position", 0), p.get("strength", 5))))
_reg(ModeSpec("weapon", "Silah tetiği (Weapon)",
              "Başlangıç ile bitiş arasında direnç; bitişte 'tetik düşmesi' hissi.",
              [ParamSpec("start", "Başlangıç", 2, 7, 2),
               ParamSpec("end", "Bitiş", 3, 8, 5),
               ParamSpec("strength", "Kuvvet", 0, 8, 8)],
              lambda p: weapon(p.get("start", 2), p.get("end", 5), p.get("strength", 8))))
_reg(ModeSpec("vibration", "Titreşim (Vibration)",
              "Belirlenen konumdan sonra tetik titreşir (otomatik silah hissi).",
              [ParamSpec("position", "Başlangıç konumu", 0, 9, 2),
               ParamSpec("amplitude", "Şiddet", 0, 8, 6),
               ParamSpec("frequency", "Frekans", 0, 255, 30, "Hz")],
              lambda p: vibration(p.get("position", 2), p.get("amplitude", 6), p.get("frequency", 30))))
_reg(ModeSpec("slope", "Rampa direnç (Slope)",
              "Direnç başlangıçtan bitişe doğrusal olarak değişir.",
              [ParamSpec("start", "Başlangıç", 0, 8, 0),
               ParamSpec("end", "Bitiş", 1, 9, 9),
               ParamSpec("start_strength", "Başlangıç kuvveti", 1, 8, 1),
               ParamSpec("end_strength", "Bitiş kuvveti", 1, 8, 8)],
              lambda p: slope_feedback(p.get("start", 0), p.get("end", 9),
                                       p.get("start_strength", 1), p.get("end_strength", 8))))
_reg(ModeSpec("bow", "Yay (Bow)",
              "Gerilen yay hissi; bırakınca geri tepme.",
              [ParamSpec("start", "Başlangıç", 0, 7, 1),
               ParamSpec("end", "Bitiş", 1, 8, 6),
               ParamSpec("strength", "Kuvvet", 0, 8, 6),
               ParamSpec("snap_force", "Geri tepme", 0, 8, 6)],
              lambda p: bow(p.get("start", 1), p.get("end", 6), p.get("strength", 6), p.get("snap_force", 6))))
_reg(ModeSpec("galloping", "Dörtnala (Galloping)",
              "Ritmik, at koşusu gibi tetik hareketi (düşük frekansta belirgin).",
              [ParamSpec("start", "Başlangıç", 0, 8, 0),
               ParamSpec("end", "Bitiş", 1, 9, 9),
               ParamSpec("first_foot", "1. adım", 0, 6, 2),
               ParamSpec("second_foot", "2. adım", 1, 7, 4),
               ParamSpec("frequency", "Frekans", 0, 255, 8, "Hz")],
              lambda p: galloping(p.get("start", 0), p.get("end", 9), p.get("first_foot", 2),
                                  p.get("second_foot", 4), p.get("frequency", 8))))
_reg(ModeSpec("machine", "Makine (Machine)",
              "İki şiddet arasında salınan titreşim.",
              [ParamSpec("start", "Başlangıç", 0, 8, 1),
               ParamSpec("end", "Bitiş", 1, 9, 9),
               ParamSpec("amp_a", "Şiddet A", 0, 7, 7),
               ParamSpec("amp_b", "Şiddet B", 0, 7, 2),
               ParamSpec("frequency", "Frekans", 0, 255, 40, "Hz"),
               ParamSpec("period", "Periyot", 0, 255, 5, "x0.1s")],
              lambda p: machine(p.get("start", 1), p.get("end", 9), p.get("amp_a", 7), p.get("amp_b", 2),
                                p.get("frequency", 40), p.get("period", 5))))
_reg(ModeSpec("multi_feedback", "Bölgesel direnç (10 bölge)",
              "Her tetik bölgesi için ayrı direnç kuvveti.",
              [],
              lambda p: multiple_position_feedback(p.get("zones", [0] * 10)),
              array_param="zones", array_label="Bölge kuvvetleri", array_max=8))
_reg(ModeSpec("multi_vibration", "Bölgesel titreşim (10 bölge)",
              "Her bölge için ayrı titreşim şiddeti, tek frekans.",
              [ParamSpec("frequency", "Frekans", 0, 255, 30, "Hz")],
              lambda p: multiple_position_vibration(p.get("frequency", 30), p.get("zones", [0] * 10)),
              array_param="zones", array_label="Bölge şiddetleri", array_max=8))
_reg(ModeSpec("simple_feedback", "Basit direnç (eski mod)",
              "Ham parametreli eski direnç modu (0-255).",
              [ParamSpec("position", "Başlangıç", 0, 255, 0),
               ParamSpec("strength", "Kuvvet", 0, 255, 180)],
              lambda p: simple_feedback(p.get("position", 0), p.get("strength", 180))))
_reg(ModeSpec("simple_weapon", "Basit silah (eski mod)",
              "Ham parametreli eski silah modu (0-255).",
              [ParamSpec("start", "Başlangıç", 0, 255, 0x45),
               ParamSpec("end", "Bitiş", 0, 255, 0xA0),
               ParamSpec("strength", "Kuvvet", 0, 255, 255)],
              lambda p: simple_weapon(p.get("start", 0x45), p.get("end", 0xA0), p.get("strength", 255))))
_reg(ModeSpec("simple_vibration", "Basit titreşim (eski mod)",
              "Ham parametreli eski titreşim modu.",
              [ParamSpec("position", "Başlangıç", 0, 255, 0),
               ParamSpec("amplitude", "Şiddet", 0, 255, 200),
               ParamSpec("frequency", "Frekans", 0, 255, 30, "Hz")],
              lambda p: simple_vibration(p.get("position", 0), p.get("amplitude", 200), p.get("frequency", 30))))
_reg(ModeSpec("raw", "Ham baytlar (Uzman)",
              "11 baytlık efekt bloğunu doğrudan gir.",
              [],
              lambda p: raw(p.get("bytes", [5] + [0] * 10)),
              array_param="bytes", array_label="Baytlar (mod + 10 parametre)", array_max=255))


def build_effect(mode: str, params: dict) -> bytes:
    spec = MODES.get(mode)
    if spec is None:
        return off()
    try:
        return spec.builder(params or {})
    except Exception:
        return off()


# Hazır ayarlar: (ad, mod, parametreler)
PRESETS: list[tuple[str, str, dict]] = [
    ("Normal", "off", {}),
    ("Yumuşak direnç", "feedback", {"position": 0, "strength": 2}),
    ("Orta direnç", "feedback", {"position": 0, "strength": 5}),
    ("Sert direnç", "feedback", {"position": 0, "strength": 8}),
    ("Yarı yolda direnç", "feedback", {"position": 5, "strength": 8}),
    ("Rampa (artan)", "slope", {"start": 0, "end": 9, "start_strength": 1, "end_strength": 8}),
    ("Tabanca", "weapon", {"start": 2, "end": 5, "strength": 8}),
    ("Tetik stop (kısa)", "weapon", {"start": 3, "end": 4, "strength": 8}),
    ("Pompalı", "weapon", {"start": 4, "end": 8, "strength": 8}),
    ("Otomatik silah", "vibration", {"position": 2, "amplitude": 6, "frequency": 35}),
    ("Ağır makineli", "vibration", {"position": 1, "amplitude": 8, "frequency": 20}),
    ("Yay", "bow", {"start": 1, "end": 6, "strength": 6, "snap_force": 6}),
    ("Dörtnala", "galloping", {"start": 0, "end": 9, "first_foot": 2, "second_foot": 4, "frequency": 8}),
    ("Makine", "machine", {"start": 1, "end": 9, "amp_a": 7, "amp_b": 2, "frequency": 40, "period": 5}),
    ("Gaz pedalı (araba)", "slope", {"start": 0, "end": 9, "start_strength": 2, "end_strength": 5}),
    ("Fren (araba)", "feedback", {"position": 3, "strength": 7}),
]
