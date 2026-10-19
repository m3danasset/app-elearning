"""Survey murid setelah menyelesaikan BASIC 2 (config.SURVEY_AFTER_COURSE).

Popup English muncul di Dashboard murid (bukan trial) setelah SEMUA video kursus itu ditonton
(progress.completed, sama dengan syarat sertifikat). Isinya: tingkat kesulitan, bagian
tersulit, bagian yang paling disukai, minat lanjutan (game, animasi, iklan, karakter,
interior), catatan. Submit = tidak muncul lagi; Skip = muncul lagi di sesi app berikutnya.
Jawaban di data\\student_surveys.json (daftar), dilihat admin di Analytics + Excel.
Fitur Dev "student_survey" bisa mematikannya.
"""

import json
import os
import threading
from datetime import datetime

from elearning import config as C

FMT = "%Y-%m-%d %H:%M:%S"
LEVELS = (("easy", "Easy", "Mudah"), ("ok", "Just right", "Pas"), ("hard", "Hard", "Sulit"))
INTERESTS = (("game", "Game", "Game"), ("animation", "Animation", "Animasi"),
             ("ads", "Advertising", "Iklan"), ("character", "Character", "Karakter"),
             ("interior", "Interior", "Interior"))
TEXT_MAX = 300
_lock = threading.Lock()
_skipped = set()          # murid yang menekan Skip di sesi app ini (tanya lagi lain kali)


def _path():
    return os.path.join(C.DATA_DIR, "student_surveys.json")


def list_all():
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return [r for r in data if isinstance(r, dict) and r.get("student")] \
            if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _write(items):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path())


def course_id():
    return getattr(C, "SURVEY_AFTER_COURSE", "basic-2")


def answered(sid):
    sid = str(sid).upper()
    return any(r.get("student") == sid and r.get("course") == course_id() for r in list_all())


def course_done(student):
    """True kalau semua video kursus survey sudah ditonton (kursus harus punya video)."""
    from elearning import progress
    from elearning.courses import by_id
    c = by_id(course_id())
    if c is None or c["id"] not in student.get("courses", ()):
        return False
    titles = progress.lesson_titles(c)
    if not titles:
        return False
    recs = progress.load(student["id"]).get("courses", {}).get(c["id"], {})
    return all(progress.completed(recs.get(t, {})) for t in titles)


def due(student):
    """Popup perlu muncul untuk murid ini sekarang?"""
    if not student or student.get("program") == "trial" or not student.get("id"):
        return False
    try:
        from elearning.app_settings import feature
        if not feature("student_survey"):
            return False
    except Exception:
        pass
    sid = student["id"].upper()
    if sid in _skipped or answered(sid):
        return False
    try:
        return course_done(student)
    except Exception as exc:
        C.log(f"Survey murid: cek {sid} gagal: {exc!r}")
        return False


def skip(student):
    _skipped.add(student["id"].upper())


def clean(answers):
    """Periksa jawaban; ValueError (English, layar murid) kalau ada yang wajib kosong."""
    level = answers.get("level")
    if level not in dict((k, v) for k, v, _i in LEVELS):
        raise ValueError("Please choose how BASIC felt for you.")
    interests = [k for k, _e, _i in INTERESTS if k in (answers.get("interests") or ())]
    if not interests:
        raise ValueError("Please pick at least one thing you want to make next.")
    out = {"level": level, "interests": interests}
    for key in ("hardest", "favorite", "note"):
        text = " ".join(str(answers.get(key, "")).split())
        if len(text) > TEXT_MAX:
            raise ValueError(f"Please keep each answer under {TEXT_MAX} characters.")
        out[key] = text
    return out


def add(student, answers):
    rec = dict(clean(answers), student=student["id"].upper(), name=student.get("name", ""),
               program=student.get("program", ""), course=course_id(),
               at=datetime.now().strftime(FMT))
    with _lock:
        items = [r for r in list_all() if not (r.get("student") == rec["student"]
                                                and r.get("course") == rec["course"])]
        items.append(rec)
        _write(items)
    C.log(f"Survey murid: {rec['student']} mengisi survey {rec['course']}")
    return rec


def label(kind, key):
    """Label Indonesia untuk admin / Excel."""
    table = LEVELS if kind == "level" else INTERESTS
    return next((i for k, _e, i in table if k == key), key)


def stats(start=None, end=None, program="all"):
    """Ringkasan untuk Analytics: {count, levels: [(label, n)], interests: [(label, n)],
    latest: [rec]} dalam periode (start / end datetime, end eksklusif)."""
    rows = []
    for r in list_all():
        try:
            at = datetime.strptime(r.get("at", ""), FMT)
        except ValueError:
            continue
        if (start and at < start) or (end and at >= end):
            continue
        if program not in ("all", None) and r.get("program") != program:
            continue
        rows.append(r)
    rows.sort(key=lambda r: r.get("at", ""), reverse=True)
    levels = [(i, sum(1 for r in rows if r.get("level") == k)) for k, _e, i in LEVELS]
    ints = [(i, sum(1 for r in rows if k in (r.get("interests") or ()))) for k, _e, i in INTERESTS]
    ints.sort(key=lambda x: -x[1])
    return {"count": len(rows), "levels": levels, "interests": ints, "latest": rows[:4]}


def delete_student(sid):
    sid = str(sid).upper()
    with _lock:
        items = list_all()
        keep = [r for r in items if r.get("student") != sid]
        if len(keep) != len(items):
            _write(keep)


def change_id(old, new):
    old, new = str(old).upper(), str(new).upper()
    with _lock:
        items = list_all()
        if any(r.get("student") == old for r in items):
            _write([dict(r, student=new) if r.get("student") == old else r for r in items])
