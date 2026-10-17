"""Permintaan sertifikat per kursus.

Murid (bukan trial) bisa menekan "Request Certificate" di halaman Sertifikat sebuah kursus
setelah SEMUA syarat terpenuhi:
- semua video pelajaran kursus itu ditonton (progress.completed: min. 80 % benar-benar
  ditonton, sama dengan badge),
- min. ASSIGNMENT_MIN assignment terupload di kursus itu,
- min. PORTFOLIO_MIN portfolio terupload di kursus itu,
- min. BADGES_MIN badge di kursus itu (badge berlaku per kursus).
Kursus tanpa video (AI CHARACTER / AI INTERIOR) juga tanpa assignment: dua syarat itu
dianggap terpenuhi.

Permintaan disimpan di data\\certificate_requests.json (satu daftar untuk admin & guru):
{id, student, name, program, course, title, at, status: "pending" | "done", done_at, done_by}.
Admin / guru menandai "Selesai" setelah sertifikat diberikan.
"""

import json
import os
import threading
from datetime import datetime

from elearning import achievements, portfolio, progress
from elearning import config as C
from elearning.courses import has_video

ASSIGNMENT_MIN = 5
PORTFOLIO_MIN = 1
BADGES_MIN = 10
PENDING, DONE = "pending", "done"

_lock = threading.Lock()


def _path():
    return os.path.join(C.DATA_DIR, "certificate_requests.json")


def _load():
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return [r for r in data if isinstance(r, dict) and r.get("id")] \
            if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _write(items):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path())      # tulis utuh atau tidak sama sekali


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --- syarat ----------------------------------------------------------------------------
def requirements(student, course):
    """Daftar syarat [(kunci, label, sekarang, target)] + ok (semua terpenuhi)."""
    sid = student["id"]
    items = []
    if has_video(course):
        titles = progress.lesson_titles(course)
        recs = progress.load(sid).get("courses", {}).get(course["id"], {})
        done = sum(1 for t in titles if progress.completed(recs.get(t, {})))
        items.append(("videos", "Watch every video", done, len(titles)))
        n_as = portfolio.count(sid, course["id"], portfolio.ASSIGNMENT)
        items.append(("assignment", f"Upload at least {ASSIGNMENT_MIN} assignments", n_as,
                      ASSIGNMENT_MIN))
    n_pf = portfolio.count(sid, course["id"])
    items.append(("portfolio", f"Upload at least {PORTFOLIO_MIN} portfolio", n_pf,
                  PORTFOLIO_MIN))
    from elearning.app_settings import feature
    if feature("badges"):        # badge dimatikan (Dev): syarat badge tidak dipakai
        n_b = len(achievements.earned(sid, course["id"]))
        items.append(("badges", f"Min. {BADGES_MIN} badges in this course", n_b, BADGES_MIN))
    ok = all(now >= want for _k, _l, now, want in items) and \
        all(want > 0 for k, _l, _n, want in items if k == "videos")
    return items, ok


# --- permintaan ------------------------------------------------------------------------
def request_of(student_id, course_id):
    """Permintaan terakhir murid untuk kursus ini (atau None)."""
    sid = str(student_id).upper()
    found = [r for r in _load() if r.get("student") == sid and r.get("course") == course_id]
    return found[-1] if found else None


def send_request(student, course):
    """Kirim permintaan. ValueError (pesan siap tampil) kalau syarat belum terpenuhi atau
    sudah pernah diminta. OSError kalau gagal menyimpan."""
    _items, ok = requirements(student, course)
    if not ok:
        raise ValueError("Certificate requirements are not complete yet.")
    with _lock:
        items = _load()
        sid = student["id"].upper()
        if any(r.get("student") == sid and r.get("course") == course["id"] for r in items):
            raise ValueError("You already requested a certificate for this course.")
        rec = {"id": f"{sid}-{course['id']}-{datetime.now():%Y%m%d%H%M%S}",
               "student": sid, "name": student.get("name", sid),
               "program": student.get("program", ""), "course": course["id"],
               "title": course["title"], "at": _now(), "status": PENDING}
        items.append(rec)
        _write(items)
    C.log(f"Sertifikat diminta: {sid} {course['id']}")
    return rec


def list_requests():
    """Semua permintaan, yang belum selesai dulu, terbaru dulu."""
    items = _load()
    items.sort(key=lambda r: r.get("at", ""), reverse=True)
    items.sort(key=lambda r: r.get("status") == DONE)
    return items


def pending_count():
    return sum(1 for r in _load() if r.get("status") != DONE)


def set_done(request_id, done=True, by=""):
    """Tandai selesai (sertifikat sudah diberikan) / batalkan tanda selesai."""
    with _lock:
        items = _load()
        for r in items:
            if r.get("id") == request_id:
                r["status"] = DONE if done else PENDING
                if done:
                    r["done_at"], r["done_by"] = _now(), by
                else:
                    r.pop("done_at", None)
                    r.pop("done_by", None)
                _write(items)
                return r
    raise ValueError("Permintaan tidak ditemukan.")


def delete_student(sid):
    """Murid dihapus: permintaannya ikut dihapus."""
    sid = str(sid).upper()
    with _lock:
        items = _load()
        keep = [r for r in items if r.get("student") != sid]
        if len(keep) != len(items):
            _write(keep)
