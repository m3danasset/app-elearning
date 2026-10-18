"""Jendela web mengambang murid PB / IC / SK (Pinterest) lewat Google Chrome mode aplikasi.

- chrome.exe --app=<WEB_URL>: jendela polos tanpa kolom alamat / tab. Chrome asli (bukan
  browser tertanam) supaya login Google tidak diblokir.
- Profil terpisah per ID murid di %LOCALAPPDATA%\\M3DAN\\browser\\<ID>: akun Pinterest / Google
  murid lain tidak terlihat. Unduhan diarahkan ke config.STUDENT_DRIVE (Z:\\).
- Hanya situs di config.WEB_ALLOWED (--host-resolver-rules: situs lain gagal dimuat).
- Hanya terlihat di aplikasi utama: jendela Chrome dijadikan "milik" jendela aplikasi
  (selalu di atas aplikasi, tidak di atas program lain, tidak ada di taskbar), ditahan di dalam
  area aplikasi, disembunyikan saat aplikasi mengecil / Blender dibuka, ditutup saat logout.
- Prioritas BelowNormal, tanpa ekstensi. Pengawas posisi = after() tiap 300 ms (bukan animasi),
  semua panggilan Win32 dari thread utama.
"""

import json
import os
import subprocess
import sys

from elearning import config as C

WATCH_MS = 300
_state = {"proc": None, "sid": None, "app": None, "job": None, "hwnds": set(), "hidden": False}
_u32 = None


def available(student):
    """Murid PB / IC / SK. Bukan trial, dan bukan murid AI (semua kursus yang dibuka
    termasuk grup config.WEB_EXCLUDED_GROUPS)."""
    from elearning.courses import COURSES
    from elearning.trial import is_trial
    if not student or is_trial(student):
        return False
    group = {c["id"]: c.get("group") for c in COURSES}
    opened = [group.get(cid) for cid in student.get("courses", [])]
    return not (opened and all(g in C.WEB_EXCLUDED_GROUPS for g in opened))


def chrome_path():
    cands = [C.CHROME_PATH] if C.CHROME_PATH else []
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            cands.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    return next((p for p in cands if p and os.path.isfile(p)), None)


def profile_dir(student_id):
    base = os.environ.get("LOCALAPPDATA") or os.path.join(C.APP_DIR, "data")
    safe = "".join(ch for ch in str(student_id) if ch.isalnum()) or "murid"
    return os.path.join(base, "M3DAN", "browser", safe)


def _prepare_profile(folder):
    """Unduhan ke drive murid, tanpa simpan kata sandi (PC dipakai bergantian)."""
    path = os.path.join(folder, "Default", "Preferences")
    try:
        with open(path, encoding="utf-8") as f:
            prefs = json.load(f)
    except Exception:
        prefs = {}
    dl = C.STUDENT_DRIVE if os.path.isdir(C.STUDENT_DRIVE) else ""
    if dl:
        prefs.setdefault("download", {}).update(
            {"default_directory": dl, "prompt_for_download": True})
        prefs.setdefault("savefile", {})["default_directory"] = dl
    prefs["credentials_enable_service"] = False
    prefs.setdefault("profile", {})["password_manager_enabled"] = False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
    except OSError as exc:
        C.log(f"Web: profil Chrome tidak bisa diatur: {exc!r}")


def _rules():
    return "MAP * ~NOTFOUND, " + ", ".join(f"EXCLUDE {h}" for h in C.WEB_ALLOWED)


def _area(app):
    """Area isi aplikasi di layar (x, y, w, h)."""
    return app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()


def _message(app, text):
    try:
        app.tk.call("tk_messageBox", "-parent", str(app), "-icon", "info",
                    "-title", C.WEB_TITLE, "-message", text)
    except Exception:
        pass


def running():
    p = _state["proc"]
    return p is not None and p.poll() is None


def open_web(widget, student):
    """Ikon Pinterest diklik: buka, atau tampilkan lagi kalau sudah terbuka."""
    app = widget.winfo_toplevel()
    if not available(student):
        return False
    if running() and _state["sid"] == student["id"]:
        _show(True, focus=True)
        return True
    close()
    exe = chrome_path()
    if exe is None:
        _message(app, "Google Chrome belum terpasang di PC ini. Hubungi guru / admin.")
        return False
    folder = profile_dir(student["id"])
    _prepare_profile(folder)
    x, y, w, h = _area(app)
    ww, hh = max(420, int(w * 0.42)), max(360, h - 24)
    args = [exe, f"--app={C.WEB_URL}", f"--user-data-dir={folder}",
            f"--window-size={ww},{hh}", f"--window-position={x + w - ww - 12},{y + 12}",
            f"--host-resolver-rules={_rules()}", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions",
            "--disable-features=Translate,MediaRouter", "--disable-background-networking"]
    flags = 0x00004000 if sys.platform == "win32" else 0   # BELOW_NORMAL_PRIORITY_CLASS
    try:
        _state["proc"] = subprocess.Popen(args, creationflags=flags, close_fds=True)
    except OSError as exc:
        C.log(f"Web: Chrome gagal dibuka: {exc!r}")
        _message(app, "Chrome tidak bisa dibuka. Coba lagi.")
        return False
    _state.update(sid=student["id"], app=app, hwnds=set(), hidden=False)
    C.log(f"Web: {C.WEB_TITLE} dibuka untuk {student['id']}")
    _watch()
    return True


def close():
    """Tutup jendela web (logout, tutup aplikasi, ganti murid)."""
    app, job = _state["app"], _state["job"]
    if app is not None and job is not None:
        try:
            app.after_cancel(job)
        except Exception:
            pass
    p = _state["proc"]
    if p is not None and p.poll() is None:
        if sys.platform == "win32":   # seluruh pohon proses Chrome
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)],
                           capture_output=True, creationflags=0x08000000)
        else:
            p.terminate()
    _state.update(proc=None, sid=None, app=None, job=None, hwnds=set(), hidden=False)


# --- Win32: jendela milik aplikasi -------------------------------------------------------
def _user32():
    global _u32
    if _u32 is None:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)   # salinan sendiri (argtypes)
        H = wintypes.HWND
        u.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, H, wintypes.LPARAM),
                                  wintypes.LPARAM]
        u.GetWindowThreadProcessId.argtypes = [H, ctypes.POINTER(wintypes.DWORD)]
        u.GetClassNameW.argtypes = [H, wintypes.LPWSTR, ctypes.c_int]
        u.IsWindowVisible.argtypes = [H]
        u.IsWindow.argtypes = [H]
        u.IsIconic.argtypes = [H]
        u.GetWindowRect.argtypes = [H, ctypes.POINTER(wintypes.RECT)]
        u.SetWindowPos.argtypes = [H, H, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wintypes.UINT]
        u.ShowWindow.argtypes = [H, ctypes.c_int]
        u.SetForegroundWindow.argtypes = [H]
        u.GetWindowLongPtrW.argtypes = [H, ctypes.c_int]
        u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        u.SetWindowLongPtrW.argtypes = [H, ctypes.c_int, ctypes.c_ssize_t]
        u.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        _u32 = (u, ctypes, wintypes)
    return _u32


def _chrome_windows(pid):
    u, ctypes, wintypes = _user32()
    found = []
    buf = ctypes.create_unicode_buffer(64)

    def cb(hwnd, _lp):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(hwnd):
            u.GetClassNameW(hwnd, buf, 64)
            if buf.value == "Chrome_WidgetWin_1":
                found.append(int(hwnd))
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return found


def _adopt(hwnd, owner):
    """Jadikan milik aplikasi: di atas aplikasi saja, tidak muncul di taskbar."""
    u, _c, _w = _user32()
    u.SetWindowLongPtrW(hwnd, -8, owner)                     # GWL_HWNDPARENT = pemilik
    ex = u.GetWindowLongPtrW(hwnd, -20)                      # GWL_EXSTYLE
    u.SetWindowLongPtrW(hwnd, -20, ex & ~0x00040000)         # tanpa WS_EX_APPWINDOW
    u.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)


def _clamp(hwnd, app):
    """Tahan jendela di dalam area aplikasi (geser / kecilkan seperlunya)."""
    u, ctypes, wintypes = _user32()
    r = wintypes.RECT()
    if u.IsIconic(hwnd) or not u.GetWindowRect(hwnd, ctypes.byref(r)):
        return
    ax, ay, aw, ah = _area(app)
    w = min(r.right - r.left, aw)
    h = min(r.bottom - r.top, ah)
    x = min(max(r.left, ax), ax + aw - w)
    y = min(max(r.top, ay), ay + ah - h)
    if (x, y, w, h) != (r.left, r.top, r.right - r.left, r.bottom - r.top):
        u.SetWindowPos(hwnd, None, x, y, w, h, 0x0004 | 0x0010)   # NOZORDER | NOACTIVATE


def _show(visible, focus=False):
    if sys.platform != "win32":
        return
    u, _c, _w = _user32()
    for hwnd in list(_state["hwnds"]):
        if not u.IsWindow(hwnd):
            _state["hwnds"].discard(hwnd)
            continue
        if visible:
            u.ShowWindow(hwnd, 9 if u.IsIconic(hwnd) else 8)   # SW_RESTORE / SW_SHOWNA
            if focus:
                u.SetForegroundWindow(hwnd)
        else:
            u.ShowWindow(hwnd, 0)                                # SW_HIDE
    _state["hidden"] = not visible


def _watch():
    app = _state["app"]
    _state["job"] = None
    if app is None or not running():
        if app is not None:
            _state.update(proc=None, sid=None, app=None, hwnds=set())
        return
    try:
        if sys.platform == "win32":
            owner = int(app.wm_frame(), 16)
            visible = app.state() == "normal" and app.winfo_viewable()
            if not _state["hidden"]:
                for hwnd in _chrome_windows(_state["proc"].pid):   # termasuk popup login
                    if hwnd not in _state["hwnds"]:
                        _adopt(hwnd, owner)
                        _state["hwnds"].add(hwnd)
            if visible == _state["hidden"]:      # aplikasi mengecil / kembali
                _show(visible)
            if visible:
                for hwnd in list(_state["hwnds"]):
                    _clamp(hwnd, app)
        _state["job"] = app.after(WATCH_MS, _watch)
    except Exception as exc:
        C.log(f"Web: pengawas jendela berhenti: {exc!r}")
