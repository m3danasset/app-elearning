"""Membuka Blender 4.2 dari aplikasi (dipakai di sidebar akun trial).

- Mencari blender.exe di lokasi pemasangan yang umum (Program Files, AppData, Steam, PATH).
- Kalau tidak ketemu: pesan yang jelas + pilihan menunjuk sendiri blender.exe.
  Lokasi pilihan itu disimpan di data\\settings.json, jadi cukup sekali.
- Blender dijalankan terpisah dari aplikasi (menutup aplikasi tidak menutup Blender).
- Hanya satu Blender: kalau Blender sudah terbuka (dari tombol ini atau dibuka sendiri),
  klik tombol hanya memindahkan layar ke jendela Blender itu.
"""

import json
import os
import shutil
import subprocess
import sys

from elearning import config as C

# CATATAN: sengaja tidak memakai tkinter.messagebox / tkinter.filedialog / glob.
# Modul-modul itu tidak ikut terbungkus di dalam .exe (kode lain tidak memakainya),
# sehingga import-nya gagal dan aplikasi jatuh kembali ke kode lama.
# Dialog dipanggil langsung lewat perintah Tk bawaan (tk_messageBox, tk_getOpenFile).

VERSION = "4.2"
EXE = "blender.exe" if sys.platform == "win32" else "blender"
SETTINGS_FILE = os.path.join(C.DATA_DIR, "settings.json")
_KEY = "blender_path"

_GHOST_CLASS = "GHOST_WindowClass"   # nama kelas jendela Blender di Windows
_proc = [None]                       # proses Blender yang dibuka dari aplikasi ini


# --- penyimpanan lokasi ------------------------------------------------------
def _load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_setting(key, value):
    data = _load_settings()
    if value is None:
        data.pop(key, None)
    else:
        data[key] = value
    try:
        os.makedirs(C.DATA_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        C.log(f"Blender: gagal menyimpan settings.json: {exc!r}")


# --- pencarian ---------------------------------------------------------------
def _candidates():
    """Daftar kemungkinan lokasi blender.exe, urutan dari yang paling mungkin."""
    roots = []
    for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        if os.environ.get(var):
            roots.append(os.environ[var])
    if sys.platform == "win32":
        for drive in "CDEF":
            roots.append(drive + ":\\Program Files")
    local = os.environ.get("LocalAppData")
    if local:
        roots_bf = [os.path.join(local, "Programs")]
    else:
        roots_bf = []

    found = []
    for root in roots + roots_bf:
        base = os.path.join(root, "Blender Foundation")
        try:
            names = sorted((n for n in os.listdir(base) if n.startswith(f"Blender {VERSION}")),
                           reverse=True)
        except OSError:
            continue
        found += [os.path.join(base, n, EXE) for n in names]

    # Versi Steam
    for root in roots:
        found.append(os.path.join(root, "Steam", "steamapps", "common", "Blender", EXE))
    return found


def find_blender():
    """Lokasi blender.exe, atau None kalau tidak ketemu."""
    saved = _load_settings().get(_KEY)
    if saved and os.path.isfile(saved):
        return saved
    for path in _candidates():
        if os.path.isfile(path):
            return path
    return shutil.which("blender")


# --- satu Blender saja: pindah ke jendela yang sudah ada ------------------------
def _user32():
    import ctypes
    from ctypes import wintypes
    u = ctypes.WinDLL("user32", use_last_error=True)   # salinan sendiri, tidak mengubah ctypes.windll
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.IsIconic.argtypes = [wintypes.HWND]
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.BringWindowToTop.argtypes = [wintypes.HWND]
    u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetForegroundWindow.restype = wintypes.HWND
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    return u


def _find_blender_window():
    """Jendela utama Blender yang sedang terbuka (hwnd), atau None. Hanya Windows."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = _user32()
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def on_window(hwnd, _lparam):
            if u.IsWindowVisible(hwnd):
                cls = ctypes.create_unicode_buffer(64)
                u.GetClassNameW(hwnd, cls, 64)
                if cls.value == _GHOST_CLASS:
                    title = ctypes.create_unicode_buffer(256)
                    u.GetWindowTextW(hwnd, title, 256)
                    found.append((hwnd, title.value))
            return True

        u.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
        u.EnumWindows(on_window, 0)
        for hwnd, title in found:        # utamakan jendela yang berjudul "Blender..."
            if title.startswith("Blender"):
                return hwnd
        return found[0][0] if found else None
    except Exception as exc:
        C.log(f"Blender: gagal mencari jendela: {exc!r}")
        return None


_MIN_W, _MIN_H = 640, 400   # jendela Blender yang lebih kecil (mis. splash) bukan jendela utama


def blender_window_info():
    """Info jendela utama Blender, atau None kalau tidak ada (hanya Windows).

    {"hwnd", "x", "y", "w", "h", "minimized"}: x,y = pojok kiri-atas area isi jendela di layar,
    w,h = ukuran area isi. Kalau Blender di-minimize, hanya hwnd dan minimized=True yang berarti.
    Splash Blender (kecil) diabaikan.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = _user32()
        u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        u.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
        wins = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def on_window(hwnd, _lparam):
            if u.IsWindowVisible(hwnd):
                cls = ctypes.create_unicode_buffer(64)
                u.GetClassNameW(hwnd, cls, 64)
                if cls.value == _GHOST_CLASS:
                    wins.append(hwnd)
            return True

        u.EnumWindows(on_window, 0)

        best, best_area, iconic = None, 0, None
        for hwnd in wins:
            if u.IsIconic(hwnd):
                iconic = hwnd
                continue
            rc = wintypes.RECT()
            if not u.GetClientRect(hwnd, ctypes.byref(rc)):
                continue
            w, h = rc.right - rc.left, rc.bottom - rc.top
            if w < _MIN_W or h < _MIN_H or w * h <= best_area:
                continue
            pt = wintypes.POINT(0, 0)
            u.ClientToScreen(hwnd, ctypes.byref(pt))
            best, best_area = {"hwnd": hwnd, "x": pt.x, "y": pt.y, "w": w, "h": h,
                               "minimized": False}, w * h
        if best:
            return best
        if iconic:
            return {"hwnd": iconic, "minimized": True}
        return None
    except Exception as exc:
        C.log(f"Blender: gagal membaca jendela: {exc!r}")
        return None


def window_exists():
    """True kalau ada jendela Blender apa pun (termasuk splash / sedang dimuat)."""
    return _find_blender_window() is not None


def bring_to_front(hwnd):
    return _bring_to_front(hwnd)


def load_setting(key, default=None):
    return _load_settings().get(key, default)


def save_setting(key, value):
    _save_setting(key, value)


def _bring_to_front(hwnd):
    try:
        import ctypes
        u = _user32()
        if u.IsIconic(hwnd):
            u.ShowWindow(hwnd, 9)        # SW_RESTORE (hanya kalau sedang di-minimize)
        if u.SetForegroundWindow(hwnd):
            return True
        # Windows kadang menolak; pinjam fokus dari jendela yang sedang aktif
        fg = u.GetForegroundWindow()
        fg_tid = u.GetWindowThreadProcessId(fg, None) if fg else 0
        my_tid = ctypes.windll.kernel32.GetCurrentThreadId()
        if fg_tid and fg_tid != my_tid:
            u.AttachThreadInput(my_tid, fg_tid, True)
            try:
                u.BringWindowToTop(hwnd)
                ok = bool(u.SetForegroundWindow(hwnd))
            finally:
                u.AttachThreadInput(my_tid, fg_tid, False)
            return ok
        return False
    except Exception as exc:
        C.log(f"Blender: gagal memindahkan fokus: {exc!r}")
        return False


def _already_running():
    """True kalau Blender sudah terbuka (atau sedang dimuat) dan layar sudah dipindahkan."""
    hwnd = _find_blender_window()
    if hwnd:
        _bring_to_front(hwnd)
        return True
    # Dibuka dari tombol ini tapi jendelanya belum muncul (Blender masih memuat): jangan buka lagi
    proc = _proc[0]
    if proc is not None and proc.poll() is None:
        return True
    return False


# --- dialog (perintah Tk bawaan, tanpa modul tambahan) -------------------------
def _ask_yes_no(parent, title, message):
    try:
        return str(parent.tk.call("tk_messageBox", "-parent", str(parent), "-title", title,
                                  "-message", message, "-type", "yesno",
                                  "-icon", "question")) == "yes"
    except Exception as exc:
        C.log(f"Blender: dialog gagal: {exc!r}")
        return False


def _show_message(parent, icon, title, message):
    try:
        parent.tk.call("tk_messageBox", "-parent", str(parent), "-title", title,
                       "-message", message, "-type", "ok", "-icon", icon)
    except Exception as exc:
        C.log(f"Blender: dialog gagal: {exc!r}")


def _pick_file(parent):
    try:
        return str(parent.tk.call("tk_getOpenFile", "-parent", str(parent),
                                  "-title", f"Pilih {EXE}",
                                  "-filetypes", (("Blender", EXE), ("Semua file", "*"))))
    except Exception as exc:
        C.log(f"Blender: dialog pilih file gagal: {exc!r}")
        return ""


# --- tombol di sidebar ---------------------------------------------------------
def _ask_location(parent):
    ok = _ask_yes_no(
        parent, "Blender tidak ditemukan",
        f"Blender {VERSION} tidak ditemukan di komputer ini.\n\n"
        f"Pastikan Blender {VERSION} sudah terpasang. Kalau sudah, Anda bisa "
        f"menunjuk sendiri file {EXE}.\n\n"
        "Pilih lokasi Blender sekarang?")
    if not ok:
        return None
    path = _pick_file(parent)
    if not path:
        return None
    path = os.path.normpath(path)
    if os.path.basename(path).lower() != EXE:
        _show_message(
            parent, "warning", "File tidak sesuai",
            f"File yang dipilih bukan {EXE}. Coba lagi dan pilih {EXE} "
            "di folder pemasangan Blender.")
        return None
    _save_setting(_KEY, path)
    return path


def open_blender(parent):
    """Buka Blender, atau pindah ke Blender yang sudah terbuka. True kalau berhasil."""
    if _already_running():
        return True

    path = find_blender() or _ask_location(parent)
    if not path:
        return False

    try:
        kw = {}
        if sys.platform == "win32":
            kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
        _proc[0] = subprocess.Popen([path], cwd=os.path.dirname(path), close_fds=True, **kw)
    except OSError as exc:
        C.log(f"Blender: gagal menjalankan {path!r}: {exc!r}")
        if _load_settings().get(_KEY) == path:
            _save_setting(_KEY, None)   # lokasi tersimpan rusak: lupakan, tanya lagi nanti
        _show_message(
            parent, "error", "Blender tidak bisa dibuka",
            f"Blender tidak bisa dijalankan dari:\n{path}\n\n"
            "Coba klik tombolnya lagi untuk memilih lokasi yang benar.")
        return False

    C.log(f"Blender: dibuka dari {path!r}")
    return True
