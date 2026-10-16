"""Pengaturan umum: nama aplikasi, lokasi file, warna, dan font."""

import os
import sys
from datetime import datetime

APP_NAME = "Blender E-Learning"
APP_ID = "jack.blender.elearning"  # supaya ikon taskbar Windows benar


def app_dir():
    """Folder tempat aplikasi berada (di samping .exe, atau folder proyek)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


APP_DIR = app_dir()


def resource_path(*parts):
    """Lokasi file bawaan (assets). Bekerja saat dijalankan biasa maupun sebagai .exe.

    Saat jadi .exe: file di samping .exe (mis. assets\\logo.png) didahulukan, baru
    yang tertanam di dalam .exe. Jadi aset baru cukup ditaruh di folder assets.
    """
    if hasattr(sys, "_MEIPASS"):  # saat dijadikan .exe oleh PyInstaller
        beside_exe = os.path.join(APP_DIR, *parts)
        if os.path.exists(beside_exe):
            return beside_exe
        return os.path.join(sys._MEIPASS, *parts)
    return os.path.join(APP_DIR, *parts)


ICON_PATH = resource_path("assets", "icon.ico")


# Folder video latar login. Letaknya DI LUAR .exe supaya videonya bisa diganti
# kapan saja tanpa build ulang: <folder .exe>\assets\video\
VIDEO_DIR = os.path.join(APP_DIR, "assets", "video")
VIDEO_DIM = 0.45  # 1.0 = terang asli, makin kecil makin gelap (biar kartu login terbaca)
LOGIN_VIDEO_OPACITY = 0.22  # video latar layar login (assets\\video\\login): 0 = tak terlihat, 1 = penuh
# Carousel 3D layar login: frame per detik (maks. 30; turunkan ke 24 kalau PC terasa berat)
LOGIN_CAROUSEL_FPS = 30
HOME_VIDEO_OPACITY = 0.22  # video latar halaman utama murid (assets\\video\\home): 0 = tak terlihat, 1 = penuh
# Video pelajaran, DI LUAR .exe juga: <folder .exe>\assets\lessons\<id kursus>\01.mp4, 02.mp4, ...
LESSON_DIR = os.path.join(APP_DIR, "assets", "lessons")
LOG_PATH = os.path.join(APP_DIR, "app.log")

# Data yang diubah guru (kursus yang dibuka tiap murid). Disimpan DI LUAR .exe dan
# di luar folder app\, jadi aman saat update.bat dijalankan: <folder .exe>\data\
DATA_DIR = os.path.join(APP_DIR, "data")
STUDENTS_FILE = os.path.join(DATA_DIR, "students.json")
PHOTO_DIR = os.path.join(DATA_DIR, "photos")  # foto profil murid: <ID>.png
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")  # riwayat masuk/keluar murid
REPORTS_FILE = os.path.join(DATA_DIR, "reports.json")    # laporan kerja guru (dilihat admin)
TEACHERS_FILE = os.path.join(DATA_DIR, "teachers.json")  # akun guru (diatur admin di Panel Admin)


def log(msg):
    """Catat masalah ke app.log di samping aplikasi."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")
    except OSError:
        pass

# --- Tema warna -------------------------------------------------------------
# Abu-abu netral-hangat (gaya claude.ai mode gelap), aksen oranye tetap.
BG = "#1a1918"          # area isi (kanan)
CARD = "#262523"
CARD_HOVER = "#302f2c"
LOCKED = "#64625c"
BORDER = "#3a3935"
TEXT = "#f0eee6"
MUTED = "#a3a097"
ACCENT = "#ea7600"
ACCENT_HOVER = "#ff8a1a"
ERROR = "#ff6b6b"
ON = "#3fb68b"          # tombol ON (kursus dibuka)
TRACK_OFF = "#4a4945"   # tombol OFF (kursus dikunci)

# Sidebar kiri (sama untuk admin, guru, murid, trial)
SIDEBAR = "#1a1918"         # latar sidebar
SIDEBAR_HOVER = "#242321"   # baris saat kursor di atasnya
SIDEBAR_ACTIVE = "#2c2b28"  # baris yang sedang dipilih
SIDEBAR_LINE = "#2e2d2a"    # garis pemisah sidebar | isi
SEARCH_BG = "#1a1918"       # kolom cari

# Layar login & splash
SEG_ON = "#3a3935"         # tab / pilihan yang aktif (gaya claude.ai: netral, bukan oranye)
LOGIN_BG = BG               # latar login & splash = latar seluruh aplikasi
SERIF = "Georgia"           # huruf judul besar (ada di semua Windows)
LOGIN_HEADLINE = "Wujudkan karya 3D-mu"
LOGIN_TAGLINE = "Kelas Blender & AI M3DAN Studios, sesuai level kamu"
SHOWCASE_SECONDS = 6        # lama tiap gambar di slideshow portfolio (detik)
SHOWCASE_SHOW_NAMES = False # True = nama murid ikut tampil di slideshow login

FONT = "Segoe UI"
