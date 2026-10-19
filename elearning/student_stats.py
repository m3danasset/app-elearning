"""Angka progres belajar murid untuk widget Dashboard murid (course_dock, English).

compute(student) -> {videos_done, videos_total, badges, portfolio, assignment, week_seconds,
streak}. Dihitung di THREAD (membaca folder video, progres, badge, portfolio, riwayat login).
"""

from datetime import date, datetime, timedelta


def compute(student):
    from elearning import achievements, portfolio, progress, sessions
    from elearning.courses import courses_for, has_video
    sid = student["id"]
    opened = set(student.get("courses") or ())
    hidden = set(student.get("hidden") or ())
    done = total = n_pf = n_as = 0
    recs = progress.load(sid).get("courses", {})
    for c in courses_for(student["program"]):
        if c["id"] not in opened or c["id"] in hidden:
            continue
        if has_video(c):
            titles = progress.lesson_titles(c)
            total += len(titles)
            mine = recs.get(c["id"], {})
            done += sum(1 for t in titles if progress.completed(mine.get(t, {})))
        try:
            n_pf += portfolio.count(sid, c["id"])
            n_as += portfolio.count(sid, c["id"], portfolio.ASSIGNMENT)
        except Exception:
            pass
    try:
        badges = len(achievements.earned_all(sid))
    except Exception:
        badges = 0
    today = date.today()
    monday = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
    week, days = 0, set()
    for e in sessions.entries(sid):
        if e["start"] >= monday:
            week += e["seconds"]
        days.add(e["start"].date())
    streak, d = 0, today
    while d in days:                  # hari belajar berturut-turut sampai hari ini
        streak += 1
        d -= timedelta(days=1)
    return {"videos_done": done, "videos_total": total, "badges": badges, "portfolio": n_pf,
            "assignment": n_as, "week_seconds": week, "streak": streak}


def fmt_time(seconds):
    m = int(seconds // 60)
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m} min"
