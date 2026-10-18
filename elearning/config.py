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
# Jam yang tampil di jadwal (kalender, Sesi, export Excel): mulai 08.00, kolom terakhir 17.00-18.00
SCHEDULE_HOURS = (8, 18)
# Badge rahasia (easter egg). Ganti berkala supaya tetap jadi rahasia (murid saling bercerita).
SECRET_CODE = "m3dan"                 # "Kode Rahasia": ketik kata ini di kolom cari
SPECIAL_DAYS = ("01-01", "08-17")     # "Hari Spesial": bulan-tanggal (MM-DD) saat belajar
# Semua animasi UI (geser, fade, loading bar): maks. 30 fps. 34 ms (bukan 33) supaya tidak lewat 30.
UI_FPS = 30
UI_RADIUS_SCALE = 1.0   # pengali semua sudut membulat (Dev): 0 = siku, 2 = dua kali lebih bulat
UI_FRAME_MS = 34
# Thread kerja untuk render animasi (carousel, dll.): sedikit saja, supaya murid yang membuka
# file Blender berat tidak terganggu. CPU 4 thread (mis. Ryzen 3) = 1, selebihnya maks. 2.
# process_cpu_count: hanya core yang boleh dipakai proses ini (ikut affinity), bukan semua core PC.
WORKER_THREADS = 1 if (getattr(os, "process_cpu_count", os.cpu_count)() or 2) <= 4 else 2
# PC spek rendah (CPU <= 4 thread, mis. Ryzen 3 2200G + Vega 8): MODE RINGAN otomatis.
LOW_END_PC = WORKER_THREADS <= 1


def lite():
    """Mode ringan: tanpa animasi UI dan tanpa video latar (login, Dashboard), carousel login
    diam, pemutar pelajaran tanpa decode GPU. Otomatis di PC spek rendah (LOW_END_PC); di PC lain
    bisa dipaksa dengan mematikan fitur "animations" di jendela Dev. Mencegah beban GPU iGPU
    (AMD "driver timeout") saat Blender juga berjalan."""
    if LOW_END_PC:
        return True
    try:
        from elearning import app_settings
        return not app_settings.feature("animations")
    except Exception:
        return False


def _high_end():
    """PC spek tinggi: driver NVIDIA terpasang (nvapi64.dll) DAN CPU >= 12 thread. Hanya di PC
    ini carousel login boleh sampai 60 fps dengan 4 thread render (PC lain tetap maks. 30 fps,
    maks. 2 thread, supaya Blender murid tidak terganggu)."""
    try:
        cpus = getattr(os, "process_cpu_count", os.cpu_count)() or 2
        nv = os.path.isfile(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                         "System32", "nvapi64.dll"))
        return nv and cpus >= 12
    except Exception:
        return False


HIGH_END = _high_end()
CAROUSEL_WORKERS = 4 if HIGH_END else WORKER_THREADS
CAROUSEL_FPS_MAX = 60 if HIGH_END else 30


def _low_priority():
    """Proses aplikasi berprioritas 'di bawah normal': Windows mendahulukan Blender dkk.
    Aplikasi tetap lancar saat PC santai; hanya mengalah kalau CPU sedang penuh."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32")          # salinan sendiri: argtypes tidak mengganggu modul lain
        k32.GetCurrentProcess.restype = wintypes.HANDLE      # handle 64-bit (jangan terpotong)
        k32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)   # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:
        pass


_low_priority()
HOME_VIDEO_OPACITY = 0.22  # video latar halaman utama murid (assets\\video\\home): 0 = tak terlihat, 1 = penuh
# Video pelajaran, DI LUAR .exe juga: <folder .exe>\assets\lessons\<id kursus>\01.mp4, 02.mp4, ...
# File browser murid (upload Portfolio / Assignment): murid HANYA bisa membuka drive ini
# (penyimpanan lokal murid) dan flashdisk yang tercolok. Ganti kalau huruf drive berbeda.
STUDENT_DRIVE = "Z:\\"
# Drive yang TIDAK BOLEH dibuka / ditulisi murid lewat aplikasi (B: = sistem e-learning,
# C: = Windows).
BLOCKED_DRIVES = ("B:", "C:")
# Jendela web mengambang murid (ikon di sebelah "Buka Blender"), tidak untuk trial.
# Google Chrome mode aplikasi (tanpa kolom alamat), SATU profil per ID murid (login Google
# dipakai bersama semua situs). Hanya host di "allowed" situs milik murid itu yang bisa dibuka;
# login Google selalu diizinkan. Catatan: kalau PC memakai proxy, pembatasan situs tidak berlaku.
# ai: True = hanya murid AI (membuka kursus grup WEB_AI_GROUPS), False = hanya murid non-AI
# (PB / IC / SK, ada kursus di luar grup AI). Murid yang punya keduanya dapat semua.
# Login Google juga memasang cookie di domain negara (accounts.google.co.id) & YouTube
# (accounts.youtube.com); tanpa itu "Continue with Google" macet setelah popup terbuka.
WEB_LOGIN_HOSTS = ("accounts.google.com", "*.google.com", "*.gstatic.com", "*.googleapis.com",
                   "*.googleusercontent.com", "www.recaptcha.net", "accounts.google.*",
                   "accounts.youtube.com",
                   # FedCM ("Continue with Google" di Chrome) membaca
                   # https://google.com/.well-known/web-identity: domain TANPA subdomain
                   "google.com")
# Akun Google STUDIO dipakai bersama semua murid (satu profil Chrome "studio" per PC).
# Admin / dev login SEKALI per PC (Jendela Dev > Settings / Ctrl+K admin); murid tidak pernah
# melihat password. Kosong = profil per murid (login sendiri-sendiri, seperti dulu).
WEB_STUDIO_ACCOUNT = "m3dan.asset@gmail.com"
# Host Google yang boleh dibuka MURID saat akun studio dipakai: hanya yang perlu untuk login /
# "Continue with Google". Gmail, Drive, myaccount, Google Search (www.google.com) DIBLOK supaya
# murid tidak bisa membuka isi akun studio. (Setup login admin memakai WEB_LOGIN_HOSTS penuh.)
# www.google.com: FedCM membaca www.google.com/.well-known/web-identity (google.com
# dialihkan ke sana). Halaman Google Search / beranda Google ditutup lewat judul jendela
# (web_launcher._close_search).
WEB_STUDENT_GOOGLE_HOSTS = ("accounts.google.com", "accounts.google.*", "google.com",
                            "www.google.com",
                            "ssl.gstatic.com", "www.gstatic.com", "fonts.gstatic.com",
                            "*.googleapis.com", "lh3.googleusercontent.com",
                            "www.recaptcha.net", "accounts.youtube.com")
WEB_SITES = (
    {"key": "pinterest", "title": "Pinterest", "icon": "web_pin", "ai": False,
     "url": "https://id.pinterest.com/",
     "allowed": ("pinterest.com", "*.pinterest.com", "pinimg.com", "*.pinimg.com")},
    {"key": "gemini", "title": "Gemini", "icon": "web_gemini", "ai": True,
     "url": "https://gemini.google.com/", "allowed": ("gemini.google.com",)},
    {"key": "flow", "title": "Flow", "icon": "web_flow", "ai": True,
     "url": "https://flow.google.com/",
     "allowed": ("flow.google.com", "labs.google", "*.labs.google")},
)
WEB_AI_GROUPS = ("AI",)
# Batas waktu per murid PER HARI (menit) supaya tidak doomscrolling; habis -> jendela ditutup,
# baru bisa dibuka lagi besok. Situs yang tidak ada di sini: tanpa batas.
PINTEREST_LIMIT_MIN = 10      # Pinterest (diatur juga di jendela Dev > Nilai; 0 = tanpa batas)
WEB_RESET_MIN = 10            # jatah habis -> jeda N menit, lalu jatah penuh lagi (Dev)
WEB_DAILY_LIMIT_MIN = {}      # situs lain, mis. {"gemini": 30}
CHROME_PATH = ""   # kosong = cari otomatis (Program Files / AppData)
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
