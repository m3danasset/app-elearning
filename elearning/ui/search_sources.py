"""Isi search palette (Ctrl+K) per peran. Lihat format di search_palette.py.

student_sources : murid & trial (layar utama dan layar kursus)
teacher_sources : guru
admin_sources   : admin
"""

import os

from elearning import config as C
from elearning import lessons as L
from elearning.courses import has_video, visible_for
from elearning.trial import is_trial

PROGRAM_LABEL = {"adult": "Murid dewasa", "kids": "Murid anak"}

_lesson_cache = {}   # id kursus -> (waktu ubah folder, [judul])


def lesson_titles(course):
    """Judul video pelajaran (urutan sama dengan lessons.lessons_for, tanpa memindai
    subtitle dan tanpa menulis log, jadi ringan dibuka berkali-kali)."""
    folder = L.lesson_folder(course)
    try:
        mtime = os.path.getmtime(folder)
    except OSError:
        return []
    hit = _lesson_cache.get(course["id"])
    if hit is not None and hit[0] == mtime:
        return hit[1]
    names = sorted(L._videos(folder), key=L._natural_key)
    titles = [os.path.splitext(n)[0] for n in names]
    _lesson_cache[course["id"]] = (mtime, titles)
    return titles


def _student_line(s):
    line = f"{s['id']}  ·  {PROGRAM_LABEL.get(s.get('program'), 'Murid')}"
    if s.get("status") == "expired":
        line += "  ·  expired"
    return line


# --- murid & trial -------------------------------------------------------------------
def student_sources(screen, student):
    app = screen.winfo_toplevel()
    trial = is_trial(student)
    allowed = set(student.get("courses", []))
    courses = visible_for(student)       # kursus yang disembunyikan admin tidak dicari
    items = []
    for c in courses:
        ok = c["id"] in allowed
        items.append({"key": f"course:{c['id']}", "kind": "courses", "title": c["title"],
                      "sub": c.get("desc", "") if ok else "Locked",
                      "words": c.get("group", ""), "dot": c.get("color"),
                      "action": (lambda c=c: app.show_course(student, c)) if ok else None})
    if not trial:
        for c in courses:
            if c["id"] not in allowed or not has_video(c):
                continue
            for i, title in enumerate(lesson_titles(c)):
                items.append({"key": f"lesson:{c['id']}:{title}", "kind": "lessons",
                              "title": title, "sub": c["title"], "icon": "play",
                              "action": lambda c=c, t=title: app.show_course(student, c,
                                                                            lesson=t)})
    actions = [{"title": "Dashboard", "icon": "home", "sub": "All courses",
                "action": lambda: app.show_home(student)}]
    cur = getattr(screen, "course", None)     # badge per kursus: hanya dari layar kursus
    if not trial and cur is not None:
        actions.append({"title": f"Badges  ·  {cur['title']}", "icon": "award",
                        "sub": "Badges earned and still locked in this course",
                        "action": lambda: app.show_badges(student, cur["id"])})
    from elearning import blender_launcher
    from elearning.ui.sidebar import open_blender
    actions.append({"title": f"Open Blender {blender_launcher.VERSION}", "icon": "play",
                    "action": lambda: open_blender(screen.sb)})
    actions.append({"title": "Log out", "icon": "logout", "action": app.logout})

    tabs = [("all", "All"), ("courses", "Courses")]
    if not trial:
        tabs.append(("lessons", "Lessons"))
    tabs.append(("actions", "Actions"))
    return {"user": student["id"], "persist": not trial, "tabs": tabs, "items": items,
            "actions": actions,
            "placeholder": "Search courses or actions" if trial
            else "Search courses, lessons, or actions"}


# --- guru ------------------------------------------------------------------------------
def teacher_sources(screen):
    from elearning.students import list_students
    app = screen.winfo_toplevel()
    items = []
    for s in list_students():
        items.append({"key": f"student:{s['id']}", "kind": "students", "title": s["name"],
                      "sub": _student_line(s), "words": s["id"], "icon": "user",
                      "action": lambda sid=s["id"]: screen.open_student(sid)})
    actions = [
        {"title": "Tambah murid", "icon": "plus", "action": screen._add_student},
        {"title": "Murid & Kursus", "icon": "users",
         "action": lambda: screen._set_view("students")},
        {"title": "Kuis", "icon": "quiz", "action": lambda: screen._set_view("quizzes")},
        {"title": "Bahan dari Guru", "icon": "image",
         "action": lambda: screen._set_view("examples")},
        {"title": "Laporan Kerja", "icon": "report",
         "action": lambda: screen._set_view("reports")},
        {"title": "Jadwal Murid", "icon": "clock", "sub": "Jadwal hari ini (diatur admin)",
         "action": lambda: screen._set_view("schedule")},
        {"title": "Keluar", "icon": "logout", "action": app.logout},
    ]
    return {"user": screen.teacher["id"], "tabs": [("all", "Semua"), ("students", "Murid"),
                                                   ("actions", "Aksi")],
            "items": items, "actions": actions,
            "placeholder": "Cari murid (nama / ID) atau aksi"}


# --- admin -----------------------------------------------------------------------------
def admin_sources(screen):
    from elearning import reports, sessions
    from elearning import teachers as T
    from elearning.students import list_students
    app = screen.winfo_toplevel()
    items = []
    for s in list_students():
        items.append({"key": f"student:{s['id']}", "kind": "students", "title": s["name"],
                      "sub": _student_line(s), "words": s["id"], "icon": "user",
                      "action": lambda sid=s["id"]: screen._show_person(
                          {"id": sid, "tab": "students"})})
    teachers = T.list_teachers()
    names = {t["id"]: t["name"] for t in teachers}
    for t in teachers:
        items.append({"key": f"teacher:{t['id']}", "kind": "teachers", "title": t["name"],
                      "sub": t["id"], "words": t["id"], "icon": "teacher",
                      "action": lambda tid=t["id"]: screen._show_person(
                          {"id": tid, "tab": "teachers"})})
    try:
        rows = reports.list_reports()[:200]
    except Exception as exc:
        C.log(f"Search palette: laporan gagal dibaca: {exc!r}")
        rows = []
    for r in rows:
        text = " ".join(str(r.get("text", "")).split())
        who = names.get(r.get("teacher"), r.get("teacher", ""))
        try:
            day = sessions.format_date(r["day"])
        except Exception:
            day = str(r.get("day", ""))
        items.append({"key": None, "kind": "reports", "title": f"{who}  ·  {day}",
                      "sub": text, "words": text, "icon": "report",
                      "action": screen._open_reports_all})
    actions = [
        {"title": "Analytics", "icon": "activity",
         "action": lambda: screen._set_tab("analytics")},
        {"title": "Murid", "icon": "users", "action": lambda: screen._set_tab("students")},
        {"title": "Guru", "icon": "teacher", "action": lambda: screen._set_tab("teachers")},
        {"title": "Agenda & Laporan", "icon": "report",
         "sub": "Agenda admin + laporan kerja guru",
         "action": lambda: screen._set_tab("reports")},
        {"title": "Jadwal", "icon": "clock", "sub": "Kalender hari & jam murid masuk",
         "action": lambda: screen._set_tab("schedule")},
        {"title": "Tambah murid", "icon": "plus", "action": screen._add_student},
        {"title": "Tambah guru", "icon": "plus", "action": screen._add_teacher_from_nav},
        {"title": "Export Excel", "icon": "download", "action": screen._export},
        {"title": "Impor murid sheet Oktober 2026", "icon": "users",
         "sub": "PB, IC, SK (yang sudah ada dilewati)", "action": screen.import_students},
        {"title": "Impor jadwal sheet Oktober 2026", "icon": "clock",
         "sub": "Sabtu & Minggu (jadwal hasil impor lama diganti)",
         "action": screen.import_schedule},
        {"title": "Muat ulang", "icon": "refresh", "action": screen._reload},
        {"title": "Keluar", "icon": "logout", "action": app.logout},
    ]
    return {"user": screen.admin_id, "tabs": [("all", "Semua"), ("students", "Murid"),
                                              ("teachers", "Guru"), ("reports", "Laporan"),
                                              ("actions", "Aksi")],
            "items": items, "actions": actions,
            "placeholder": "Cari murid, guru, laporan, atau aksi"}
