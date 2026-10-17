"""Jadwal kelas: hari & jam murid masuk (diatur admin di Panel Admin, tab Jadwal).

Disimpan di data\\schedule.json:
  {"slots": [{"id": "J0001", "day": 0..6 (0 = Senin), "start": "09:00", "end": "11:00",
              "teacher": "GURU001" atau "", "students": ["PB001", ...], "note": ""}]}
Jadwal berulang setiap minggu. Murid boleh ada di beberapa jadwal.
"""

import copy
import json
import os
import threading

from elearning import config as C

SCHEDULE_FILE = os.path.join(C.DATA_DIR, "schedule.json")
DAYS = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
_lock = threading.Lock()
_cache = {"key": None, "data": None}


def to_min(hhmm):
    h, m = str(hhmm).split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _valid(slot):
    try:
        day = int(slot["day"])
        a, b = to_min(slot["start"]), to_min(slot["end"])
    except Exception:
        return None
    if not (0 <= day <= 6 and 0 <= a < b <= 24 * 60):
        return None
    return {"id": str(slot.get("id") or ""), "day": day, "start": to_hhmm(a),
            "end": to_hhmm(b), "teacher": str(slot.get("teacher") or ""),
            "students": [str(s) for s in slot.get("students") or []],
            "note": str(slot.get("note") or "")[:120]}


def _load():
    try:
        st = os.stat(SCHEDULE_FILE)
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return []
    if key == _cache["key"]:
        return copy.deepcopy(_cache["data"])
    try:
        with open(SCHEDULE_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        slots = [s for s in (_valid(x) for x in raw.get("slots", [])) if s is not None]
    except Exception as exc:
        C.log(f"data\\schedule.json rusak, dibaca kosong: {exc!r}")
        slots = []
    _cache["key"], _cache["data"] = key, copy.deepcopy(slots)
    return slots


def _save(slots):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = SCHEDULE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"slots": slots}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SCHEDULE_FILE)   # tulis utuh atau tidak sama sekali


def list_slots():
    """Semua jadwal, urut hari lalu jam mulai."""
    with _lock:
        return sorted(_load(), key=lambda s: (s["day"], s["start"], s["end"]))


def save_slot(slot):
    """Tambah (id kosong) atau ubah jadwal. Mengembalikan jadwal tersimpan.
    ValueError kalau isinya tidak benar."""
    clean = _valid(slot)
    if clean is None:
        raise ValueError("Jam selesai harus setelah jam mulai.")
    with _lock:
        slots = _load()
        if not clean["id"]:
            used = {s["id"] for s in slots}
            n = 1
            while f"J{n:04d}" in used:
                n += 1
            clean["id"] = f"J{n:04d}"
            slots.append(clean)
        else:
            slots = [clean if s["id"] == clean["id"] else s for s in slots]
        _save(slots)
    return clean


def delete_slot(slot_id):
    with _lock:
        _save([s for s in _load() if s["id"] != slot_id])


def remove_student(student_id):
    """Murid dihapus: keluarkan dari semua jadwal."""
    with _lock:
        slots = _load()
        changed = False
        for s in slots:
            if student_id in s["students"]:
                s["students"].remove(student_id)
                changed = True
        if changed:
            _save(slots)


def slots_for(student_id):
    return [s for s in list_slots() if student_id in s["students"]]
