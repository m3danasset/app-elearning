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
# Fitur yang bisa dimatikan dari jendela Dev (label ringkas). Bawaan: semua ON.
FEATURES = (
    ("intro", "Video pembuka"),
    ("badges", "Badge"),
    ("certificate", "Sertifikat"),
    ("floating", "Mode mengambang"),
    ("mini_player", "Mini player"),
    ("palette", "Search Ctrl+K"),
    ("fps60", "60 fps (PC kuat)"),
    ("animations", "Animasi & video latar bergerak (mati = latar statis; Ryzen 3: selalu mati)"),
    ("survey", "Survey trial"),
    ("student_survey", "Survey murid setelah BASIC 2"),
    ("safesearch", "SafeSearch Chrome murid SUPERKIDS"),
    ("teaser", "Video teaser kursus di Dashboard murid"),
)
# Warna aksen UI (tombol utama, sorotan). Berlaku penuh setelah aplikasi dibuka ulang.
ACCENTS = {
    "orange": ("Oranye", "#ea7600", "#ff8a1a"),
    "blue": ("Biru", "#2f7de1", "#4b95f0"),
    "green": ("Hijau", "#2e9e6e", "#3fb68b"),
    "purple": ("Ungu", "#8a5cf6", "#a07cff"),
    "pink": ("Merah muda", "#e0457b", "#f0628f"),
    "red": ("Merah", "#d93a3a", "#ef5353"),
}
DEFAULTS = {
    "login_mode": "carousel",
    "accent": "orange",
    "perf_preset": "auto",       # preset performa (Dev > Performa), dibaca config saat mulai
}

_lock = threading.Lock()
# lapisan sementara (Dev > Apply Now): hanya di memori, hilang saat aplikasi ditutup.
# Bentuknya sama dengan file: kunci biasa + "features" / "values" (dict, digabung per isi).
_session = {}
_MERGED = ("features", "values")


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


def _effective():
    """Isi file + lapisan sementara (Apply Now) di atasnya."""
    data = _load()
    for k, v in _session.items():
        if k in _MERGED:
            data[k] = {**(data.get(k) or {}), **v}
        else:
            data[k] = v
    return data


def saved(key):
    """Nilai yang TERSIMPAN di file (tanpa lapisan sementara)."""
    return _load().get(key, DEFAULTS.get(key))


def set_session(key, value):
    """Apply Now: pasang sementara (tidak ditulis ke file)."""
    if key in _MERGED:
        _session[key] = {**_session.get(key, {}), **value}
    else:
        _session[key] = value


def session():
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in _session.items()}


def clear_session(key=None):
    if key is None:
        _session.clear()
    else:
        _session.pop(key, None)


def get(key):
    data = _effective()
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


def feature(name):
    """True kalau fitur ON (bawaan ON). Aman dipanggil dari mana saja."""
    try:
        return bool(_effective().get("features", {}).get(name, True))
    except Exception:
        return True


def set_feature(name, on):
    data = _load()                   # simpan ke file: mulai dari isi file, bukan sementara
    feats = dict(data.get("features") or {})
    feats[name] = bool(on)
    set("features", feats)


def apply_theme():
    """Pasang warna aksen pilihan ke config (dipanggil sekali saat aplikasi mulai)."""
    try:
        key = get("accent")
        _name, acc, hover = ACCENTS.get(key, ACCENTS["orange"])
        C.ACCENT, C.ACCENT_HOVER = acc, hover
    except Exception as exc:
        C.log(f"Warna aksen tidak bisa dipasang: {exc!r}")
