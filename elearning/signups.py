"""Pendaftar dari akun trial (survey setelah trial selesai) -> disetujui admin jadi murid.

Disimpan di data\\trial_signups.json (daftar, terbaru di akhir):
  {"id": "S0001", "at": "YYYY-mm-dd HH:MM:SS", "status": "pending" | "approved" | "rejected",
   <isi survey: name, phone, email, age, school, parent, parent_phone, address, interest,
    source, notes>, "student": ID murid (setelah disetujui), "done_at", "by"}
Survey diisi di layar trial (bahasa Inggris); Panel Admin > Pendaftar menyetujui / menolak.
"""

import json
import os
import re
import threading
from datetime import datetime

from elearning import config as C

PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
FMT = "%Y-%m-%d %H:%M:%S"
MAX_LEN = 200          # batas panjang satu isian (alamat / catatan boleh panjang)

# (kunci, label survey English, label admin Indonesia, wajib?, lebar penuh?)
FIELDS = (
    ("name", "Full name", "Nama", True, False),
    ("phone", "Phone / WhatsApp", "Telepon / WA", True, False),
    ("age", "Age", "Umur", True, False),
    ("email", "Email", "Email", False, False),
    ("school", "School / campus / workplace", "Sekolah / kampus / kerja", False, False),
    ("interest", "Class you're interested in", "Minat kelas", False, False),
    ("parent", "Parent / guardian name", "Nama orang tua / wali", False, False),
    ("parent_phone", "Parent / guardian phone", "Telepon orang tua", False, False),
    ("address", "Address", "Alamat", False, True),
    ("source", "How did you hear about us?", "Tahu dari mana", False, True),
    ("notes", "Anything else we should know?", "Catatan", False, True),
)
KEYS = tuple(f[0] for f in FIELDS)

_lock = threading.Lock()


def _path():
    return os.path.join(C.DATA_DIR, "trial_signups.json")


def _read():
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return [r for r in data if isinstance(r, dict) and r.get("id")] \
            if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _write(rows):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _path())       # tulis utuh atau tidak sama sekali


def clean(values):
    """Rapikan & periksa isian survey. ValueError (pesan English) kalau ada yang salah."""
    out = {}
    for key in KEYS:
        v = " ".join(str(values.get(key, "")).split())
        if len(v) > MAX_LEN:
            v = v[:MAX_LEN]
        out[key] = v
    if not out["name"]:
        raise ValueError("Please fill in your full name.")
    digits = re.sub(r"\D", "", out["phone"])
    if len(digits) < 8:
        raise ValueError("Please enter a valid phone / WhatsApp number.")
    if not out["age"].isdigit() or not 3 <= int(out["age"]) <= 99:
        raise ValueError("Please enter your age as a number (3-99).")
    if out["email"] and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", out["email"]):
        raise ValueError("That email address doesn't look right.")
    if out["parent_phone"] and len(re.sub(r"\D", "", out["parent_phone"])) < 8:
        raise ValueError("Please enter a valid parent / guardian phone number.")
    return out


def add(values):
    """Simpan survey baru (status menunggu). Kembalikan rekamannya."""
    rec = clean(values)
    with _lock:
        rows = _read()
        n = max([int(r["id"][1:]) for r in rows if re.match(r"^S\d+$", r["id"])] or [0]) + 1
        rec = dict({"id": f"S{n:04d}", "at": datetime.now().strftime(FMT),
                    "status": PENDING}, **rec)
        rows.append(rec)
        _write(rows)
    C.log(f"Pendaftar baru dari trial: {rec['id']}")
    return rec


def list_all():
    """Semua pendaftar: yang menunggu dulu, lalu terbaru."""
    rows = _read()
    rows.sort(key=lambda r: r.get("at", ""), reverse=True)
    rows.sort(key=lambda r: r.get("status") != PENDING)
    return rows


def get(signup_id):
    return next((r for r in _read() if r["id"] == signup_id), None)


def pending_count():
    return sum(1 for r in _read() if r.get("status") == PENDING)


def _set(signup_id, **changes):
    with _lock:
        rows = _read()
        for r in rows:
            if r["id"] == signup_id:
                r.update(changes)
                _write(rows)
                return r
    raise ValueError(f"Pendaftar {signup_id} tidak ditemukan.")


def approve(signup_id, student_id, by=""):
    return _set(signup_id, status=APPROVED, student=student_id, by=by,
                done_at=datetime.now().strftime(FMT))


def reject(signup_id, by=""):
    return _set(signup_id, status=REJECTED, by=by, done_at=datetime.now().strftime(FMT))


def reopen(signup_id):
    """Batalkan penolakan: kembali menunggu."""
    return _set(signup_id, status=PENDING, by="", done_at="")


def delete(signup_id):
    with _lock:
        rows = _read()
        left = [r for r in rows if r["id"] != signup_id]
        if len(left) == len(rows):
            raise ValueError(f"Pendaftar {signup_id} tidak ditemukan.")
        _write(left)
