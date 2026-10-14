"""Riwayat masuk/keluar murid, disimpan di  data\\sessions.json  (di samping .exe).

Satu catatan per sesi: {"id", "in", "out", "last"}. 'last' diperbarui tiap menit
selama murid masuk. Kalau aplikasi mati mendadak (listrik padam, ditutup paksa)
sehingga 'out' kosong, jam keluar diperkirakan dari 'last' dan ditandai perkiraan.

Pencatatan tidak boleh mengganggu aplikasi: semua kegagalan hanya dicatat di app.log.
"""

import json
import os
from datetime import datetime

from elearning import config as C

FMT = "%Y-%m-%d %H:%M:%S"
MAX_KEEP = 5000          # simpan paling banyak sekian catatan terbaru
_current = None          # (id, jam masuk) sesi yang sedang terbuka di jalankan ini

_DAYS = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
           "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


# --- baca / tulis -------------------------------------------------------------
def _now():
    return datetime.now().strftime(FMT)


def _parse(text):
    try:
        return datetime.strptime(text, FMT)
    except (TypeError, ValueError):
        return None


def _read():
    try:
        with open(C.SESSIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)
                    and isinstance(r.get("id"), str) and _parse(r.get("in"))]
        raise ValueError("isi file bukan daftar sesi")
    except FileNotFoundError:
        return []
    except Exception as exc:
        C.log(f"data\\sessions.json rusak ({exc!r}) -> dimulai dari kosong")
        try:
            os.replace(C.SESSIONS_FILE, C.SESSIONS_FILE + ".rusak")
        except OSError:
            pass
        return []


def _write(records):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = C.SESSIONS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records[-MAX_KEEP:], f, ensure_ascii=False, indent=1)
    os.replace(tmp, C.SESSIONS_FILE)


def _is_current(rec):
    return (_current is not None and rec.get("out") is None
            and (rec["id"], rec["in"]) == _current)


# --- dipanggil aplikasi ---------------------------------------------------------
def start(student_id):
    """Murid masuk. Sesi lama yang tidak ditutup dirapikan dulu."""
    global _current
    try:
        if _current is not None:
            end()
        records = _read()
        for r in records:
            if r.get("out") is None:       # sisa aplikasi yang mati mendadak
                r["out"] = r.get("last") or r["in"]
                r["auto"] = True
        now = _now()
        records.append({"id": student_id, "in": now, "out": None, "last": now})
        _write(records)
        _current = (student_id, now)
    except Exception as exc:
        C.log(f"Gagal mencatat masuk {student_id}: {exc!r}")


def _touch(close):
    global _current
    if _current is None:
        return
    try:
        records = _read()
        now = _now()
        for r in records:
            if _is_current(r):
                r["last"] = now
                if close:
                    r["out"] = now
        _write(records)
        if close:
            _current = None
    except Exception as exc:
        C.log(f"Gagal memperbarui riwayat login: {exc!r}")
        if close:
            _current = None


def heartbeat():
    """Tandai murid masih di dalam aplikasi (dipanggil tiap menit)."""
    _touch(close=False)


def end():
    """Murid keluar (tombol Keluar atau jendela ditutup). Aman dipanggil kapan saja."""
    _touch(close=True)


def delete_student(student_id):
    """Hapus seluruh riwayat satu murid."""
    global _current
    try:
        records = _read()
        kept = [r for r in records if r["id"] != student_id]
        if len(kept) != len(records):
            _write(kept)
        if _current is not None and _current[0] == student_id:
            _current = None
    except Exception as exc:
        C.log(f"Gagal menghapus riwayat {student_id}: {exc!r}")


# --- dipakai layar guru -----------------------------------------------------------
def entries(student_id):
    """Riwayat satu murid, terbaru di atas.

    Tiap item: start, end (datetime atau None), seconds, active (masih masuk),
    approx (jam keluar hanya perkiraan karena aplikasi tidak ditutup normal).
    """
    out = []
    for r in _read():
        if r["id"] != student_id:
            continue
        start_dt = _parse(r["in"])
        active = _is_current(r)
        end_dt = _parse(r.get("out")) if r.get("out") else None
        approx = bool(r.get("auto"))
        if end_dt is None:
            end_dt = _parse(r.get("last")) or start_dt
            approx = not active
        seconds = max(0, int((end_dt - start_dt).total_seconds()))
        out.append({"start": start_dt, "end": None if active else end_dt,
                    "seconds": seconds, "active": active, "approx": approx})
    out.sort(key=lambda e: e["start"], reverse=True)
    return out


def format_duration(seconds):
    """Durasi singkat: '<1 Mnt', '25 Mnt', '3.5 Jam', '2 Jam'."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "<1 Mnt"
    if seconds < 3600:
        return f"{seconds // 60} Mnt"
    hours = f"{seconds / 3600:.1f}".rstrip("0").rstrip(".")
    return f"{hours} Jam"


def format_date(dt):
    return f"{_DAYS[dt.weekday()]}, {dt.day} {_MONTHS[dt.month - 1]} {dt.year}"


def format_time(dt):
    return dt.strftime("%H:%M")
