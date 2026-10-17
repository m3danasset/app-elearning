"""Pengaturan aplikasi yang diatur admin (Panel Admin > Setting), di data\\app_settings.json.

Berlaku untuk semua PC yang memakai folder data yang sama. Nilai yang belum pernah diatur
memakai DEFAULTS. Tulis utuh atau tidak sama sekali (file .tmp lalu os.replace).
"""

import json
import os
import threading

from elearning import config as C

# Tampilan layar login:
#   "carousel" = carousel 1 baris + video latar (bawaan)
#   "rows3"    = carousel 3 baris (30 portfolio), TANPA video latar
#   "video"    = video latar saja, tanpa carousel
LOGIN_MODES = ("carousel", "rows3", "video")
DEFAULTS = {
    "login_mode": "carousel",
}

_lock = threading.Lock()


def _path():
    # file sendiri: data\settings.json sudah dipakai blender_launcher (posisi ikon, ukuran mini)
    return os.path.join(C.DATA_DIR, "app_settings.json")


def _load():
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(key):
    data = _load()
    if key == "login_mode" and key not in data and data.get("login_carousel_rows3"):
        return "rows3"                       # pengaturan versi sebelumnya (switch 3 baris)
    value = data.get(key, DEFAULTS.get(key))
    if key == "login_mode" and value not in LOGIN_MODES:
        return DEFAULTS[key]
    return value


def login_mode():
    """Tampilan layar login: "carousel", "rows3", atau "video" (lihat LOGIN_MODES)."""
    try:
        return get("login_mode")
    except Exception:
        return DEFAULTS["login_mode"]


def set(key, value):     # noqa: A001 - nama sengaja sederhana (app_settings.set)
    """Simpan satu pengaturan. OSError dilempar kalau folder data tidak bisa ditulis."""
    with _lock:
        data = _load()
        data[key] = value
        os.makedirs(C.DATA_DIR, exist_ok=True)
        tmp = _path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _path())
