"""Perhitungan untuk halaman Analytics di Panel Admin (hanya membaca data, tidak mengubah).

Sumber: data\\sessions.json (masuk/keluar murid & guru), folder portfolio, laporan guru,
dan data murid (status akun, kursus yang dibuka).

compute(period, program) -> dict siap tampil:
  period : "7d", "30d", "90d" atau "all"
  program: "all", "adult" atau "kids"
"""

from datetime import date, datetime, timedelta

from elearning import config as C
from elearning import portfolio, reports, sessions
from elearning import teachers as T
from elearning.courses import courses_for
from elearning.students import STATUS_EXPIRED, list_students

PERIODS = (("7d", "7 hari", 7), ("30d", "30 hari", 30), ("90d", "3 bulan", 90),
           ("all", "Semua", None))
PROGRAMS = (("all", "Semua program"), ("adult", "Murid dewasa"), ("kids", "Murid anak"))
HEAT_HOURS = range(8, 22)      # jam yang ditampilkan di peta jam ramai (08.00 - 21.59)
INACTIVE_DAYS = 14             # murid dianggap perlu diperhatikan kalau tidak login selama ini
TOP_N = 10

DAY_SHORT = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


# --- bantuan ---------------------------------------------------------------------
def _sessions(since=None):
    """Sesi sejak 'since' (None = semua, termasuk arsip): [(id, mulai, selesai)].
    Selesai diperkirakan kalau aplikasi mati. Arsip bulan lebih lama tidak dibuka."""
    out = []
    now = datetime.now()
    for r in sessions.records(since):
        start = sessions._parse(r["in"])
        end = sessions._parse(r.get("out")) if r.get("out") else None
        if end is None:
            end = sessions._parse(r.get("last")) or start
        end = min(end, now)
        if start and end and end > start:
            out.append((r["id"], start, end))
    return out


def _overlap(a0, a1, b0, b1):
    return max(0.0, (min(a1, b1) - max(a0, b0)).total_seconds())


def fmt_hours(seconds):
    h = seconds / 3600.0
    if h >= 100:
        return f"{h:.0f} jam"
    return f"{h:.1f}".replace(".", ",") + " jam"


def _day_label(d):
    return f"{d.day} {MONTHS[d.month - 1]}"


def _buckets(start_day, end_day):
    """Pembagian sumbu waktu grafik: per hari (<= 31 hari) atau per minggu."""
    days = (end_day - start_day).days + 1
    out = []
    if days <= 31:
        for i in range(days):
            d = start_day + timedelta(days=i)
            out.append((d, d + timedelta(days=1), _day_label(d) if days <= 7
                        else str(d.day)))
        return out, "hari"
    d = start_day - timedelta(days=start_day.weekday())   # mulai Senin
    while d <= end_day:
        out.append((d, d + timedelta(days=7), _day_label(d)))
        d += timedelta(days=7)
    return out, "minggu"


def _dt(d):
    return datetime(d.year, d.month, d.day)


# --- utama -------------------------------------------------------------------------
def compute(period="30d", program="all"):
    now = datetime.now()
    today = now.date()
    n_days = dict((k, n) for k, _l, n in PERIODS).get(period, 30)

    all_students = list_students()
    students = [s for s in all_students if program == "all" or s["program"] == program]
    student_ids = {s["id"] for s in students}
    names = {s["id"]: s["name"] for s in all_students}
    teachers = T.list_teachers()
    teacher_ids = {t["id"] for t in teachers}
    # Arsip hanya dibuka sejauh yang dipakai: periode ini + periode pembanding sebelumnya
    sess = _sessions(None if n_days is None else today - timedelta(days=2 * n_days))

    # Portfolio semua murid (terfilter program)
    uploads = []   # (id murid, waktu, jenis, judul kursus)
    for s in students:
        for c in courses_for(s["program"]):
            try:
                for it in portfolio.list_items(s["id"], c["id"]):
                    uploads.append((s["id"], it["added"], it["kind"], c["title"]))
            except Exception as exc:
                C.log(f"Analytics: portfolio {s['id']}/{c['id']} gagal dibaca: {exc!r}")

    # Rentang waktu
    if n_days is None:
        firsts = [st for i, st, _e in sess if i in student_ids]
        firsts += [u[1] for u in uploads]
        start_day = min(firsts).date() if firsts else today - timedelta(days=29)
        start_day = min(start_day, today - timedelta(days=6))
    else:
        start_day = today - timedelta(days=n_days - 1)
    p0, p1 = _dt(start_day), now
    length = p1 - p0
    q0, q1 = p0 - length, p0           # periode sebelumnya (untuk naik/turun %)

    # --- jam belajar ------------------------------------------------------------------
    buckets, unit = _buckets(start_day, today)
    hours = [0.0] * len(buckets)
    total = prev_total = 0.0
    per_student = {}
    per_teacher = {}
    heat = [[0.0] * len(HEAT_HOURS) for _ in range(7)]
    for rid, s0, s1 in sess:
        is_student = rid in student_ids
        is_teacher = rid in teacher_ids
        if not (is_student or is_teacher):
            continue
        sec = _overlap(s0, s1, p0, p1)
        if is_teacher:
            if sec:
                t = per_teacher.setdefault(rid, {"seconds": 0.0, "sessions": 0})
                t["seconds"] += sec
                t["sessions"] += 1
            continue
        prev_total += _overlap(s0, s1, q0, q1)
        if not sec:
            continue
        total += sec
        per_student[rid] = per_student.get(rid, 0.0) + sec
        for i, (b0, b1, _lbl) in enumerate(buckets):
            hours[i] += _overlap(s0, s1, _dt(b0), _dt(b1))
        # peta jam ramai: menit kehadiran per (hari, jam)
        t = max(s0, p0).replace(minute=0, second=0, microsecond=0)
        while t < min(s1, p1):
            nxt = t + timedelta(hours=1)
            if t.hour in HEAT_HOURS:
                heat[t.weekday()][t.hour - HEAT_HOURS.start] += _overlap(s0, s1, t, nxt)
            t = nxt
    weeks = max(1.0, (today - start_day).days / 7.0)
    heat = [[v / 3600.0 / weeks for v in row] for row in heat]   # rata-rata murid hadir

    # --- portfolio ----------------------------------------------------------------------
    pf_img = [0] * len(buckets)
    pf_vid = [0] * len(buckets)
    pf_period = 0
    pf_by_student = {}
    pf_total_by_student = {}
    for sid, when, kind, _title in uploads:
        pf_total_by_student[sid] = pf_total_by_student.get(sid, 0) + 1
        if not (p0 <= when <= p1):
            continue
        pf_period += 1
        pf_by_student[sid] = pf_by_student.get(sid, 0) + 1
        for i, (b0, b1, _lbl) in enumerate(buckets):
            if _dt(b0) <= when < _dt(b1):
                if kind == "video":
                    pf_vid[i] += 1
                else:
                    pf_img[i] += 1
                break
    pf_prev = sum(1 for _s, w, _k, _t in uploads if q0 <= w < q1)

    # --- laporan guru -------------------------------------------------------------------
    try:
        recs = reports.list_reports(None, start_day, today)
    except Exception as exc:
        C.log(f"Analytics: laporan gagal dibaca: {exc!r}")
        recs = []
    rep_by_teacher = {}
    for r in recs:
        rep_by_teacher[r["teacher"]] = rep_by_teacher.get(r["teacher"], 0) + 1

    # --- murid per kursus (kursus yang dibuka, murid aktif) -------------------------------
    programs = ("adult", "kids") if program == "all" else (program,)
    course_rows = []
    for prog in programs:
        for c in courses_for(prog):
            n = sum(1 for s in students if s.get("status") != STATUS_EXPIRED
                    and c["id"] in s["courses"])
            course_rows.append({"title": c["title"], "color": c["color"], "count": n})

    # --- murid yang perlu diperhatikan ----------------------------------------------------
    # login terakhir sepanjang masa (ringkasan arsip sudah diingat, jadi ringan)
    last_seen = {rid: min(st["last_seen"], now) for rid, st in
                 sessions.overview(student_ids).items() if st["last_seen"] is not None}
    attention = []
    for s in students:
        if s.get("status") == STATUS_EXPIRED:
            continue
        reasons = []
        seen = last_seen.get(s["id"])
        if seen is None:
            reasons.append("belum pernah login")
            idle = 10 ** 6
        else:
            idle = (now - seen).days
            if idle >= INACTIVE_DAYS:
                reasons.append(f"tidak login {idle} hari")
        if not pf_total_by_student.get(s["id"]):
            reasons.append("belum pernah upload portfolio")
        if reasons:
            attention.append({"id": s["id"], "name": s["name"], "reason": ", ".join(reasons),
                              "idle": idle})
    attention.sort(key=lambda a: (-a["idle"], a["id"]))

    # --- 10 murid paling rajin -------------------------------------------------------------
    top = sorted(student_ids, key=lambda i: (-per_student.get(i, 0.0),
                                            -pf_by_student.get(i, 0), i))
    top = [{"id": i, "name": names.get(i, i), "seconds": per_student.get(i, 0.0),
            "uploads": pf_by_student.get(i, 0)}
           for i in top if per_student.get(i) or pf_by_student.get(i)][:TOP_N]

    # --- aktivitas guru ----------------------------------------------------------------------
    teacher_rows = [{"id": t["id"], "name": t["name"],
                     "seconds": per_teacher.get(t["id"], {}).get("seconds", 0.0),
                     "sessions": per_teacher.get(t["id"], {}).get("sessions", 0),
                     "reports": rep_by_teacher.get(t["id"], 0)} for t in teachers]
    teacher_rows.sort(key=lambda r: (-r["seconds"], -r["reports"], r["id"]))

    def delta(cur, prev):
        if n_days is None or prev <= 0:
            return None
        return (cur - prev) / prev * 100.0

    active = sum(1 for s in students if s.get("status") != STATUS_EXPIRED)
    return {
        "period_label": dict((k, l) for k, l, _n in PERIODS).get(period, ""),
        "range": (start_day, today),
        "unit": unit,
        "kpi": {
            "active": active,
            "expired": len(students) - active,
            "seconds": total,
            "seconds_delta": delta(total, prev_total),
            "learners": len(per_student),
            "uploads": pf_period,
            "uploads_delta": delta(pf_period, pf_prev),
            "reports": len(recs),
        },
        "hours": {"labels": [b[2] for b in buckets], "values": [h / 3600.0 for h in hours]},
        "heat": heat,
        "portfolio": {"labels": [b[2] for b in buckets], "images": pf_img, "videos": pf_vid},
        "courses": course_rows,
        "attention": attention,
        "top": top,
        "teachers": teacher_rows,
    }
