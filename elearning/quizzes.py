"""Kuis singkat (soal isian) yang ditulis guru, di  data\\quizzes.json.

Satu kuis: {"id", "teacher", "course", "lesson" (judul video), "question",
            "answer" (kunci, boleh kosong), "students" [ID murid], "created", "edited"}
Kunci jawaban boleh berisi beberapa jawaban benar dipisah titik koma, mis. "kubus; cube".
Kalau kunci kosong, jawaban murid disimpan saja dan dinilai guru sendiri.

Kuis muncul untuk murid yang dipilih setelah video itu selesai ditonton. Jawaban disimpan
di file progres murid (progress.py), jadi PC murid tidak pernah menulis file ini.
"""

import json
import os
from datetime import datetime

from elearning import config as C
from elearning import progress

QUIZ_FILE = os.path.join(C.DATA_DIR, "quizzes.json")
FMT = "%Y-%m-%d %H:%M:%S"
QUESTION_MAX = 300
ANSWER_MAX = 120

_cache = {"key": None, "items": []}


def _read():
    try:
        st = os.stat(QUIZ_FILE)
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return []
    if key == _cache["key"]:
        return _cache["items"]
    try:
        with open(QUIZ_FILE, encoding="utf-8") as f:
            data = json.load(f)
        items = [q for q in data if isinstance(q, dict) and isinstance(q.get("id"), str)
                 and isinstance(q.get("question"), str) and isinstance(q.get("students"), list)]
    except Exception as exc:
        C.log(f"data\\quizzes.json tidak terbaca ({exc!r})")
        return _cache["items"]
    _cache["key"], _cache["items"] = key, items
    return items


def _write(items):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = f"{QUIZ_FILE}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    os.replace(tmp, QUIZ_FILE)


def list_quizzes():
    """Semua kuis, terbaru dulu (salinan)."""
    return sorted((dict(q) for q in _read()), key=lambda q: q.get("created", ""), reverse=True)


def _validate(course, lesson, question, answer, students):
    question = " ".join(question.split())
    answer = " ".join(answer.split())
    if not course or not lesson:
        raise ValueError("Pilih kursus dan video.")
    if not question:
        raise ValueError("Tulis pertanyaannya dulu.")
    if len(question) > QUESTION_MAX:
        raise ValueError(f"Pertanyaan maksimal {QUESTION_MAX} huruf.")
    if len(answer) > ANSWER_MAX:
        raise ValueError(f"Kunci jawaban maksimal {ANSWER_MAX} huruf.")
    students = sorted({s.strip().upper() for s in students if s.strip()})
    if not students:
        raise ValueError("Pilih minimal satu murid.")
    return question, answer, students


def add(teacher_id, course, lesson, question, answer, students):
    question, answer, students = _validate(course, lesson, question, answer, students)
    items = [dict(q) for q in _read()]
    now = datetime.now()
    base = now.strftime("Q%Y%m%d%H%M%S")
    qid, n = base, 2
    while any(q["id"] == qid for q in items):
        qid, n = f"{base}-{n}", n + 1
    items.append({"id": qid, "teacher": teacher_id, "course": course, "lesson": lesson,
                  "question": question, "answer": answer, "students": students,
                  "created": now.strftime(FMT), "edited": None})
    _write(items)
    return qid


def update(qid, course, lesson, question, answer, students):
    question, answer, students = _validate(course, lesson, question, answer, students)
    items = [dict(q) for q in _read()]
    for q in items:
        if q["id"] == qid:
            q.update(course=course, lesson=lesson, question=question, answer=answer,
                     students=students, edited=datetime.now().strftime(FMT))
            _write(items)
            return
    raise ValueError("Kuis tidak ditemukan (mungkin sudah dihapus).")


def delete(qid):
    items = [q for q in _read() if q["id"] != qid]
    _write(items)


def _norm(text):
    return " ".join(str(text).lower().replace(".", " ").replace(",", " ").split())


def check(answer, key):
    """True/False kalau ada kunci, None kalau kunci kosong (dinilai guru)."""
    keys = [_norm(k) for k in str(key or "").split(";") if _norm(k)]
    if not keys:
        return None
    return _norm(answer) in keys


def pending(sid, course, lesson):
    """Kuis untuk murid ini di video ini yang belum dijawab."""
    done = progress.answers(sid)
    return [dict(q) for q in _read() if q.get("course") == course and q.get("lesson") == lesson
            and sid in q.get("students", []) and q["id"] not in done]


def for_student(sid):
    """Semua kuis yang diberikan ke murid ini."""
    return [dict(q) for q in _read() if sid in q.get("students", [])]


def remove_student(sid):
    """Murid dihapus: keluarkan dari daftar penerima kuis."""
    try:
        items = [dict(q) for q in _read()]
        changed = False
        for q in items:
            if sid in q["students"]:
                q["students"] = [s for s in q["students"] if s != sid]
                changed = True
        if changed:
            _write(items)
    except Exception as exc:
        C.log(f"Gagal mengeluarkan {sid} dari kuis: {exc!r}")
