"""Pengaturan aplikasi yang diatur admin (Panel Admin > Setting), di data\\app_settings.json.

Berlaku untuk semua PC yang memakai folder data yang sama. Nilai yang belum pernah diatur
memakai DEFAULTS. Tulis utuh atau tidak sama sekali (file .tmp lalu os.replace).
"""

import json
import os
import threading

from elearning import config as C

DEFAULTS = {
    "login_carousel_rows3": False,   # carousel login: + baris atas & bawah (total 30 portfolio)
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
    return _load().get(key, DEFAULTS.get(key))


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
