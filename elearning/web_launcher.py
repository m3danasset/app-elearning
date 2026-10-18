"""Chrome murid (config.WEB_SITES), bukan trial: Google Chrome BIASA untuk semua murid
(pemilih profil ui/chrome_profiles.py) + Gemini / Flow untuk murid AI (jendela --app).

- Gemini / Flow: chrome.exe --app=<url>: jendela polos tanpa kolom alamat / tab. Chrome asli
  (bukan browser tertanam) supaya login Google tidak diblokir.
- SATU folder data Chrome per ID murid di %LOCALAPPDATA%\\M3DAN\\browser\\<ID> (satu proses
  Chrome; tiap situs = jendela sendiri). Di dalamnya profil Chrome milik murid (Default,
  Profile 1, ...; pemilih profil ui/chrome_profiles.py). Akun murid lain tidak terlihat.
  Unduhan diarahkan ke config.STUDENT_DRIVE (Z:\\).
- Chrome biasa & jendela situs memakai SATU proses Chrome per murid (peluncuran berikutnya
  diteruskan ke proses itu): membuka Gemini tidak menutup Chrome murid, dan sebaliknya.
- Jendela situs hanya terlihat di aplikasi utama: dijadikan "milik" jendela aplikasi
  (selalu di atas aplikasi, tidak di atas program lain, tidak ada di taskbar), ditahan di dalam
  area aplikasi, disembunyikan saat aplikasi mengecil / Blender dibuka, ditutup saat logout.
- Prioritas BelowNormal. Pengawas posisi = after() tiap 300 ms (bukan animasi),
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
# hwnds: jendela situs milik aplikasi; site_hwnd: kunci situs -> jendela utamanya;
# pending: situs yang baru diluncurkan, menunggu jendelanya muncul; pdirs: profil Chrome biasa
# yang dibuka; bwins: jendela Chrome biasa (bebas, tidak dijadikan milik aplikasi)
_state = {"proc": None, "sid": None, "app": None, "job": None, "hwnds": set(), "hidden": False,
          "site_hwnd": {}, "pending": [], "extra": {}, "pdirs": set(), "bwins": set()}
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
    return [s for s in C.WEB_SITES if s["ai"] is None or (ai if s["ai"] else other)]


def available(student):
    return bool(sites_for(student))


def chrome_path():
    cands = [C.CHROME_PATH] if C.CHROME_PATH else []
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            cands.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    return next((p for p in cands if p and os.path.isfile(p)), None)


def profile_dir(student_id):
    """Folder data Chrome (--user-data-dir) murid ini; profil-profilnya ada di dalamnya."""
    base = os.environ.get("LOCALAPPDATA") or os.path.join(C.APP_DIR, "data")
    safe = "".join(ch for ch in str(student_id) if ch.isalnum()) or "murid"
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


# --- profil Chrome murid (pemilih profil gaya Chrome: tambah akun Google / hapus) ---------
META = "m3dan_profiles.json"      # {"profiles": ["Profile 1", ...]} di folder data Chrome murid
# halaman login Google versi "masuk ke Chrome" (seperti tombol Sign in profil baru Chrome)
SIGNIN_URL = ("https://accounts.google.com/signin/chrome/sync?ssp=1&continue="
              "https%3A%2F%2Fwww.google.com%2F")


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
        return True
    except OSError as exc:
        C.log(f"Web: {os.path.basename(path)} tidak tersimpan: {exc!r}")
        return False


def _cookie_email(prefs):
    """Email akun Google yang login di web saja (belum login ke Chrome): daftar akun cookie
    Google yang disimpan Chrome di Preferences (gaia_cookie)."""
    import base64
    import re
    g = prefs.get("gaia_cookie") or {}
    text = g.get("last_list_accounts_data") or ""
    raw = g.get("last_list_accounts_binary_data") or ""
    if raw:
        try:
            text += base64.b64decode(raw).decode("latin-1")
        except Exception:
            pass
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", str(text))
    return m.group(0) if m else ""


def _account(folder, pdir, local):
    """(nama, email, gambar) akun Google profil ini: data login Chrome (Local State), daftar
    akun di Preferences, atau akun yang login di web. Kosong = belum login."""
    info = ((local.get("profile") or {}).get("info_cache") or {}).get(pdir) or {}
    name = info.get("gaia_given_name") or info.get("gaia_name") or ""
    email = info.get("user_name") or ""
    pd = os.path.join(folder, pdir)
    if not email or not name:
        prefs = _read_json(os.path.join(pd, "Preferences"))
        for a in prefs.get("account_info") or []:
            if isinstance(a, dict) and a.get("email"):
                email = email or a["email"]
                name = name or a.get("given_name") or a.get("full_name") or ""
                break
        email = email or _cookie_email(prefs)
    pic = os.path.join(pd, "Google Profile Picture.png")
    if not os.path.isfile(pic):
        pic = None
        av = os.path.join(pd, "Accounts", "Avatar Images")
        try:
            names = sorted(os.listdir(av))
        except OSError:
            names = []
        if names:
            pic = os.path.join(av, names[0])
    return name, email, pic


def _profile_dirs(sid):
    """Nama folder profil murid (urut ditambahkan). Pertama kali: profil lama "Default" yang
    sudah login akun Google ikut dipakai."""
    folder = profile_dir(sid)
    dirs = _read_json(os.path.join(folder, META)).get("profiles")
    if isinstance(dirs, list):
        return [d for d in dirs if isinstance(d, str) and d]
    dirs = []
    if os.path.isdir(os.path.join(folder, "Default")):
        local = _read_json(os.path.join(folder, "Local State"))
        if _account(folder, "Default", local)[1]:
            dirs = ["Default"]
        _write_json(os.path.join(folder, META), {"profiles": dirs})
    return dirs


def chrome_profiles(sid):
    """Profil Chrome murid ini: [{"dir", "name", "email", "picture"}] (yang foldernya ada)."""
    folder = profile_dir(sid)
    local = _read_json(os.path.join(folder, "Local State"))
    out = []
    for d in _profile_dirs(sid):
        if os.path.isdir(os.path.join(folder, d)):
            name, email, pic = _account(folder, d, local)
            out.append({"dir": d, "name": name, "email": email, "picture": pic})
    return out


def max_profiles():
    return max(1, int(getattr(C, "WEB_MAX_PROFILES", 4) or 4))


def add_profile(widget, student):
    """Kartu "Add": profil Chrome baru (Profile N) dibuka di halaman login Google."""
    from elearning.i18n import L
    app = widget.winfo_toplevel()
    sid = student["id"]
    if len(chrome_profiles(sid)) >= max_profiles():
        _message(app, "Chrome", L(f"Maksimal {max_profiles()} profil. Hapus satu dulu.",
                                  f"You can have up to {max_profiles()} profiles. "
                                  "Delete one first."))
        return False
    if _browse_blocked(app, sid):
        return False
    folder = profile_dir(sid)
    dirs = _profile_dirs(sid)
    n = 1
    while f"Profile {n}" in dirs or os.path.exists(os.path.join(folder, f"Profile {n}")):
        n += 1
    pdir = f"Profile {n}"
    if not _write_json(os.path.join(folder, META), {"profiles": dirs + [pdir]}):
        return False
    C.log(f"Web: profil Chrome {pdir} ditambahkan untuk {sid}")
    return open_browser(widget, student, pdir, url=SIGNIN_URL)


def delete_profile(student, pdir):
    """Hapus profil Chrome murid dari PC ini (akun Google, riwayat, bookmark). Chrome murid
    ditutup dulu; folder profil dihapus di thread."""
    import shutil
    import threading
    sid = student["id"]
    dirs = _profile_dirs(sid)
    if pdir not in dirs or os.sep in pdir or "/" in pdir or pdir in (".", ".."):
        return False
    folder = profile_dir(sid)
    if running() and _state["sid"] == sid:
        close()
    _kill_profile(folder)
    dirs = [d for d in dirs if d != pdir]
    _write_json(os.path.join(folder, META), {"profiles": dirs})
    path = os.path.join(folder, "Local State")
    local = _read_json(path)
    prof = local.get("profile")
    if isinstance(prof, dict):         # hanya kalau terbaca (kunci cookie profil lain aman)
        (prof.get("info_cache") or {}).pop(pdir, None)
        for k in ("profiles_order", "last_active_profiles"):
            if isinstance(prof.get(k), list):
                prof[k] = [d for d in prof[k] if d != pdir]
        if prof.get("last_used") == pdir:
            if dirs:
                prof["last_used"] = dirs[-1]
            else:
                prof.pop("last_used", None)
        _write_json(path, local)
    target = os.path.join(folder, pdir)

    def work():                    # Chrome yang baru ditutup bisa masih memegang file sebentar
        for _ in range(5):
            shutil.rmtree(target, ignore_errors=True)
            if not os.path.exists(target):
                break
            time.sleep(1.0)
        C.log(f"Web: profil Chrome {pdir} milik {sid} dihapus"
              + ("" if not os.path.exists(target) else " (sebagian file masih terkunci)"))

    threading.Thread(target=work, daemon=True).start()
    return True


def _last_profile(folder):
    """Profil Chrome yang terakhir dipakai murid (akun Google terakhir): untuk Gemini / Flow."""
    d = (_read_json(os.path.join(folder, "Local State")).get("profile") or {}).get("last_used")
    return d if isinstance(d, str) and d and os.path.isdir(os.path.join(folder, d)) else "Default"


def _prepare_profile(folder, pdir="Default"):
    """Unduhan ke drive murid, tanpa simpan kata sandi (PC dipakai bergantian)."""
    path = os.path.join(folder, pdir, "Preferences")
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


def _base_args(exe, student, pdir):
    """Argumen bersama (Chrome biasa & jendela situs = SATU proses): profil murid, tanpa layar
    pertama, pencarian aman SUPERKIDS (+ --test-type: tanpa bilah peringatan "unsupported
    command-line flag"), mode ringan tanpa GPU."""
    args = [exe, f"--user-data-dir={profile_dir(student['id'])}", f"--profile-directory={pdir}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-features=Translate,MediaRouter"]
    rules = _safe_rules(student)
    if rules:
        args += [f"--host-resolver-rules={rules}", "--test-type"]
    if C.lite():   # mode ringan (iGPU + Blender): Chrome tidak memakai GPU
        args += ["--disable-gpu", "--disable-smooth-scrolling"]
    return args


def _launch(app, title, args):
    """Jalankan chrome.exe (BelowNormal) -> proses atau None (+ pesan)."""
    from elearning.i18n import L
    flags = 0x00004000 if sys.platform == "win32" else 0   # BELOW_NORMAL_PRIORITY_CLASS
    try:
        return subprocess.Popen(args, creationflags=flags, close_fds=True)
    except OSError as exc:
        C.log(f"Web: Chrome gagal dibuka: {exc!r}")
        _message(app, title, L("Chrome tidak bisa dibuka. Coba lagi.",
                               "Chrome could not be opened. Please try again."))
        return None


def _no_chrome(app, title):
    from elearning.i18n import L
    _message(app, title, L("Google Chrome belum terpasang di PC ini. Hubungi guru / admin.",
                           "Google Chrome is not installed on this PC. Please ask your teacher."))


def _started(proc, student, app):
    """Proses Chrome pertama murid ini: peluncuran berikutnya diteruskan ke sini."""
    _state.update(proc=proc, sid=student["id"], app=app, hwnds=set(), hidden=False,
                  site_hwnd={}, pending=[], extra={}, pdirs=set(), bwins=set())


def open_web(widget, student, key):
    """Situs (Gemini / Flow) di jendela aplikasi sendiri (--app), atau tampilkan lagi kalau
    sudah terbuka. Profil Chrome yang terakhir dipakai murid (akun Google-nya). Proses Chrome
    murid yang sudah jalan (mis. Chrome biasa) dipakai bersama; ganti murid -> ditutup."""
    from elearning.i18n import L
    app = widget.winfo_toplevel()
    sites = sites_for(student)
    site = next((s for s in sites if s["key"] == key), None)
    if site is None:
        return False
    if running() and _state["sid"] != student["id"]:
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
        _no_chrome(app, site["title"])
        return False
    folder = profile_dir(student["id"])
    first = not running()
    pdir = _last_profile(folder)
    if first:
        _kill_profile(folder)     # sisa Chrome murid ini (aturan / flag lama)
        _prepare_profile(folder, pdir)
    x, y, w, h = _area(app)
    ww, hh = max(420, int(w * 0.42)), max(360, h - 24)
    n = len(_state["site_hwnd"]) if running() else 0          # jendela berikutnya sedikit bergeser
    args = _base_args(exe, student, pdir) + [
        f"--app={site['url']}", f"--window-size={ww},{hh}",
        f"--window-position={x + w - ww - 12 - 24 * n},{y + 12 + 24 * n}"]
    proc = _launch(app, site["title"], args)
    if proc is None:
        return False
    if first:      # peluncuran berikutnya diteruskan ke proses ini lalu langsung selesai
        _started(proc, student, app)
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


def _kill_profile(folder):
    """Chrome lain yang memakai folder data ini (mis. sisa jendela situs / Chrome biasa)
    ditutup: aturan host hanya berlaku saat proses Chrome pertama diluncurkan."""
    if sys.platform != "win32" or not os.path.isdir(folder):
        return
    lock = os.path.join(folder, "lockfile")     # ada & terkunci = Chrome profil ini jalan
    if not os.path.exists(lock):
        return
    try:
        os.remove(lock)                         # bisa dihapus = tidak ada Chrome yang jalan
        return
    except OSError:
        pass
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object { "
          "$_.CommandLine -and $_.CommandLine.ToLower().Contains('" + folder.lower().replace("'", "''")
          + "') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
          "-ErrorAction SilentlyContinue }")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, creationflags=0x08000000, timeout=15)
    except Exception as exc:
        C.log(f"Web: Chrome profil lama tidak bisa ditutup: {exc!r}")


def _safe_rules(student):
    """Program config.WEB_SAFE_PROGRAMS (SUPERKIDS): pencarian aman (SafeSearch Google / Bing /
    DuckDuckGo, YouTube Restricted) lewat aturan host. Situs lain tetap bebas."""
    if student.get("program") not in getattr(C, "WEB_SAFE_PROGRAMS", ()):
        return ""
    try:
        from elearning import app_settings
        if not app_settings.feature("safesearch"):
            return ""
    except Exception:
        pass
    return ", ".join(f"MAP {a} {b}" for a, b in getattr(C, "WEB_SAFE_MAP", ()))


def _browse_blocked(app, sid):
    """Batas browsing habis / Chrome diblokir guru -> pesan + True."""
    from elearning.i18n import L
    left = remaining(sid, "pinterest")
    if left is None or left > 0:
        return False
    lim = _limit("pinterest", sid)
    r = reset_at(sid, "pinterest")
    _message(app, "Chrome", L(
        "Chrome tidak tersedia untukmu. Tanya guru." if lim == 0 else
        f"Batas browsing habis. Bisa dipakai lagi pukul {r}.",
        "Chrome is not available for you. Ask your teacher." if lim == 0 else
        f"You've hit your browsing limit ({lim} min). It resets at {r}."))
    return True


def _browser_windows():
    """Jendela Chrome biasa murid yang masih ada."""
    if sys.platform != "win32":
        return []
    u = _user32()[0]
    live = [h for h in _state["bwins"] if u.IsWindow(h)]
    _state["bwins"] = set(live)
    return live


def _front():
    """Jendela Chrome biasa murid dibawa ke depan (yang di-minimize dipulihkan)."""
    if sys.platform != "win32" or not running():
        return
    u, _c, _w = _user32()
    wins = _browser_windows()
    for hwnd in wins:
        u.ShowWindow(hwnd, 9 if u.IsIconic(hwnd) else 5)    # RESTORE / SHOW
    if wins:
        u.SetForegroundWindow(wins[0])


def open_browser(widget, student, pdir, url=None):
    """Kartu profil di popup Chrome: Google Chrome BIASA (tab, kolom alamat, semua situs) dengan
    profil murid itu (--profile-directory). Proses Chrome murid yang sudah jalan (profil lain,
    Gemini / Flow) dipakai bersama: jendela baru. Waktu browsing dibatasi per hari (kunci
    "pinterest"): dihitung selama ada jendela Chrome biasa yang tidak di-minimize."""
    app = widget.winfo_toplevel()
    if not any(s["key"] == "pinterest" for s in sites_for(student)):
        return False
    if running() and _state["sid"] != student["id"]:
        close()
    if _browse_blocked(app, student["id"]):
        return False
    if running() and url is None and pdir in _state["pdirs"] and _browser_windows():
        _front()                                     # profil ini sudah terbuka: ke depan
        return True
    exe = chrome_path()
    if exe is None:
        _no_chrome(app, "Chrome")
        return False
    folder = profile_dir(student["id"])
    first = not running()
    if first:
        _kill_profile(folder)      # sisa Chrome murid ini (aturan / flag lama)
    _prepare_profile(folder, pdir)
    args = _base_args(exe, student, pdir) + ([url] if url else [])
    proc = _launch(app, "Chrome", args)
    if proc is None:
        return False
    if first:      # peluncuran berikutnya diteruskan ke proses ini lalu langsung selesai
        _started(proc, student, app)
    _state["pdirs"].add(pdir)
    _state["bwait"] = time.monotonic()
    C.log(f"Web: Chrome ({pdir}) dibuka untuk {student['id']}")
    if _state["job"] is None:
        _watch()
    return True


def _count_browser(app, active):
    """Waktu browsing (kunci "pinterest"): bertambah selama ada jendela Chrome biasa yang tidak
    di-minimize. Sisa 2 menit -> peringatan; habis -> jendela Chrome biasa ditutup (Gemini /
    Flow tetap) + jam reset."""
    from elearning.i18n import L
    now = time.monotonic()
    dt = 0.0 if _usage["blast"] is None else min(5.0, now - _usage["blast"])
    _usage["blast"] = now
    sid, key = _state["sid"], "pinterest"
    if _limit(key, sid) is None:
        return
    if active:
        e = _slot(sid, key, create=True)
        e["secs"] += dt
        _usage["dirty"] += dt
    left = remaining(sid, key)
    e = _slot(sid, key)
    if 0 < left <= WARN_S and e and not e.get("warned"):
        e["warned"] = True
        _save_usage()
        app.after(50, lambda m=getattr(C, "WEB_RESET_MIN", 10): _message(app, "Chrome", L(
            f"Sisa waktu browsing 2 menit. Setelah habis, istirahat {m} menit.",
            f"2 minutes of browsing left. After that, take a {m}-minute break.")))
    if left <= 0:
        e = _slot(sid, key, create=True)
        if not e.get("hit"):
            e["hit"] = time.time()
        _save_usage()
        r = reset_at(sid, key)
        C.log(f"Web: batas browsing habis untuk {sid}, reset {r}")
        if sys.platform == "win32" and any(_alive(h) for h in _state["site_hwnd"].values()):
            u = _user32()[0]
            for hwnd in _browser_windows():                      # jendela situs tetap
                u.PostMessageW(hwnd, 0x0010, 0, 0)               # WM_CLOSE
            _state.update(pdirs=set(), bwins=set())
        else:
            close()                                              # seluruh Chrome ditutup
        app.after(50, lambda r=r: _message(app, "Chrome", L(
            f"Batas browsing habis. Bisa dipakai lagi pukul {r}.",
            f"You've hit your browsing limit. It resets at {r}.")))
        return
    if _usage["dirty"] >= 10:
        _save_usage()


def close():
    """Tutup jendela web (logout, tutup aplikasi, ganti murid)."""
    if _usage["dirty"]:
        _save_usage()
    _usage["last"] = _usage["blast"] = None
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
                  site_hwnd={}, pending=[], extra={}, pdirs=set(), bwins=set())


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
_usage = {"data": None, "dirty": 0.0, "last": None, "blast": None}   # blast = Chrome biasa


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
    what = "browsing" if key == "pinterest" else title
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
    return (frac, f"{round(frac * 100)}% of {what} limit", f"{m} min left of {lim} min")


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
                          pending=[], extra={}, pdirs=set(), bwins=set())
        return
    try:
        if sys.platform == "win32":
            owner = int(app.wm_frame(), 16)
            visible = app.state() == "normal" and app.winfo_viewable()
            now = time.monotonic()
            _state["pending"] = [p for p in _state["pending"] if now - p[1] < PENDING_S]
            for hwnd in _chrome_windows(_state["proc"].pid):       # termasuk popup login
                if hwnd in _state["hwnds"] or hwnd in _state["bwins"]:
                    continue
                if _state["pending"]:          # jendela baru = situs yang terakhir diminta
                    if _state["hidden"]:
                        continue               # dijadikan milik aplikasi setelah tampil lagi
                    _adopt(hwnd, owner)
                    _state["hwnds"].add(hwnd)
                    _state["site_hwnd"][_state["pending"].pop(0)[0]] = hwnd
                elif _state["pdirs"]:          # Chrome biasa murid: jendela bebas (tab, Ctrl+N)
                    _state["bwins"].add(hwnd)
                elif not _state["hidden"]:     # dibuka dari dalam situs: diperiksa dulu
                    _adopt(hwnd, owner)
                    _state["hwnds"].add(hwnd)
                    _state["extra"][hwnd] = now
            if not _state["hidden"]:
                _close_extra(now)
            if visible == _state["hidden"]:      # aplikasi mengecil / kembali
                _show(visible)
            if visible:
                for hwnd in list(_state["hwnds"]):
                    _clamp(hwnd, app)
            _count_usage(app)
            if _state["pdirs"]:
                u = _user32()[0]
                live = _browser_windows()
                if not live and now - _state.get("bwait", 0.0) > PENDING_S:
                    _state["pdirs"] = set()    # semua jendela Chrome biasa sudah ditutup
                _count_browser(app, any(not u.IsIconic(h) for h in live))
        else:
            _count_usage(app)
            if _state["pdirs"]:
                _count_browser(app, True)
        if _state["app"] is not None:
            _state["job"] = app.after(WATCH_MS, _watch)
    except Exception as exc:
        C.log(f"Web: pengawas jendela berhenti: {exc!r}")
