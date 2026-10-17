"""Nilai pengaturan yang bisa diisi dev (jendela Dev > Settings > Nilai).

Disimpan di data\\app_settings.json ("values": {kunci: teks isian}) dan dipasang ke modul
saat aplikasi mulai (App) dan saat dev menekan Apply. Nilai bawaan diambil dari kode (dicatat
sebelum ditimpa), jadi "Reset" mengembalikan nilai aslinya.

Menambah nilai baru: tambahkan satu baris ke VALUES
  (kunci, grup, label ringkas, jenis, [(modul, atribut), ...])
jenis: int, float, str, list (pisah koma), hours ("8-18"), ints (pisah koma), secs (detik per
kartu -> SPEED = 1/x).
"""

import importlib

from elearning import app_settings
from elearning import config as C

VALUES = (
    ("login_max_len", "Login", "Maks. karakter ID/PIN", "int",
     [("elearning.ui.login_screen", "MAX_LEN")]),
    ("carousel_secs", "Carousel", "Detik per kartu", "secs",
     [("elearning.ui.carousel3d", "SPEED")]),
    ("carousel_bright", "Carousel", "Kecerahan kartu (0-1)", "float",
     [("elearning.ui.carousel3d", "BRIGHT")]),
    ("carousel_items", "Carousel", "Portfolio per baris", "int",
     [("elearning.ui.carousel3d", "MAX_ITEMS")]),
    ("login_video_opacity", "Video", "Video latar login (0-1)", "float",
     [("elearning.config", "LOGIN_VIDEO_OPACITY"), ("elearning.ui.login_bg", "OPACITY")]),
    ("home_video_dim", "Video", "Video latar beranda (0-1)", "float",
     [("elearning.config", "VIDEO_DIM")]),
    ("intro_timeout", "Video", "Intro macet -> lewati (dtk)", "float",
     [("elearning.ui.lesson_view", "INTRO_TIMEOUT")]),
    ("sub_up_pos", "Video", "Subtitle naik (% tinggi)", "int",
     [("elearning.ui.lesson_view", "SUB_UP_POS")]),
    ("mini_sizes", "Video", "Mini player lebar (3 ukuran)", "ints",
     [("elearning.ui.mini_player", "SIZES")]),
    ("rewind_s", "Video", "Mundur mini player (dtk)", "int",
     [("elearning.ui.mini_player", "REWIND_S")]),
    ("badge_videos_5", "Badge", "Video: Lima Video", "int",
     [("elearning.achievements", "VIDEOS_5")]),
    ("badge_videos_15", "Badge", "Video: Lanjut Terus", "int",
     [("elearning.achievements", "VIDEOS_15")]),
    ("badge_uploads", "Badge", "Upload: Rajin Berkarya", "int",
     [("elearning.achievements", "UPLOADS_5")]),
    ("badge_days_3", "Badge", "Hari: Tiga Hari", "int", [("elearning.achievements", "DAYS_3")]),
    ("badge_days_7", "Badge", "Hari: Seminggu", "int", [("elearning.achievements", "DAYS_7")]),
    ("badge_days_30", "Badge", "Hari: Sebulan", "int", [("elearning.achievements", "DAYS_30")]),
    ("badge_sabar", "Badge", "Si Sabar diam (dtk)", "int",
     [("elearning.ui.badge_ui", "BadgeTracker.SABAR_S")]),
    ("secret_code", "Badge", "Kode rahasia", "str", [("elearning.config", "SECRET_CODE")]),
    ("special_days", "Badge", "Hari spesial (MM-DD, ...)", "list",
     [("elearning.config", "SPECIAL_DAYS")]),
    ("cert_assignment", "Sertifikat", "Min. assignment", "int",
     [("elearning.certificates", "ASSIGNMENT_MIN")]),
    ("cert_portfolio", "Sertifikat", "Min. portfolio", "int",
     [("elearning.certificates", "PORTFOLIO_MIN")]),
    ("cert_badges", "Sertifikat", "Min. badge", "int",
     [("elearning.certificates", "BADGES_MIN")]),
    ("schedule_hours", "Jadwal", "Jam tampil (mis. 8-18)", "hours",
     [("elearning.config", "SCHEDULE_HOURS"), ("elearning.ui.schedule_view", "HOURS")]),
    ("schedule_rows", "Jadwal", "Slot murid per sesi", "int",
     [("elearning.ui.schedule_view", "MAX_ROWS")]),
    ("present_min", "Jadwal", "Hadir min. (menit)", "int",
     [("elearning.analytics", "PRESENT_MIN")]),
    ("early_min", "Jadwal", "Boleh lebih awal (menit)", "int",
     [("elearning.analytics", "EARLY_MIN")]),
    ("inactive_days", "Analytics", "Perlu diperhatikan (hari)", "int",
     [("elearning.analytics", "INACTIVE_DAYS")]),
    ("note_words", "Murid", "Catatan video maks. kata", "int",
     [("elearning.progress", "NOTE_WORDS")]),
    ("student_drive", "Murid", "Drive murid (upload)", "str",
     [("elearning.config", "STUDENT_DRIVE")]),
    ("admin_refresh", "Admin", "Muat ulang otomatis (dtk)", "int",
     [("elearning.ui.admin_screen", "REFRESH_MS")]),
)
BY_KEY = {v[0]: v for v in VALUES}
_originals = {}      # kunci -> nilai asli dari kode (dicatat sebelum pertama kali ditimpa)


def _resolve(module, attr):
    obj = importlib.import_module(module)
    *path, name = attr.split(".")
    for p in path:
        obj = getattr(obj, p)
    return obj, name


def _read(key):
    _k, _g, _l, _t, targets = BY_KEY[key]
    obj, name = _resolve(*targets[0])
    return getattr(obj, name)


def to_text(key, value):
    """Nilai kode -> teks isian."""
    kind = BY_KEY[key][3]
    if kind == "secs":
        return f"{1 / value:g}" if value else "0"
    if kind == "hours":
        return f"{value[0]}-{value[1]}"
    if kind in ("list", "ints"):
        return ", ".join(str(v) for v in value)
    if key == "admin_refresh":
        return f"{value / 1000:g}"
    return f"{value:g}" if isinstance(value, float) else str(value)


def parse(key, text):
    """Teks isian -> nilai kode. ValueError (pesan siap tampil) kalau formatnya salah."""
    _k, _g, label, kind, _t = BY_KEY[key]
    t = str(text).strip()
    try:
        if kind == "int":
            v = int(float(t))
            if key == "admin_refresh":
                v = int(float(t) * 1000)
            if v < 0:
                raise ValueError
            return v
        if kind == "float":
            v = float(t.replace(",", "."))
            if v < 0:
                raise ValueError
            return v
        if kind == "secs":
            v = float(t.replace(",", "."))
            if v <= 0:
                raise ValueError
            return 1.0 / v
        if kind == "str":
            if not t:
                raise ValueError
            return t
        if kind == "list":
            return tuple(x.strip() for x in t.split(",") if x.strip())
        if kind == "ints":
            v = tuple(int(x) for x in t.replace(" ", "").split(",") if x)
            if len(v) != 3 or min(v) < 200:
                raise ValueError
            return v
        if kind == "hours":
            a, b = (int(x) for x in t.replace(" ", "").split("-"))
            if not 0 <= a < b <= 24:
                raise ValueError
            return (a, b)
    except (ValueError, TypeError):
        pass
    hint = {"int": "angka bulat", "float": "angka (mis. 0.5)", "secs": "angka > 0",
            "str": "tidak boleh kosong", "list": "pisah koma", "hours": "mis. 8-18",
            "ints": "3 angka pisah koma, min. 200"}.get(kind, "")
    raise ValueError(f"{label}: format salah ({hint}).")


def current_text(key):
    return to_text(key, _read(key))


def default_text(key):
    return to_text(key, _originals.get(key, _read(key)))


def apply_all():
    """Pasang semua nilai tersimpan ke modulnya (nilai asli dicatat dulu untuk Reset)."""
    saved = app_settings.get("values") or {}
    for key, (_k, _g, _l, _t, targets) in BY_KEY.items():
        try:
            if key not in _originals:
                _originals[key] = _read(key)
            value = parse(key, saved[key]) if key in saved else _originals[key]
            for module, attr in targets:
                obj, name = _resolve(module, attr)
                setattr(obj, name, value)
        except Exception as exc:
            C.log(f"Dev nilai {key} tidak dipasang: {exc!r}")
