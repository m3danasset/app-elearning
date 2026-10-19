"""Pertanyaan survey yang bisa dibuat / diubah admin (Panel Admin > Survey), English.

Dua survey:
  "student" : survey murid setelah BASIC 2 (student_survey.py), SEMUA pertanyaan bisa diatur.
  "trial"   : survey trial (signups.py). Isian tetap (nama, telepon, umur, ... dipakai saat
              menyetujui pendaftar) tidak bisa diubah; admin menambah PERTANYAAN TAMBAHAN.
Satu pertanyaan: {id, kind "single" | "multi" | "text", text, options [..], required}.
data\\survey_questions.json: {"student": [...], "trial": [...]} (yang belum pernah diatur =
bawaan). Jawaban lama tetap tersimpan walau pertanyaannya dihapus (tidak ikut statistik).
"""

import copy
import json
import os
import re
import threading

from elearning import config as C

SURVEYS = (("student", "Survey murid (setelah BASIC 2)"), ("trial", "Survey trial"))
KINDS = (("single", "Pilih satu"), ("multi", "Pilih banyak"), ("text", "Isian teks"))
TEXT_MAX, OPT_MAX, OPTS_MAX, QUESTIONS_MAX = 150, 40, 8, 15
DEFAULTS = {
    "student": [
        {"id": "level", "kind": "single", "text": "How did BASIC 1 & 2 feel?",
         "options": ["Easy", "Just right", "Hard"], "required": True},
        {"id": "interests", "kind": "multi", "text": "What do you want to make next?",
         "options": ["Game", "Animation", "Advertising", "Character", "Interior"],
         "required": True},
        {"id": "hardest", "kind": "text", "text": "What was the hardest part?",
         "options": [], "required": False},
        {"id": "favorite", "kind": "text", "text": "What did you enjoy the most?",
         "options": [], "required": False},
        {"id": "note", "kind": "text", "text": "Anything else you'd like to tell us?",
         "options": [], "required": False},
    ],
    "trial": [],
}
_lock = threading.Lock()


def _path():
    return os.path.join(C.DATA_DIR, "survey_questions.json")


def _read():
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _clean_q(q):
    if not isinstance(q, dict) or q.get("kind") not in dict(KINDS):
        return None
    text = " ".join(str(q.get("text", "")).split())
    if not text or not re.match(r"^[a-z0-9_]{1,30}$", str(q.get("id", ""))):
        return None
    opts = [" ".join(str(o).split()) for o in (q.get("options") or []) if str(o).strip()]
    return {"id": q["id"], "kind": q["kind"], "text": text,
            "options": opts if q["kind"] != "text" else [], "required": bool(q.get("required"))}


def load(which):
    """Pertanyaan survey (bawaan kalau belum pernah diatur admin)."""
    raw = _read().get(which)
    if not isinstance(raw, list):
        return copy.deepcopy(DEFAULTS.get(which, []))
    return [q for q in map(_clean_q, raw) if q is not None]


def customized(which):
    return isinstance(_read().get(which), list)


def _new_id(text, used):
    base = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:20] or "q"
    qid, n = base, 2
    while qid in used:
        qid, n = f"{base}_{n}", n + 1
    return qid


def check(q, others):
    """Periksa satu pertanyaan dari dialog admin. ValueError (Indonesia, layar admin)."""
    text = " ".join(str(q.get("text", "")).split())
    if not text:
        raise ValueError("Pertanyaan belum diisi.")
    if len(text) > TEXT_MAX:
        raise ValueError(f"Pertanyaan terlalu panjang (maksimal {TEXT_MAX} huruf).")
    kind = q.get("kind")
    if kind not in dict(KINDS):
        raise ValueError("Pilih jenis jawaban.")
    opts = []
    if kind != "text":
        for o in q.get("options") or []:
            o = " ".join(str(o).split())
            if not o:
                continue
            if len(o) > OPT_MAX:
                raise ValueError(f"Pilihan \"{o[:20]}…\" terlalu panjang (maks. {OPT_MAX}).")
            if o.lower() in (x.lower() for x in opts):
                raise ValueError(f"Pilihan \"{o}\" ditulis dua kali.")
            opts.append(o)
        if len(opts) < 2:
            raise ValueError("Isi minimal 2 pilihan jawaban (satu per baris).")
        if len(opts) > OPTS_MAX:
            raise ValueError(f"Maksimal {OPTS_MAX} pilihan.")
    used = {x["id"] for x in others}
    qid = q.get("id") or _new_id(text, used)
    return {"id": qid, "kind": kind, "text": text, "options": opts,
            "required": bool(q.get("required"))}


def save(which, questions):
    if len(questions) > QUESTIONS_MAX:
        raise ValueError(f"Maksimal {QUESTIONS_MAX} pertanyaan.")
    with _lock:
        data = _read()
        data[which] = [q for q in map(_clean_q, questions) if q is not None]
        os.makedirs(C.DATA_DIR, exist_ok=True)
        tmp = _path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _path())


def reset(which):
    with _lock:
        data = _read()
        if data.pop(which, None) is not None:
            tmp = _path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, _path())


def clean_answers(questions, answers):
    """Jawaban dari popup (English): {qid: str | [str]}. ValueError (English) kalau wajib kosong."""
    out = {}
    for q in questions:
        v = answers.get(q["id"])
        if q["kind"] == "multi":
            v = [o for o in q["options"] if o in (v or ())]
            empty = not v
        elif q["kind"] == "single":
            v = v if v in q["options"] else ""
            empty = not v
        else:
            v = " ".join(str(v or "").split())
            if len(v) > 300:
                raise ValueError("Please keep each answer under 300 characters.")
            empty = not v
        if q["required"] and empty:
            raise ValueError(f"Please answer: {q['text']}")
        out[q["id"]] = v
    return out


def tally(questions, records, get):
    """Hitung jawaban pilihan: [(pertanyaan, [(pilihan, n)], jumlah penjawab)].
    get(record) -> {qid: jawaban}."""
    out = []
    for q in questions:
        if q["kind"] == "text":
            continue
        counts = {o: 0 for o in q["options"]}
        n = 0
        for r in records:
            v = get(r).get(q["id"])
            vals = v if isinstance(v, list) else [v] if v else []
            if vals:
                n += 1
            for x in vals:
                if x in counts:
                    counts[x] += 1
        out.append((q, list(counts.items()), n))
    return out
