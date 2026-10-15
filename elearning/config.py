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
BG = "#14171f"
CARD = "#1d212c"
CARD_HOVER = "#262b39"
LOCKED = "#5a6072"
BORDER = "#2a2f3d"
TEXT = "#e8eaf0"
MUTED = "#8b91a3"
ACCENT = "#ea7600"
ACCENT_HOVER = "#ff8a1a"
ERROR = "#ff6b6b"
ON = "#3fb68b"          # tombol ON (kursus dibuka)
TRACK_OFF = "#3a3f4d"   # tombol OFF (kursus dikunci)

FONT = "Segoe UI"
