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

from elearning.i18n import L
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


def is_foreground(tk_window_id):
    """True kalau jendela Tk (winfo_id) sedang jadi jendela aktif di depan; None kalau tidak bisa
    dicek (bukan Windows / gagal)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
        u.GetAncestor.restype = wintypes.HWND
        fg = u.GetForegroundWindow()
        if not fg:
            return False
        mine = u.GetAncestor(wintypes.HWND(tk_window_id), 2)   # GA_ROOT
        return bool(mine) and u.GetAncestor(fg, 2) == mine
    except Exception as exc:
        C.log(f"Blender: gagal memeriksa jendela aktif: {exc!r}")
        return None


def window_state(tk_window_id):
    """Keadaan jendela utama aplikasi menurut Windows (bukan menurut Tk, yang bisa terlambat tahu
    setelah Alt+Tab): "iconic" (di-minimize), "hidden", atau "visible". None kalau tidak bisa dicek."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        root = root_of(tk_window_id)
        if not root:
            return None
        u = _user32()
        h = wintypes.HWND(root)
        if u.IsIconic(h):
            return "iconic"
        return "visible" if u.IsWindowVisible(h) else "hidden"
    except Exception as exc:
        C.log(f"Blender: gagal membaca keadaan jendela aplikasi: {exc!r}")
        return None


def z_above(hwnd_a, hwnd_b):
    """True kalau jendela a berada di atas jendela b pada urutan tumpukan layar, False kalau di
    bawahnya. None kalau tidak bisa ditentukan."""
    if sys.platform != "win32" or not hwnd_a or not hwnd_b:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.GetTopWindow.argtypes = [wintypes.HWND]
        u.GetTopWindow.restype = wintypes.HWND
        u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        u.GetWindow.restype = wintypes.HWND
        a, b = int(hwnd_a), int(hwnd_b)
        h = u.GetTopWindow(None)
        for _ in range(4000):
            if not h:
                return None
            hv = int(h)
            if hv == a:
                return True
            if hv == b:
                return False
            h = u.GetWindow(h, 2)                  # GW_HWNDNEXT
        return None
    except Exception as exc:
        C.log(f"Blender: gagal membaca urutan jendela: {exc!r}")
        return None


def blender_covered(hwnd, own_root=None):
    """True kalau ada jendela biasa lain (aplikasi e-learning, browser, ...) di atas jendela Blender
    pada urutan tumpukan layar dan menutupi sebagian besar Blender; False kalau Blender paling
    depan. None kalau tidak bisa dicek.

    Dipakai karena setelah Alt+Tab, jendela yang tampil di depan belum tentu langsung menjadi
    "jendela aktif" menurut Windows (baru setelah diklik), sedangkan urutan tumpukan langsung benar.
    Jendela ikon/mini player sendiri, jendela alat (tool window), jendela tersembunyi / di-minimize
    dan jendela "hantu" (cloaked) diabaikan."""
    if sys.platform != "win32" or not hwnd:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = _user32()
        u.GetTopWindow.argtypes = [wintypes.HWND]
        u.GetTopWindow.restype = wintypes.HWND
        u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        u.GetWindow.restype = wintypes.HWND
        u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        try:
            dwm = ctypes.WinDLL("dwmapi")
            dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p,
                                                  wintypes.DWORD]
        except Exception:
            dwm = None
        target = int(hwnd)
        br = wintypes.RECT()
        if not u.GetWindowRect(wintypes.HWND(target), ctypes.byref(br)):
            return None
        barea = max(1, (br.right - br.left) * (br.bottom - br.top))
        mypid = os.getpid()
        pid = wintypes.DWORD()
        rect = wintypes.RECT()
        h = u.GetTopWindow(None)
        for _ in range(4000):
            if not h:
                return None
            hv = int(h)
            if hv == target:
                return False
            h = u.GetWindow(h, 2)                       # GW_HWNDNEXT
            hw = wintypes.HWND(hv)
            if not u.IsWindowVisible(hw) or u.IsIconic(hw):
                continue
            ex = u.GetWindowLongW(hw, -20) & 0xFFFFFFFF
            u.GetWindowThreadProcessId(hw, ctypes.byref(pid))
            if pid.value == mypid and (own_root is None or hv != int(own_root)):
                continue                                # ikon / mini player / tombol sendiri
            if ex & 0x00000080 or ex & 0x08000000:      # TOOLWINDOW / NOACTIVATE
                continue
            if dwm is not None:
                cloaked = wintypes.DWORD(0)
                if dwm.DwmGetWindowAttribute(hw, 14, ctypes.byref(cloaked), 4) == 0 and cloaked.value:
                    continue
            if not u.GetWindowRect(hw, ctypes.byref(rect)):
                continue
            iw = min(rect.right, br.right) - max(rect.left, br.left)
            ih = min(rect.bottom, br.bottom) - max(rect.top, br.top)
            if iw > 0 and ih > 0 and iw * ih >= 0.3 * barea:
                return True
        return None
    except Exception as exc:
        C.log(f"Blender: gagal memeriksa jendela yang menutupi Blender: {exc!r}")
        return None


def foreground_is_blender():
    """True kalau jendela yang sedang aktif adalah jendela Blender. None kalau tidak bisa dicek."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = _user32()
        u.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
        u.GetAncestor.restype = wintypes.HWND
        fg = u.GetForegroundWindow()
        if not fg:
            return False
        root = u.GetAncestor(fg, 2) or fg                    # GA_ROOT
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(root, cls, 64)
        return cls.value == _GHOST_CLASS
    except Exception as exc:
        C.log(f"Blender: gagal memeriksa apakah Blender yang aktif: {exc!r}")
        return None


def left_button_down():
    """True kalau tombol kiri mouse sedang ditekan (di mana pun). None kalau tidak bisa dicek."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.GetAsyncKeyState.argtypes = [ctypes.c_int]
        u.GetAsyncKeyState.restype = ctypes.c_short
        return bool(u.GetAsyncKeyState(0x01) & 0x8000)      # VK_LBUTTON
    except Exception:
        return None


def root_at_point(x, y):
    """Jendela induk paling atas (hwnd, angka) tepat di bawah titik layar (x, y); 0 kalau tidak ada."""
    if sys.platform != "win32":
        return 0
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.WindowFromPoint.argtypes = [wintypes.POINT]
        u.WindowFromPoint.restype = wintypes.HWND
        u.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
        u.GetAncestor.restype = wintypes.HWND
        hwnd = u.WindowFromPoint(wintypes.POINT(int(x), int(y)))
        if not hwnd:
            return 0
        return int(u.GetAncestor(hwnd, 2) or hwnd)
    except Exception:
        return 0


def root_of(tk_window_id):
    """Jendela induk paling atas (hwnd, angka) dari widget Tk (winfo_id)."""
    if sys.platform != "win32":
        return 0
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
        u.GetAncestor.restype = wintypes.HWND
        h = wintypes.HWND(tk_window_id)
        return int(u.GetAncestor(h, 2) or 0)
    except Exception:
        return 0


def foreground_is_ours():
    """True kalau jendela yang sedang aktif milik proses ini (aplikasi, ikon, atau mini player).
    None kalau tidak bisa dicek."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        fg = u.GetForegroundWindow()
        if not fg:
            return False
        pid = wintypes.DWORD(0)
        u.GetWindowThreadProcessId(fg, ctypes.byref(pid))
        return pid.value == os.getpid()
    except Exception as exc:
        C.log(f"Blender: gagal memeriksa pemilik jendela aktif: {exc!r}")
        return None


def monitor_work_area(hwnd):
    """Area kerja monitor tempat jendela hwnd berada: (kiri, atas, kanan, bawah), di luar taskbar.
    None kalau tidak bisa dibaca (bukan Windows / gagal)."""
    if sys.platform != "win32" or not hwnd:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        u = ctypes.WinDLL("user32", use_last_error=True)
        u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        u.MonitorFromWindow.restype = wintypes.HANDLE
        u.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
        hmon = u.MonitorFromWindow(hwnd, 2)          # MONITOR_DEFAULTTONEAREST
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not hmon or not u.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return None
        r = mi.rcWork
        return (r.left, r.top, r.right, r.bottom)
    except Exception as exc:
        C.log(f"Blender: gagal membaca area monitor: {exc!r}")
        return None


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
        parent, L("Blender tidak ditemukan", "Blender not found"),
        L(f"Blender {VERSION} tidak ditemukan di komputer ini.\n\n"
          f"Pastikan Blender {VERSION} sudah terpasang. Kalau sudah, Anda bisa "
          f"menunjuk sendiri file {EXE}.\n\n"
          "Pilih lokasi Blender sekarang?",
          f"Blender {VERSION} was not found on this computer.\n\n"
          f"Make sure Blender {VERSION} is installed. If it is, you can point to "
          f"{EXE} yourself.\n\n"
          "Choose the Blender location now?"))
    if not ok:
        return None
    path = _pick_file(parent)
    if not path:
        return None
    path = os.path.normpath(path)
    if os.path.basename(path).lower() != EXE:
        _show_message(
            parent, "warning", L("File tidak sesuai", "Wrong file"),
            L(f"File yang dipilih bukan {EXE}. Coba lagi dan pilih {EXE} "
              "di folder pemasangan Blender.",
              f"The chosen file is not {EXE}. Try again and pick {EXE} "
              "in the Blender install folder."))
        return None
    _save_setting(_KEY, path)
    return path


def blender_running():
    """True kalau Blender sudah terbuka / sedang dimuat (tanpa memindahkan jendela)."""
    if _find_blender_window():
        return True
    proc = _proc[0]
    return proc is not None and proc.poll() is None


REFERENCE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "blender_scripts", "reference_view.py")


def open_with_reference(parent, image_paths):
    """Buka Blender BARU dengan gambar referensi di Image Editor kiri (tanpa addon).
    Kalau Blender sudah terbuka: minta murid menyimpan & menutupnya dulu. True = dibuka."""
    paths = [p for p in image_paths if os.path.isfile(p)]
    if not paths:
        _show_message(parent, "error", L("Gambar tidak ditemukan", "Image not found"),
                      L("Gambar referensi tidak bisa dibuka. Hubungi guru.",
                        "The reference image could not be opened. Ask your teacher."))
        return False
    if blender_running():
        _show_message(
            parent, "info", L("Tutup Blender dulu", "Close Blender first"),
            L("Blender sedang terbuka.\n\nSimpan pekerjaanmu (Ctrl+S), tutup Blender, lalu "
              "klik tombol ini lagi. Blender akan dibuka dengan gambar referensi di sebelah "
              "kiri.",
              "Blender is already open.\n\nSave your work (Ctrl+S), close Blender, then click "
              "this button again. Blender will open with the reference image on the left."))
        return False
    if not os.path.isfile(REFERENCE_SCRIPT):
        C.log(f"Blender: skrip referensi tidak ada: {REFERENCE_SCRIPT!r}")
        return open_blender(parent)
    return open_blender(parent, ["--python", REFERENCE_SCRIPT, "--"] + paths)


def open_blender(parent, args=()):
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
        _proc[0] = subprocess.Popen([path] + list(args), cwd=os.path.dirname(path), close_fds=True, **kw)
    except OSError as exc:
        C.log(f"Blender: gagal menjalankan {path!r}: {exc!r}")
        if _load_settings().get(_KEY) == path:
            _save_setting(_KEY, None)   # lokasi tersimpan rusak: lupakan, tanya lagi nanti
        _show_message(
            parent, "error", L("Blender tidak bisa dibuka", "Blender could not be opened"),
            L(f"Blender tidak bisa dijalankan dari:\n{path}\n\n"
              "Coba klik tombolnya lagi untuk memilih lokasi yang benar.",
              f"Blender could not be started from:\n{path}\n\n"
              "Click the button again to choose the right location."))
        return False

    C.log(f"Blender: dibuka dari {path!r}")
    return True
