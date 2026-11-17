"""Profil ve uygulama ayarları (JSON, %APPDATA%\\DualSensePilot)."""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path

log = logging.getLogger(__name__)

_APPDATA = Path(os.environ.get("APPDATA", str(Path.home())))
APP_DIR = _APPDATA / "DualSensePilot"
_OLD_APP_DIR = _APPDATA / "DualSenseStudio"  # eski ad: DualSense Studio
PROFILE_DIR = APP_DIR / "profiles"
SETTINGS_FILE = APP_DIR / "settings.json"


def _migrate_from_old_app_dir() -> None:
    """Uygulama "DualSense Studio" adıyla kurulmuşsa eski profil/ayarları yeni
    klasöre bir kerelik taşır (kullanıcı verisini kaybetmemek için)."""
    if APP_DIR.exists() or not _OLD_APP_DIR.exists():
        return
    try:
        shutil.copytree(_OLD_APP_DIR, APP_DIR)
        log.info("eski ayarlar taşındı: %s -> %s", _OLD_APP_DIR, APP_DIR)
    except Exception as e:  # noqa: BLE001
        log.warning("eski ayarlar taşınamadı: %s", e)


def _compatible_type(default, value) -> bool:
    """Kaydedilmiş bir alanın tipi, dataclass alanının varsayılan tipiyle makul
    ölçüde uyumlu mu? (Bozuk/elle düzenlenmiş JSON'un, örn. bir listenin yerine
    string gelmesi gibi durumlarda, uygulamayı sonradan çökertmemesi için.)"""
    if default is None or value is None:
        return True
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


@dataclass
class TriggerConfig:
    mode: str = "off"
    params: dict = field(default_factory=dict)


@dataclass
class Profile:
    name: str = "Varsayılan"
    # Işık çubuğu
    lightbar_mode: str = "static"          # static | battery | rainbow | off
    lightbar_color: list = field(default_factory=lambda: [0, 110, 255])
    lightbar_brightness: int = 0           # 0 yüksek, 1 orta, 2 düşük
    rainbow_speed: int = 50                # 1-100
    player_leds: int = 0x04
    player_led_fade: bool = False
    mic_led: int = 0                       # 0 kapalı 1 açık 2 yanıp sönen
    mic_mute: bool = False
    # Tetikler
    left_trigger: TriggerConfig = field(default_factory=TriggerConfig)
    right_trigger: TriggerConfig = field(default_factory=TriggerConfig)
    # Titreşim
    rumble_passthrough: bool = True
    rumble_scale: int = 100                # %
    rumble_min: int = 0                    # alt eşik
    # Emülasyon
    emulation: str = "x360"                # none | x360 | ds4
    stick_deadzone: int = 5                # %
    invert_left_y: bool = False
    invert_right_y: bool = False
    swap_sticks: bool = False
    touchpad_as_back: bool = False
    trigger_threshold: int = 0             # 0-255 bu değerin altı yok sayılır
    # Otomatik profil
    exe_names: list = field(default_factory=list)

    # -- dönüşüm ---------------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        p = cls()
        for k, v in (d or {}).items():
            if k in ("left_trigger", "right_trigger"):
                tc = TriggerConfig()
                if isinstance(v, dict):
                    tc.mode = v.get("mode", "off")
                    params = v.get("params", {})
                    tc.params = dict(params) if isinstance(params, dict) else {}
                setattr(p, k, tc)
            elif hasattr(p, k):
                if not _compatible_type(getattr(p, k), v):
                    log.warning("profil alanı yok sayıldı (tip uyumsuz): %s=%r", k, v)
                    continue
                setattr(p, k, v)
        return p

    def clone(self) -> "Profile":
        return copy.deepcopy(self)

    @property
    def file_name(self) -> str:
        safe = re.sub(r"[^\w\-. ]+", "_", self.name, flags=re.UNICODE).strip() or "profil"
        return safe + ".json"


@dataclass
class Settings:
    active_profile: str = "Varsayılan"
    auto_switch: bool = True
    start_minimized: bool = False
    minimize_to_tray: bool = True
    auto_emulation: bool = True
    hide_with_hidhide: bool = False
    lightbar_off_when_idle: bool = False
    window_geometry: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        s = cls()
        for k, v in (d or {}).items():
            if hasattr(s, k):
                if not _compatible_type(getattr(s, k), v):
                    log.warning("ayar alanı yok sayıldı (tip uyumsuz): %s=%r", k, v)
                    continue
                setattr(s, k, v)
        return s


class ProfileStore:
    def __init__(self):
        _migrate_from_old_app_dir()
        APP_DIR.mkdir(parents=True, exist_ok=True)
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self.profiles: dict[str, Profile] = {}
        self.settings = Settings()
        self.load_all()

    # -- ayarlar ---------------------------------------------------------
    def load_all(self):
        self.profiles.clear()
        for f in sorted(PROFILE_DIR.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    p = Profile.from_dict(json.load(fh))
                self.profiles[p.name] = p
            except Exception as e:  # noqa: BLE001
                log.warning("profil okunamadı %s: %s", f, e)
        if not self.profiles:
            self._create_defaults()
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
                    self.settings = Settings.from_dict(json.load(fh))
            except Exception as e:  # noqa: BLE001
                log.warning("ayarlar okunamadı: %s", e)
        if self.settings.active_profile not in self.profiles:
            self.settings.active_profile = next(iter(self.profiles))

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
                json.dump(self.settings.to_dict(), fh, ensure_ascii=False, indent=2)
        except Exception as e:  # noqa: BLE001
            log.warning("ayarlar kaydedilemedi: %s", e)

    def _create_defaults(self):
        defaults = [
            Profile(name="Varsayılan"),
            Profile(name="FPS",
                    lightbar_color=[255, 40, 40],
                    left_trigger=TriggerConfig("feedback", {"position": 2, "strength": 4}),
                    right_trigger=TriggerConfig("weapon", {"start": 2, "end": 5, "strength": 8})),
            Profile(name="Yarış",
                    lightbar_color=[255, 140, 0],
                    left_trigger=TriggerConfig("feedback", {"position": 3, "strength": 7}),
                    right_trigger=TriggerConfig("slope", {"start": 0, "end": 9, "start_strength": 2, "end_strength": 5})),
            Profile(name="Sadece ışık (emülasyon yok)", emulation="none", lightbar_mode="battery"),
        ]
        for p in defaults:
            self.profiles[p.name] = p
            self.save_profile(p)

    # -- profiller -------------------------------------------------------
    def save_profile(self, p: Profile, old_name: str | None = None):
        if old_name and old_name != p.name:
            self.delete_profile(old_name, _keep_file=False)
        self.profiles[p.name] = p
        try:
            with open(PROFILE_DIR / p.file_name, "w", encoding="utf-8") as fh:
                json.dump(p.to_dict(), fh, ensure_ascii=False, indent=2)
        except Exception as e:  # noqa: BLE001
            log.warning("profil kaydedilemedi: %s", e)

    def delete_profile(self, name: str, _keep_file: bool = False):
        p = self.profiles.pop(name, None)
        if p and not _keep_file:
            try:
                (PROFILE_DIR / p.file_name).unlink(missing_ok=True)
            except Exception as e:  # noqa: BLE001
                log.warning("profil silinemedi: %s", e)
        if not self.profiles:
            self._create_defaults()
        if self.settings.active_profile not in self.profiles:
            self.settings.active_profile = next(iter(self.profiles))
            self.save_settings()

    def get(self, name: str) -> Profile | None:
        return self.profiles.get(name)

    @property
    def active(self) -> Profile:
        p = self.profiles.get(self.settings.active_profile)
        if p is None:
            p = next(iter(self.profiles.values()))
        return p

    def find_for_exe(self, exe_name: str) -> Profile | None:
        exe_name = (exe_name or "").lower()
        if not exe_name:
            return None
        for p in self.profiles.values():
            for n in p.exe_names:
                if n and n.lower() == exe_name:
                    return p
        return None
