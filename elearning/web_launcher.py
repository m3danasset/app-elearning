"""Jendela web mengambang murid lewat Google Chrome mode aplikasi (config.WEB_SITES):
Pinterest untuk murid PB / IC / SK, Gemini + Flow untuk murid AI. Bukan trial.

- chrome.exe --app=<url>: jendela polos tanpa kolom alamat / tab. Chrome asli (bukan
  browser tertanam) supaya login Google tidak diblokir.
- SATU profil per ID murid di %LOCALAPPDATA%\\M3DAN\\browser\\<ID> (satu proses Chrome; tiap
  situs = jendela sendiri, login Google dipakai bersama). Akun murid lain tidak terlihat.
  Unduhan diarahkan ke config.STUDENT_DRIVE (Z:\\).
- Hanya host situs milik murid + login Google (--host-resolver-rules: lainnya gagal dimuat).
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
import time

from elearning import config as C

WATCH_MS = 300
PENDING_S = 10.0   # jendela situs yang tidak muncul dalam 10 dtk dianggap gagal
# hwnds: semua jendela Chrome milik aplikasi; site_hwnd: kunci situs -> jendela utamanya;
# pending: situs yang baru diluncurkan, menunggu jendelanya muncul
_state = {"proc": None, "sid": None, "app": None, "job": None, "hwnds": set(), "hidden": False,
          "site_hwnd": {}, "pending": []}
_u32 = None


def sites_for(student):
    """Situs yang boleh dibuka murid ini (urut config.WEB_SITES)."""
    from elearning.courses import COURSES, ai_only
    from elearning.trial import is_trial
    if not student or is_trial(student):
        return []
    group = {c["id"]: c.get("group") for c in COURSES}
    ai = any(group.get(cid) in C.WEB_AI_GROUPS for cid in student.get("courses", []))
    other = not ai_only(student)
    return [s for s in C.WEB_SITES if (ai if s["ai"] else other)]


def available(student):
    return bool(sites_for(student))


def chrome_path():
    cands = [C.CHROME_PATH] if C.CHROME_PATH else []
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            cands.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    return next((p for p in cands if p and os.path.isfile(p)), None)


def shared():
    """True: akun Google studio tersedia (profil "studio" = Pinterest akun guru)."""
    return bool(getattr(C, "WEB_STUDIO_ACCOUNT", ""))


def profiles_for(student):
    """Profil Chrome untuk Pinterest: [(kunci, boleh?)]. "studio" = akun guru (semua murid);
    "own" = akun Google murid sendiri (hanya program WEB_OWN_PROFILE_PROGRAMS, bukan SUPERKIDS)."""
    out = []
    if shared():
        out.append(("studio", True))
    own_ok = bool(student) and student.get("program") in getattr(
        C, "WEB_OWN_PROFILE_PROGRAMS", ("adult",))
    out.append(("own", own_ok))
    return out


def profile_dir(student_id, profile="own"):
    base = os.environ.get("LOCALAPPDATA") or os.path.join(C.APP_DIR, "data")
    safe = "studio" if profile == "studio" else \
        ("".join(ch for ch in str(student_id) if ch.isalnum()) or "murid")
    return os.path.join(base, "M3DAN", "browser", safe)


def chrome_logo(size):
    """Logo Chrome ASLI dari instalasi Chrome di PC ini (VisualElements\\Logo.png), dipotong
    pas & diperkecil halus (PIL RGBA) atau None."""
    exe = chrome_path()
    if not exe:
        return None
    try:
        from PIL import Image
        root = os.path.dirname(exe)
        cands = [os.path.join(root, "VisualElements", "Logo.png")]
        for d in sorted(os.listdir(root), reverse=True):        # folder versi, mis. 155.0...
            cands.append(os.path.join(root, d, "VisualElements", "Logo.png"))
        path = next((p for p in cands if os.path.isfile(p)), None)
        if path is None:
            return None
        with Image.open(path) as im:
            img = im.convert("RGBA")
        box = img.getchannel("A").getbbox()
        if box:
            img = img.crop(box)
        return img.resize((size, size), Image.LANCZOS)
    except Exception as exc:
        C.log(f"Web: logo Chrome tidak terbaca: {exc!r}")
        return None


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


def _rules(sites, setup=False, profile="own"):
    """Aturan host Chrome: selain host di sini gagal dimuat. Profil studio (akun guru) untuk
    murid: host Google dipersempit (tanpa Gmail / Drive / myaccount / Search); profil murid
    sendiri & setup login admin: penuh."""
    narrow = profile == "studio" and not setup
    hosts = list(getattr(C, "WEB_STUDENT_GOOGLE_HOSTS", C.WEB_LOGIN_HOSTS) if narrow
                 else C.WEB_LOGIN_HOSTS)
    for s in sites:
        hosts += [h for h in s["allowed"] if h not in hosts]
    return "MAP * ~NOTFOUND, " + ", ".join(f"EXCLUDE {h}" for h in hosts)


def _area(app):
    """Area isi aplikasi di layar (x, y, w, h)."""
    return app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()


def _message(app, title, text):
    try:
        app.tk.call("tk_messageBox", "-parent", str(app), "-icon", "info",
                    "-title", title, "-message", text)
    except Exception:
        pass


def running():
    p = _state["proc"]
    return p is not None and p.poll() is None


def open_web(widget, student, key, profile="own"):
    """Situs dibuka: jendelanya, atau tampilkan lagi kalau sudah terbuka. profile: "studio"
    (Pinterest akun guru) / "own" (akun Google murid). Satu proses Chrome sekaligus: ganti
    murid / ganti profil -> yang lama ditutup."""
    from elearning.i18n import L
    app = widget.winfo_toplevel()
    sites = sites_for(student)
    site = next((s for s in sites if s["key"] == key), None)
    if site is None:
        return False
    ok = dict(profiles_for(student))
    if profile == "studio" and not ok.get("studio"):
        profile = "own"
    if profile == "own" and not ok.get("own") and key == "pinterest":
        return False                         # SUPERKIDS: hanya akun guru
    if running() and (_state["sid"] != student["id"] or _state.get("profile") != profile):
        close()
    left = remaining(student["id"], key)
    if left is not None and left <= 0:
        lim = _limit(key, student["id"])
        r = reset_at(student["id"], key)
        _message(app, site["title"], L(
            f"{site['title']} tidak tersedia untukmu. Tanya guru." if lim == 0 else
            f"Batas {site['title']} habis. Bisa dipakai lagi pukul {r}.",
            f"{site['title']} is not available for you. Ask your teacher." if lim == 0 else
            f"You've hit your {site['title']} limit ({lim} min). It resets at {r}."))
        return False
    if running() and _alive(_state["site_hwnd"].get(key)):
        _show(True, focus=_state["site_hwnd"][key])
        return True
    if any(k == key and time.monotonic() - t < PENDING_S for k, t in _state["pending"]):
        return True     # masih menunggu jendelanya muncul (klik dobel)
    exe = chrome_path()
    if exe is None:
        _message(app, site["title"], L("Google Chrome belum terpasang di PC ini. Hubungi guru / admin.",
                                       "Google Chrome is not installed on this PC. Please ask your teacher."))
        return False
    folder = profile_dir(student["id"], profile)
    x, y, w, h = _area(app)
    ww, hh = max(420, int(w * 0.42)), max(360, h - 24)
    n = len(_state["site_hwnd"]) if running() else 0          # jendela berikutnya sedikit bergeser
    args = [exe, f"--app={site['url']}", f"--user-data-dir={folder}",
            f"--window-size={ww},{hh}",
            f"--window-position={x + w - ww - 12 - 24 * n},{y + 12 + 24 * n}"]
    first = not running()
    if first:   # proses browser baru: aturan situs & opsi hanya berlaku di peluncuran pertama
        if profile == "studio":   # profil studio: tutup sisa Chrome lain (mis. setup admin)
            _kill_profile(folder)
        _prepare_profile(folder)
        args += [f"--host-resolver-rules={_rules(sites, profile=profile)}", "--no-first-run",
                 "--no-default-browser-check", "--disable-extensions",
                 "--disable-features=Translate,MediaRouter", "--disable-background-networking"]
        if C.lite():   # mode ringan (iGPU + Blender): Chrome tidak memakai GPU
            args += ["--disable-gpu", "--disable-smooth-scrolling"]
    flags = 0x00004000 if sys.platform == "win32" else 0   # BELOW_NORMAL_PRIORITY_CLASS
    try:
        proc = subprocess.Popen(args, creationflags=flags, close_fds=True)
    except OSError as exc:
        C.log(f"Web: Chrome gagal dibuka: {exc!r}")
        _message(app, site["title"], L("Chrome tidak bisa dibuka. Coba lagi.",
                                       "Chrome could not be opened. Please try again."))
        return False
    if first:      # peluncuran berikutnya diteruskan ke proses ini lalu langsung selesai
        _state.update(proc=proc, sid=student["id"], app=app, hwnds=set(), hidden=False,
                      site_hwnd={}, pending=[], profile=profile, extra={})
    _state["pending"].append((key, time.monotonic()))
    C.log(f"Web: {site['title']} dibuka untuk {student['id']}")
    if _state["job"] is None:
        _watch()
    return True


EXTRA_GRACE_S = 4.0     # jendela tambahan tanpa judul login Google -> ditutup setelah ini
LOGIN_WORDS = ("google", "sign in", "masuk", "login", "log in", "akun", "account",
               "youtube", "pilih akun", "choose an account")


def _title(hwnd):
    u, ctypes, _w = _user32()
    buf = ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def _close_extra(now):
    """Murid hanya boleh SATU jendela per situs (anti spam): jendela yang dibuka dari dalam
    situs (tautan / tab baru, mis. Pinterest) langsung ditutup; popup login Google boleh."""
    extra = _state.setdefault("extra", {})
    if not extra:
        return
    u, _c, _w = _user32()
    for hwnd, t in list(extra.items()):
        if not u.IsWindow(hwnd):
            extra.pop(hwnd, None)
            continue
        title = _title(hwnd).lower()
        if any(w in title for w in LOGIN_WORDS):
            extra.pop(hwnd, None)            # popup login: dibiarkan (tetap milik aplikasi)
            continue
        # tanpa judul / masih memuat (popup login baru dibuka, internet lambat): tunggu dulu,
        # jangan pernah ditutup; yang ditutup hanya halaman situs itu sendiri (judul berisi
        # nama situs, mis. "Pinterest") atau jendela berjudul lain setelah EXTRA_GRACE_S
        blank = not title or title in ("about:blank", "untitled") or title.startswith("http")
        if blank:
            continue
        if any(s["title"].lower() in title for s in C.WEB_SITES) or now - t > EXTRA_GRACE_S:
            u.PostMessageW(hwnd, 0x0010, 0, 0)             # WM_CLOSE
            extra.pop(hwnd, None)
            _state["hwnds"].discard(hwnd)
            C.log(f"Web: jendela tambahan ditutup ({title[:40]!r}) - hanya 1 jendela per situs")


SEARCH_TITLES = ("google search", "penelusuran google", "telusuri dengan google")


def _close_search():
    """Akun studio dipakai murid: halaman Google Search / beranda Google tidak boleh dibuka
    (www.google.com diizinkan hanya untuk login FedCM) -> jendela itu ditutup."""
    u, _c, _w = _user32()
    for hwnd in list(_state["hwnds"]):
        if not u.IsWindow(hwnd):
            continue
        t = _title(hwnd).strip().lower()
        if t == "google" or any(w in t for w in SEARCH_TITLES):
            u.PostMessageW(hwnd, 0x0010, 0, 0)             # WM_CLOSE
            _state["hwnds"].discard(hwnd)
            for k, h in list(_state["site_hwnd"].items()):
                if h == hwnd:
                    _state["site_hwnd"].pop(k, None)
            C.log(f"Web: halaman Google ditutup ({t[:40]!r}) - akun studio")


def studio_login(widget):
    """Admin / dev: buka Chrome profil studio (jendela biasa) untuk login akun Google studio
    SEKALI di PC ini, lalu "Continue with Google" di Pinterest. Password diketik sendiri oleh
    admin; tidak disimpan aplikasi (cookie login disimpan Chrome di profil studio)."""
    from urllib.parse import quote
    from elearning.i18n import L
    app = widget.winfo_toplevel()
    exe = chrome_path()
    if exe is None:
        _message(app, "Akun studio", L("Google Chrome belum terpasang di PC ini.",
                                       "Google Chrome is not installed on this PC."))
        return False
    close()                                   # jendela murid (profil sama) ditutup dulu
    folder = profile_dir("", "studio")
    _kill_profile(folder)
    _prepare_profile(folder)
    acc = getattr(C, "WEB_STUDIO_ACCOUNT", "")
    url = ("https://accounts.google.com/ServiceLogin?continue="
           + quote("https://id.pinterest.com/login/", safe="") + "&Email=" + quote(acc))
    args = [exe, f"--app={url}", f"--user-data-dir={folder}",
            f"--host-resolver-rules={_rules(C.WEB_SITES, setup=True)}", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions"]
    try:
        subprocess.Popen(args, close_fds=True)
    except OSError as exc:
        C.log(f"Web: login akun studio gagal dibuka: {exc!r}")
        return False
    C.log("Web: jendela login akun studio dibuka")
    _message(app, "Akun studio", L(
        f"Login dengan {acc} di jendela Chrome, lalu di Pinterest pilih \"Continue with "
        "Google\". Setelah masuk, tutup jendela itu. Cukup sekali di PC ini; semua murid "
        "langsung memakai akun ini.",
        f"Sign in with {acc} in the Chrome window, then choose \"Continue with Google\" "
        "on Pinterest. Close that window when done. Once per PC."))
    return True


def _kill_profile(folder):
    """Chrome lain yang memakai profil ini (mis. jendela setup admin yang aksesnya lebar)
    ditutup: aturan host hanya berlaku saat proses Chrome pertama diluncurkan."""
    if sys.platform != "win32" or not os.path.isdir(folder):
        return
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object { "
          "$_.CommandLine -and $_.CommandLine.ToLower().Contains('" + folder.lower().replace("'", "''")
          + "') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
          "-ErrorAction SilentlyContinue }")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, creationflags=0x08000000, timeout=15)
    except Exception as exc:
        C.log(f"Web: Chrome profil lama tidak bisa ditutup: {exc!r}")


def close():
    """Tutup jendela web (logout, tutup aplikasi, ganti murid)."""
    if _usage["dirty"]:
        _save_usage()
    _usage["last"] = None
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
    _state.update(proc=None, sid=None, app=None, job=None, hwnds=set(), hidden=False,
                  site_hwnd={}, pending=[], extra={}, profile=None)


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
        u.GetWindowTextW.argtypes = [H, wintypes.LPWSTR, ctypes.c_int]
        u.IsWindowVisible.argtypes = [H]
        u.IsWindow.argtypes = [H]
        u.IsIconic.argtypes = [H]
        u.GetWindowRect.argtypes = [H, ctypes.POINTER(wintypes.RECT)]
        u.SetWindowPos.argtypes = [H, H, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wintypes.UINT]
        u.ShowWindow.argtypes = [H, ctypes.c_int]
        u.SetForegroundWindow.argtypes = [H]
        u.PostMessageW.argtypes = [H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
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


def _alive(hwnd):
    return bool(hwnd) and sys.platform == "win32" and bool(_user32()[0].IsWindow(hwnd))


def _show(visible, focus=None):
    """Tampilkan / sembunyikan semua jendela web; focus = jendela yang dibawa ke depan."""
    if sys.platform != "win32":
        return
    u, _c, _w = _user32()
    for hwnd in list(_state["hwnds"]):
        if not u.IsWindow(hwnd):
            _state["hwnds"].discard(hwnd)
            continue
        if visible:
            u.ShowWindow(hwnd, 9 if u.IsIconic(hwnd) else 8)   # SW_RESTORE / SW_SHOWNA
            if hwnd == focus:
                u.SetForegroundWindow(hwnd)
        else:
            u.ShowWindow(hwnd, 0)                                # SW_HIDE
    _state["hidden"] = not visible


# --- batas waktu harian (config.WEB_DAILY_LIMIT_MIN) ---------------------------------------
USAGE_FILE = os.path.join(C.DATA_DIR, "web_usage.json")
_usage = {"data": None, "dirty": 0.0, "last": None}


_own = {}   # sid -> (waktu baca, batas khusus): students.json dibaca maks. 1x / 5 dtk


def _own_limit(sid):
    hit = _own.get(sid)
    if hit is not None and time.monotonic() - hit[0] < 5.0:
        return hit[1]
    try:
        from elearning.students import lookup_student
        val = (lookup_student(sid) or {}).get("pinterest_limit")
    except Exception:
        val = None
    _own[sid] = (time.monotonic(), val)
    return val


def _limit(key, sid=None):
    """Menit per hari, atau None (tanpa batas). Dibaca saat dipakai (nilai Dev langsung berlaku).
    Pinterest: batas khusus murid dari guru (students.json "pinterest_limit") didahulukan."""
    if key == "pinterest":
        own = _own_limit(sid) if sid else None
        if own is not None:
            return None if own < 0 else own          # -1 = tanpa batas, 0 = diblokir
        return getattr(C, "PINTEREST_LIMIT_MIN", 10) or None
    return (getattr(C, "WEB_DAILY_LIMIT_MIN", {}) or {}).get(key) or None


def _usage_data():
    """{"v": 3, "used": {"<ID>:<situs>": {"start", "secs", "hit", "warned"}}}.
    Sistem menit (seperti batas chat Claude): jatah dipakai sampai habis ("hit" = waktu habis),
    lalu jeda config.WEB_RESET_MIN menit, setelah itu jatah penuh lagi."""
    if _usage["data"] is None:
        try:
            with open(USAGE_FILE, encoding="utf-8") as f:
                _usage["data"] = json.load(f)
        except Exception:
            _usage["data"] = {}
        if _usage["data"].get("v") != 3:             # format lama: mulai baru
            _usage["data"] = {"v": 3, "used": {}}
    return _usage["data"]


def _reset_s():
    return max(1.0, float(getattr(C, "WEB_RESET_MIN", 10) or 10)) * 60


def _slot(sid, key, create=False):
    """Catatan murid+situs; jeda sudah lewat (atau catatan > 1 hari) -> dibuang (reset)."""
    used = _usage_data()["used"]
    k = f"{sid}:{key}"
    e = used.get(k)
    now = time.time()
    if e is not None and ((e.get("hit") and now - e["hit"] >= _reset_s())
                          or now - e.get("start", 0) >= 86400):
        used.pop(k, None)
        e = None
    if e is None and create:
        e = used[k] = {"start": now, "secs": 0.0, "hit": None, "warned": False}
    return e


def used_secs(sid, key):
    e = _slot(sid, key)
    return e["secs"] if e else 0.0


def reset_at(sid, key):
    """Jam reset (HH:MM): jeda setelah jatah habis; sebelum habis = perkiraan kalau dipakai
    terus sampai habis."""
    e = _slot(sid, key)
    if e and e.get("hit"):
        t = e["hit"] + _reset_s()
    else:
        left = remaining(sid, key) or 0.0
        t = time.time() + left + _reset_s()
    return time.strftime("%H:%M", time.localtime(t))


def _save_usage():
    try:
        os.makedirs(C.DATA_DIR, exist_ok=True)
        tmp = USAGE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_usage_data(), f)
        os.replace(tmp, USAGE_FILE)
    except OSError as exc:
        C.log(f"Web: pemakaian tidak tersimpan: {exc!r}")
    _usage["dirty"] = 0.0


def remaining(sid, key):
    """Detik tersisa di jendela waktu sekarang, atau None kalau situs tanpa batas."""
    lim = _limit(key, sid)
    if lim is None:
        return None
    return max(0.0, lim * 60 - used_secs(sid, key))


def usage_ring(sid, key):
    """(0..1 terpakai, baris 1, baris 2) untuk cincin di sidebar, atau None (tanpa batas).
    Mis. (0.46, "46% of Pinterest limit", "6 min left") / (1, "Limit reached",
    "Resets in 43 min")."""
    lim = _limit(key, sid)
    if lim is None:
        return None
    title = next((s["title"] for s in C.WEB_SITES if s["key"] == key), key)
    if lim == 0:
        return (1.0, f"{title} is not available", "Ask your teacher")
    used = used_secs(sid, key)
    frac = min(1.0, used / (lim * 60))
    left = remaining(sid, key) or 0.0
    if left <= 0:
        e = _slot(sid, key)
        wait = max(0, int(((e["hit"] if e and e.get("hit") else time.time()) + _reset_s()
                           - time.time()) // 60) + 1)
        return (1.0, "Limit reached", f"Resets in {wait} min")
    m = int(left // 60 + (1 if left % 60 else 0))
    return (frac, f"{round(frac * 100)}% of {title} limit", f"{m} min left of {lim} min")


def status_text(sid, key):
    """Ringkas untuk tooltip ikon: '8 min left' / 'Limit reached · resets 15:30'."""
    left = remaining(sid, key)
    if left is None:
        return ""
    if _limit(key, sid) == 0:
        return "Not available"
    if left <= 0:
        return f"Limit reached · resets {reset_at(sid, key)}"
    m = int(left // 60 + (1 if left % 60 else 0))
    return f"{m} min left"


WARN_S = 120   # peringatan sekali per jendela waktu saat sisa <= 2 menit


def _count_usage(app):
    """Tambah waktu pakai situs berbatas yang jendelanya terbuka & terlihat; sisa 2 menit ->
    peringatan; habis -> jendela ditutup + jam reset (seperti batas chat Claude)."""
    from elearning.i18n import L
    now = time.monotonic()
    dt = 0.0 if _usage["last"] is None else min(5.0, now - _usage["last"])
    _usage["last"] = now
    sid = _state["sid"]
    for key, hwnd in list(_state["site_hwnd"].items()):
        if _limit(key, sid) is None or not _alive(hwnd):
            continue
        title = next((s["title"] for s in C.WEB_SITES if s["key"] == key), key)
        if not _state["hidden"]:
            e = _slot(sid, key, create=True)
            e["secs"] += dt
            _usage["dirty"] += dt
        left = remaining(sid, key)
        e = _slot(sid, key)
        if 0 < left <= WARN_S and e and not e.get("warned"):
            e["warned"] = True
            _save_usage()
            app.after(50, lambda t=title, m=getattr(C, "WEB_RESET_MIN", 10): _message(app, t, L(
                f"Sisa waktu {t} 2 menit. Setelah habis, istirahat {m} menit.",
                f"2 minutes of {t} left. After that, take a {m}-minute break.")))
        if left <= 0:
            e = _slot(sid, key, create=True)
            if not e.get("hit"):
                e["hit"] = time.time()                              # jeda reset mulai sekarang
            _user32()[0].PostMessageW(hwnd, 0x0010, 0, 0)          # WM_CLOSE
            _state["site_hwnd"].pop(key, None)
            _save_usage()
            r = reset_at(sid, key)
            C.log(f"Web: batas {title} habis untuk {sid}, reset {r}")
            app.after(50, lambda t=title, r=r: _message(app, t, L(
                f"Batas {t} habis. Bisa dipakai lagi pukul {r}.",
                f"You've hit your {t} limit. It resets at {r}.")))
    if _usage["dirty"] >= 10:                    # simpan tiap ~10 dtk pemakaian
        _save_usage()


def _watch():
    app = _state["app"]
    _state["job"] = None
    if app is None or not running():
        if app is not None:
            _state.update(proc=None, sid=None, app=None, hwnds=set(), site_hwnd={},
                          pending=[])
        return
    try:
        if sys.platform == "win32":
            owner = int(app.wm_frame(), 16)
            visible = app.state() == "normal" and app.winfo_viewable()
            if not _state["hidden"]:
                now = time.monotonic()
                _state["pending"] = [p for p in _state["pending"] if now - p[1] < PENDING_S]
                for hwnd in _chrome_windows(_state["proc"].pid):   # termasuk popup login
                    if hwnd not in _state["hwnds"]:
                        _adopt(hwnd, owner)
                        _state["hwnds"].add(hwnd)
                        if _state["pending"]:   # jendela baru = situs yang terakhir diminta
                            _state["site_hwnd"][_state["pending"].pop(0)[0]] = hwnd
                        else:                   # dibuka dari dalam situs: diperiksa dulu
                            _state.setdefault("extra", {})[hwnd] = now
                _close_extra(now)
                if _state.get("profile") == "studio":
                    _close_search()
            if visible == _state["hidden"]:      # aplikasi mengecil / kembali
                _show(visible)
            if visible:
                for hwnd in list(_state["hwnds"]):
                    _clamp(hwnd, app)
            _count_usage(app)
        _state["job"] = app.after(WATCH_MS, _watch)
    except Exception as exc:
        C.log(f"Web: pengawas jendela berhenti: {exc!r}")
