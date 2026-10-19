"""Live classroom: aktivitas murid SAAT INI untuk admin & guru (Panel Admin / guru > Live Kelas).

Aplikasi murid (bukan trial) menulis data\\presence\\<ID>.json tiap PUSH_S detik (di thread
utama, kecil & cepat): layar & halaman yang dibuka, kursus, pelajaran + posisi video (diputar /
dijeda), Blender terbuka / di depan, Chrome terbuka, lama tidak menyentuh mouse / keyboard (idle),
nama PC. Keluar / tutup aplikasi = file dihapus. File yang lebih tua dari STALE_S detik =
dianggap offline (PC mati / app macet). Seperti sessions.py: semua PC memakai folder data yang
sama, jadi admin / guru melihat murid di PC lain.
"""

import json
import os
import time
from datetime import datetime

from elearning import config as C

PUSH_S = 15          # murid menulis status sesering ini
STALE_S = 75         # lebih tua dari ini = offline
IDLE_AWAY_S = 300    # tidak menyentuh mouse / keyboard selama ini = "diam"


def _dir():
    return os.path.join(C.DATA_DIR, "presence")


def _path(sid):
    return os.path.join(_dir(), f"{str(sid).upper()}.json")


def idle_seconds():
    """Detik sejak input terakhir di PC ini (GetLastInputInfo), 0 kalau tidak tahu."""
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0
        now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        return max(0, (now - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:
        return 0


def write(sid, info):
    """Simpan status murid (dict). Gagal menulis = diam saja (tidak boleh mengganggu murid)."""
    try:
        os.makedirs(_dir(), exist_ok=True)
        rec = dict(info, id=str(sid).upper(), t=time.time())
        tmp = _path(sid) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
        os.replace(tmp, _path(sid))
    except OSError as exc:
        C.log(f"Live kelas: status {sid} tidak tersimpan: {exc!r}")


def clear(sid):
    try:
        os.remove(_path(sid))
    except OSError:
        pass


def read_all():
    """[status] murid yang online sekarang (file cukup baru), urut ID."""
    out = []
    now = time.time()
    try:
        names = os.listdir(_dir())
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(_dir(), name), encoding="utf-8") as f:
                rec = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and now - float(rec.get("t", 0)) <= STALE_S:
            out.append(rec)
    out.sort(key=lambda r: r.get("id", ""))
    return out


def activity(rec):
    """(teks aktivitas, jenis) untuk tampilan: jenis = video | blender | browse | page | idle."""
    if rec.get("idle", 0) >= IDLE_AWAY_S:
        return f"Diam {int(rec['idle'] // 60)} menit", "idle"
    if rec.get("blender_front"):
        return "Mengerjakan di Blender", "blender"
    if rec.get("screen") == "course" and rec.get("view") == "materi" and rec.get("lesson"):
        state = "menonton" if rec.get("playing") else "video dijeda"
        return f"{state}: {rec['lesson']}", "video"
    if rec.get("browser_front"):
        return "Browsing di Chrome", "browse"
    page = {"dashboard": "Dashboard", "materi": "Lessons", "resource": "Resources",
            "portfolio": "Portfolio", "assignment": "Assignment", "badges": "Badges",
            "certificate": "Certificate"}.get(rec.get("view"), rec.get("view") or "-")
    return f"Membuka {page}", "page"


# --- rekap aktivitas harian (untuk export Excel) -------------------------------------------
# data\activity\<ID>.json {"YYYY-MM-DD": {"video": dtk, "blender": dtk, "browse": dtk,
# "page": dtk, "idle": dtk, "courses": {judul: dtk}, "first": "HH:MM", "last": "HH:MM",
# "pc": nama}}. Ditambah tiap status (15 dtk) oleh app murid; > KEEP_DAYS hari dibuang.
KINDS = ("video", "blender", "browse", "page", "idle")
KEEP_DAYS = 400


def _act_path(sid):
    return os.path.join(C.DATA_DIR, "activity", f"{str(sid).upper()}.json")


def _act_load(sid):
    try:
        with open(_act_path(sid), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def add_activity(sid, kind, seconds, course="", pc=""):
    """Tambah detik aktivitas murid hari ini (dipanggil app murid tiap status)."""
    if kind not in KINDS or seconds <= 0:
        return
    now = datetime.now()
    day = now.strftime("%Y-%m-%d")
    data = _act_load(sid)
    d = data.setdefault(day, {})
    d[kind] = round(d.get(kind, 0) + seconds, 1)
    if course and kind != "idle":
        c = d.setdefault("courses", {})
        c[course] = round(c.get(course, 0) + seconds, 1)
    d.setdefault("first", now.strftime("%H:%M"))
    d["last"] = now.strftime("%H:%M")
    if pc:
        d["pc"] = pc
    if len(data) > KEEP_DAYS:
        for k in sorted(data)[:len(data) - KEEP_DAYS]:
            data.pop(k, None)
    try:
        os.makedirs(os.path.dirname(_act_path(sid)), exist_ok=True)
        tmp = _act_path(sid) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, _act_path(sid))
    except OSError as exc:
        C.log(f"Live kelas: rekap aktivitas {sid} tidak tersimpan: {exc!r}")


def activity_days(sid):
    """Rekap harian murid {tanggal: {...}} (lihat add_activity)."""
    return _act_load(sid)
