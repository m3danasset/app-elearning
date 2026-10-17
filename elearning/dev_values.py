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
    # --- Login ---
    ("login_max_len", "Login", "Maks. karakter ID/PIN", "int",
     [("elearning.ui.login_screen", "MAX_LEN")]),
    ("login_logo_alpha", "Login", "Logo tampak (0-1)", "float",
     [("elearning.ui.login_screen", "LOGO_ALPHA")]),
    ("login_field_fill", "Login", "Gelap kolom ID (0-255)", "int",
     [("elearning.ui.login_screen", "FIELD_FILL")]),
    ("login_blink_ms", "Login", "Kedip kursor (ms)", "int",
     [("elearning.ui.login_screen", "BLINK_MS")]),
    ("login_video_opacity", "Login", "Video latar login (0-1)", "float",
     [("elearning.config", "LOGIN_VIDEO_OPACITY"), ("elearning.ui.login_bg", "OPACITY")]),
    ("login_video_fps", "Login", "Video latar login fps", "int",
     [("elearning.ui.login_bg", "FPS")]),
    # --- Carousel ---
    ("carousel_secs", "Carousel", "Detik per kartu", "secs",
     [("elearning.ui.carousel3d", "SPEED")]),
    ("carousel_bright", "Carousel", "Kecerahan kartu (0-1)", "float",
     [("elearning.ui.carousel3d", "BRIGHT")]),
    ("carousel_items", "Carousel", "Portfolio per baris", "int",
     [("elearning.ui.carousel3d", "MAX_ITEMS")]),
    ("carousel_aspect", "Carousel", "Lebar : tinggi kartu", "float",
     [("elearning.ui.carousel3d", "ASPECT")]),
    ("carousel_fade", "Carousel", "Fade tepi (0-0.5 layar)", "float",
     [("elearning.ui.carousel3d", "FADE")]),
    ("carousel_slice", "Carousel", "Irisan lengkung (px)", "int",
     [("elearning.ui.carousel3d", "SLICE_PX")]),
    # --- Beranda murid ---
    ("home_video_opacity", "Beranda", "Video latar beranda (0-1)", "float",
     [("elearning.config", "HOME_VIDEO_OPACITY"), ("elearning.ui.course_dock", "VIDEO_OPACITY")]),
    ("home_video_fps", "Beranda", "Video latar beranda fps", "int",
     [("elearning.ui.course_dock", "VIDEO_FPS")]),
    ("home_card_alpha", "Beranda", "Kartu kursus tampak (0-1)", "float",
     [("elearning.ui.course_dock", "CARD_ALPHA")]),
    ("home_scroll_ms", "Beranda", "Geser kartu (ms)", "int",
     [("elearning.ui.course_dock", "SCROLL_MS")]),
    ("showcase_secs", "Beranda", "Slideshow per gambar (dtk)", "int",
     [("elearning.config", "SHOWCASE_SECONDS")]),
    # --- Video pelajaran ---
    ("video_done_pct", "Video", "Selesai kalau sampai (%)", "int",
     [("elearning.progress", "DONE_PCT")]),
    ("video_save_every", "Video", "Simpan posisi tiap (dtk)", "int",
     [("elearning.progress", "SAVE_EVERY")]),
    ("video_ov_idle", "Video", "Sembunyikan tombol (dtk)", "float",
     [("elearning.ui.lesson_view", "OV_IDLE")]),
    ("video_fs_out", "Video", "Fullscreen: redup (ms)", "int",
     [("elearning.ui.lesson_view", "FS_FADE_OUT_MS")]),
    ("video_fs_in", "Video", "Fullscreen: muncul (ms)", "int",
     [("elearning.ui.lesson_view", "FS_FADE_IN_MS")]),
    ("intro_max", "Video", "Intro maks. (dtk)", "float",
     [("elearning.ui.lesson_view", "INTRO_MAX")]),
    ("intro_timeout", "Video", "Intro macet -> lewati (dtk)", "float",
     [("elearning.ui.lesson_view", "INTRO_TIMEOUT")]),
    ("sub_up_pos", "Video", "Subtitle naik (% tinggi)", "int",
     [("elearning.ui.lesson_view", "SUB_UP_POS")]),
    ("note_words", "Video", "Catatan video maks. kata", "int",
     [("elearning.progress", "NOTE_WORDS")]),
    # --- Mini player & ikon mengambang ---
    ("mini_sizes", "Mini player", "Lebar (3 ukuran)", "ints",
     [("elearning.ui.mini_player", "SIZES")]),
    ("rewind_s", "Mini player", "Mundur (dtk)", "int",
     [("elearning.ui.mini_player", "REWIND_S")]),
    ("float_idle_alpha", "Mini player", "Ikon samar (0-1)", "float",
     [("elearning.ui.floating", "IDLE_ALPHA")]),
    ("float_missing", "Mini player", "Ikon hilang (x 0.25 dtk)", "int",
     [("elearning.ui.floating", "MISSING_LIMIT")]),
    # --- Badge ---
    ("badge_watch_pct", "Badge", "Video dihitung (% ditonton)", "int",
     [("elearning.progress", "WATCH_PCT")]),
    ("badge_videos_1", "Badge", "Video: Video Pertama", "int",
     [("elearning.achievements", "VIDEOS_1")]),
    ("badge_videos_5", "Badge", "Video: Lima Video", "int",
     [("elearning.achievements", "VIDEOS_5")]),
    ("badge_videos_15", "Badge", "Video: Lanjut Terus", "int",
     [("elearning.achievements", "VIDEOS_15")]),
    ("badge_rewatch", "Badge", "Tonton ulang (kali)", "int",
     [("elearning.achievements", "REWATCH")]),
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
    # --- Sertifikat ---
    ("cert_assignment", "Sertifikat", "Min. assignment", "int",
     [("elearning.certificates", "ASSIGNMENT_MIN")]),
    ("cert_portfolio", "Sertifikat", "Min. portfolio", "int",
     [("elearning.certificates", "PORTFOLIO_MIN")]),
    ("cert_badges", "Sertifikat", "Min. badge", "int",
     [("elearning.certificates", "BADGES_MIN")]),
    # --- Jadwal & kehadiran ---
    ("schedule_hours", "Jadwal", "Jam tampil (mis. 8-18)", "hours",
     [("elearning.config", "SCHEDULE_HOURS"), ("elearning.ui.schedule_view", "HOURS")]),
    ("schedule_rows", "Jadwal", "Slot murid per sesi", "int",
     [("elearning.ui.schedule_view", "MAX_ROWS")]),
    ("present_min", "Jadwal", "Hadir min. (menit)", "int",
     [("elearning.analytics", "PRESENT_MIN")]),
    ("early_min", "Jadwal", "Boleh lebih awal (menit)", "int",
     [("elearning.analytics", "EARLY_MIN")]),
    # --- Analytics ---
    ("inactive_days", "Analytics", "Perlu diperhatikan (hari)", "int",
     [("elearning.analytics", "INACTIVE_DAYS")]),
    ("absent_rate", "Analytics", "Hadir rendah di bawah (0-1)", "float",
     [("elearning.analytics", "ABSENT_RATE")]),
    ("top_n", "Analytics", "Paling rajin (jumlah murid)", "int",
     [("elearning.analytics", "TOP_N")]),
    ("online_window", "Analytics", "Dianggap online (dtk)", "int",
     [("elearning.sessions", "ONLINE_WINDOW")]),
    # --- Search palette ---
    ("palette_dim", "Search", "Gelap latar (0-0.9)", "float",
     [("elearning.ui.search_palette", "DIM_ALPHA")]),
    ("palette_fade", "Search", "Lama muncul (dtk)", "float",
     [("elearning.ui.search_palette", "FADE_S")]),
    ("palette_per_kind", "Search", "Hasil per tipe", "int",
     [("elearning.ui.search_palette", "PER_KIND")]),
    ("recents_max", "Search", "Riwayat per akun", "int",
     [("elearning.recents", "MAX_PER_USER")]),
    # --- File & upload ---
    ("student_drive", "File", "Drive murid (upload)", "str",
     [("elearning.config", "STUDENT_DRIVE")]),
    ("blocked_drives", "File", "Drive diblok (B:, C:)", "list",
     [("elearning.config", "BLOCKED_DRIVES")]),
    ("upload_max_mb", "File", "Upload maks. per file (MB)", "int",
     [("elearning.portfolio", "MAX_MB")]),
    ("resource_limit", "File", "Resource maks. tampil", "int",
     [("elearning.ui.resource_list", "LIMIT")]),
    ("blender_version", "File", "Versi Blender", "str",
     [("elearning.blender_launcher", "VERSION")]),
    # --- Batas teks & akun ---
    ("student_name_max", "Batas", "Nama murid maks. huruf", "int",
     [("elearning.students", "NAME_MAX")]),
    ("teacher_name_max", "Batas", "Nama guru maks. huruf", "int",
     [("elearning.teachers", "NAME_MAX")]),
    ("pin_min", "Batas", "PIN guru min. karakter", "int",
     [("elearning.teachers", "PIN_MIN")]),
    ("quiz_question_max", "Batas", "Pertanyaan kuis maks.", "int",
     [("elearning.quizzes", "QUESTION_MAX")]),
    ("quiz_answer_max", "Batas", "Jawaban kuis maks.", "int",
     [("elearning.quizzes", "ANSWER_MAX")]),
    ("report_text_max", "Batas", "Catatan laporan maks.", "int",
     [("elearning.reports", "TEXT_MAX")]),
    ("report_keep", "Batas", "Laporan disimpan maks.", "int",
     [("elearning.reports", "MAX_KEEP")]),
    # --- Admin ---
    ("admin_refresh", "Admin", "Muat ulang otomatis (dtk)", "int",
     [("elearning.ui.admin_screen", "REFRESH_MS")]),
)
# batas aman (min, maks) per nilai; di luar batas -> Apply ditolak
LIMITS = {
    "login_max_len": (4, 30), "login_logo_alpha": (0.05, 1), "login_field_fill": (0, 255),
    "login_blink_ms": (200, 3000), "login_video_opacity": (0, 1), "login_video_fps": (1, 30),
    "carousel_bright": (0.1, 1), "carousel_items": (3, 30), "carousel_aspect": (0.3, 1.6),
    "carousel_fade": (0, 0.5), "carousel_slice": (16, 256),
    "home_video_opacity": (0, 1), "home_video_fps": (1, 30), "home_card_alpha": (0.3, 1),
    "home_scroll_ms": (50, 2000), "showcase_secs": (1, 120),
    "video_done_pct": (10, 100), "video_save_every": (1, 120), "video_ov_idle": (0.5, 30),
    "video_fs_out": (0, 1000), "video_fs_in": (0, 1000), "intro_max": (0.5, 30),
    "intro_timeout": (1, 60), "sub_up_pos": (30, 100), "note_words": (1, 500),
    "rewind_s": (1, 120), "float_idle_alpha": (0.1, 1), "float_missing": (2, 120),
    "badge_watch_pct": (10, 100), "badge_videos_1": (1, 100), "badge_videos_5": (1, 200),
    "badge_videos_15": (1, 500), "badge_rewatch": (2, 50), "badge_uploads": (1, 200),
    "badge_days_3": (1, 365), "badge_days_7": (1, 365), "badge_days_30": (1, 1000),
    "badge_sabar": (5, 3600), "cert_assignment": (0, 100), "cert_portfolio": (0, 100),
    "cert_badges": (0, 20), "schedule_rows": (5, 60), "present_min": (1, 240),
    "early_min": (0, 120), "inactive_days": (1, 365), "absent_rate": (0, 1), "top_n": (1, 50),
    "online_window": (30, 3600), "palette_dim": (0, 0.9), "palette_fade": (0.01, 1),
    "palette_per_kind": (1, 30), "recents_max": (1, 200), "upload_max_mb": (1, 20000),
    "resource_limit": (10, 5000), "student_name_max": (10, 100), "teacher_name_max": (10, 100),
    "pin_min": (1, 10), "quiz_question_max": (20, 5000), "quiz_answer_max": (5, 2000),
    "report_text_max": (100, 20000), "report_keep": (100, 100000),
    "admin_refresh": (5000, 3600000),
}
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
    """Teks isian -> nilai kode. ValueError (pesan siap tampil) kalau formatnya salah atau di
    luar batas LIMITS."""
    v = _parse(key, text)
    lim = LIMITS.get(key)
    if lim is not None and not lim[0] <= v <= lim[1]:
        lo, hi = lim
        if key == "admin_refresh":
            lo, hi = lo / 1000, hi / 1000
        raise ValueError(f"{BY_KEY[key][2]}: harus {lo:g} - {hi:g}.")
    return v


def _parse(key, text):
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
