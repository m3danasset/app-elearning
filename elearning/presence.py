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
