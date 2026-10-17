"""Perhitungan untuk halaman Analytics di Panel Admin (hanya membaca data, tidak mengubah).

Sumber: data\\sessions.json (masuk/keluar murid & guru), folder portfolio & assignment,
laporan guru, badge murid (data\\achievements), jadwal kelas (data\\schedule.json),
dan data murid (status akun, kursus yang dibuka).

compute(period, program) -> dict siap tampil:
  period : "7d", "30d", "90d" atau "all"
  program: "all", "adult" atau "kids"
"""

from datetime import date, datetime, timedelta

from elearning import config as C
from elearning import achievements, portfolio, reports, schedule, sessions
from elearning import teachers as T
from elearning.courses import courses_for
from elearning.students import STATUS_EXPIRED, list_students

PERIODS = (("7d", "7 hari", 7), ("30d", "30 hari", 30), ("90d", "3 bulan", 90),
           ("all", "Semua", None))
PROGRAMS = (("all", "Semua program"), ("adult", "Murid dewasa"), ("kids", "Murid anak"))
HEAT_HOURS = range(8, 22)      # jam yang ditampilkan di peta jam ramai (08.00 - 21.59)
INACTIVE_DAYS = 14             # murid dianggap perlu diperhatikan kalau tidak login selama ini
TOP_N = 10
PRESENT_MIN = 10               # hadir jadwal = login min. sekian menit di jam jadwal
EARLY_MIN = 15                 # login sedikit sebelum jadwal tetap dihitung hadir
ABSENT_RATE = 0.5              # di bawah ini (min. 2 jadwal) -> "perlu diperhatikan"

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


def _min(hhmm):
    h, m = str(hhmm).split(":")
    return int(h) * 60 + int(m)


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


# --- pendaftar dari trial (survey) -----------------------------------------------
AGE_GROUPS = (("\u2264 8 th", 0, 8), ("9-12 th", 9, 12), ("13-17 th", 13, 17),
              ("18-24 th", 18, 24), ("25+ th", 25, 200))
# kata kunci isian bebas "Tahu dari mana" -> nama sumber (urutan = prioritas)
SOURCES = (("Instagram", ("instagram", "insta", "ig")), ("TikTok", ("tiktok", "tik tok")),
           ("YouTube", ("youtube", "yt")), ("WhatsApp", ("whatsapp", "wa ", "wa")),
           ("Facebook", ("facebook", "fb")), ("Google / web", ("google", "web", "internet",
                                                             "search", "website")),
           ("Teman / keluarga", ("teman", "friend", "keluarga", "family", "saudara",
                                 "parent", "mom", "dad", "ibu", "ayah", "kakak", "relative")),
           ("Sekolah", ("sekolah", "school", "guru", "teacher", "kampus", "campus")),
           ("Brosur / spanduk", ("brosur", "flyer", "spanduk", "banner", "poster")))
INTERESTS = (("Animation", ("anim",)), ("Modeling", ("model",)), ("AI", ("ai ", "ai", "a.i")),
             ("Game", ("game",)), ("Interior", ("interior", "arsitek", "architect")),
             ("Character", ("character", "karakter")))


def _match(text, table, empty):
    t = " " + " ".join(str(text).lower().split()) + " "
    if not t.strip():
        return empty
    for label, keys in table:
        for k in keys:
            k = k.strip()
            if f" {k} " in t or (len(k) > 3 and k in t):
                return label
    return None


def _top(counter, n, other="Lainnya"):
    rows = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(rows) > n:
        rest = sum(v for _k, v in rows[n - 1:])
        rows = rows[:n - 1] + [(other, rest)]
    return rows


def _weeks(start_day, end_day):
    """Per minggu (mulai Senin) - grafik pendaftar: jumlah per hari biasanya kecil, jadi
    dikelompokkan supaya kurvanya terbaca (bukan deretan puncak tipis)."""
    out = []
    d = start_day - timedelta(days=start_day.weekday())
    while d <= end_day:
        out.append((d, d + timedelta(days=7), _day_label(d)))
        d += timedelta(days=7)
    return out


def signup_stats(p0, p1, q0, q1, buckets, compare=True):
    """Statistik pendaftar trial pada periode p0..p1 (q0..q1 = periode sebelumnya)."""
    unit = "hari"
    if (p1.date() - p0.date()).days > 14:
        buckets, unit = _weeks(p0.date(), p1.date()), "minggu"
    from elearning import signups as SU
    try:
        rows = SU.list_all()
    except Exception as exc:
        C.log(f"Analytics: pendaftar gagal dibaca: {exc!r}")
        rows = []

    def at(r, key="at"):
        try:
            return datetime.strptime(r.get(key, ""), SU.FMT)
        except Exception:
            return None

    cur = [r for r in rows if at(r) is not None and p0 <= at(r) <= p1]
    prev = [r for r in rows if at(r) is not None and q0 <= at(r) < q1] if compare else []
    appr = [r for r in cur if r.get("status") == SU.APPROVED]
    prev_appr = [r for r in prev if r.get("status") == SU.APPROVED]

    def delta(c, pv):
        return None if not compare or pv <= 0 else (c - pv) / pv * 100.0

    conv = len(appr) / len(cur) * 100.0 if cur else None
    prev_conv = len(prev_appr) / len(prev) * 100.0 if prev else None
    new = [0] * len(buckets)
    done = [0] * len(buckets)
    for r in rows:
        a, d = at(r), at(r, "done_at") if r.get("status") == SU.APPROVED else None
        for i, (b0, b1, _l) in enumerate(buckets):
            if a is not None and _dt(b0) <= a < _dt(b1):
                new[i] += 1
            if d is not None and _dt(b0) <= d < _dt(b1):
                done[i] += 1
    pending = [r for r in rows if r.get("status") == SU.PENDING]
    oldest = min((at(r) for r in pending if at(r) is not None), default=None)
    ages = [int(r["age"]) for r in cur if str(r.get("age", "")).isdigit()]

    def ages_of(rs):
        out = {}
        for r in rs:
            if str(r.get("age", "")).isdigit():
                a = int(r["age"])
                for label, lo, hi in AGE_GROUPS:
                    if lo <= a <= hi:
                        out[label] = out.get(label, 0) + 1
        return out
    by_age, by_age_appr, by_age_prev = ages_of(cur), ages_of(appr), ages_of(prev)
    age_rows = []
    for label, _lo, _hi in AGE_GROUPS:
        n, a = by_age.get(label, 0), by_age_appr.get(label, 0)
        age_rows.append({"label": label, "n": n, "approved": a,
                         "conv": a / n * 100.0 if n else None,
                         "delta": delta(n, by_age_prev.get(label, 0))})
    src, intr = {}, {}
    for r in cur:
        k = _match(r.get("source", ""), SOURCES, "Tidak diisi") or "Lainnya"
        src[k] = src.get(k, 0) + 1
        raw = " ".join(str(r.get("interest", "")).split())
        k = _match(raw, INTERESTS, "Tidak diisi") or (raw[:24].title() if raw else "Tidak diisi")
        intr[k] = intr.get(k, 0) + 1
    return {
        "total": len(cur), "total_delta": delta(len(cur), len(prev)),
        "approved": len(appr), "approved_delta": delta(len(appr), len(prev_appr)),
        "rejected": sum(1 for r in cur if r.get("status") == SU.REJECTED),
        "conv": conv,
        "conv_delta": (conv - prev_conv) if (compare and conv is not None
                                             and prev_conv is not None) else None,
        "pending": len(pending),
        "oldest_days": (datetime.now() - oldest).days if oldest else None,
        "avg_age": sum(ages) / len(ages) if ages else None,
        "kids_pct": sum(1 for a in ages if a <= 12) / len(ages) * 100.0 if ages else None,
        "series": {"labels": [b[2] for b in buckets], "new": new, "approved": done,
                   "unit": unit},
        "sources": _top(src, 5), "interests": _top(intr, 5),
        "ages": age_rows,
        "recent": [{"name": r.get("name", ""), "age": r.get("age", ""),
                    "interest": r.get("interest", ""), "phone": r.get("phone", ""),
                    "at": r.get("at", "")} for r in pending[:6]],
    }


# --- utama -------------------------------------------------------------------------
def occurrences(slots, by_sid, active_ids, a0, a1):
    """Setiap jadwal yang SUDAH selesai di rentang [a0, a1] (sejak jadwal dibuat), per murid:
    yield (jadwal, tanggal, id murid, hadir?, mulai, selesai). Dipakai Analytics & Excel.
    by_sid: {id murid: [(masuk, keluar), ...]} dari riwayat login."""
    for sl in slots:
        members = [m for m in sl["students"] if m in active_ids]
        if not members:
            continue
        first = a0.date()
        if sl.get("since"):
            try:
                first = max(first, date.fromisoformat(sl["since"]))
            except ValueError:
                pass
        d = first + timedelta(days=(sl["day"] - first.weekday()) % 7)
        sm, em = _min(sl["start"]), _min(sl["end"])
        while d <= a1.date():
            o0 = _dt(d) + timedelta(minutes=sm)
            o1 = _dt(d) + timedelta(minutes=em)
            if o1 > a1:          # jadwal belum selesai: belum dihitung
                break
            if o0 >= a0:
                for m in members:
                    here = any(_overlap(s0, s1, o0 - timedelta(minutes=EARLY_MIN), o1)
                               >= PRESENT_MIN * 60 for s0, s1 in by_sid.get(m, ()))
                    yield sl, d, m, here, o0, o1
            d += timedelta(days=7)


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
    assigns = []   # (id murid, waktu)  hasil render assignment
    for s in students:
        for c in courses_for(s["program"]):
            try:
                for it in portfolio.list_items(s["id"], c["id"]):
                    uploads.append((s["id"], it["added"], it["kind"], c["title"]))
                for it in portfolio.list_items(s["id"], c["id"], portfolio.ASSIGNMENT):
                    assigns.append((s["id"], it["added"]))
            except Exception as exc:
                C.log(f"Analytics: portfolio {s['id']}/{c['id']} gagal dibaca: {exc!r}")

    # Rentang waktu
    if n_days is None:
        firsts = [st for i, st, _e in sess if i in student_ids]
        firsts += [u[1] for u in uploads]
        try:          # pendaftar trial ikut menentukan awal rentang "Semua"
            from elearning import signups as SU
            for r in SU.list_all():
                try:
                    firsts.append(datetime.strptime(r.get("at", ""), SU.FMT))
                except Exception:
                    pass
        except Exception:
            pass
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
    asg = [0] * len(buckets)
    asg_period = 0
    for _sid, when in assigns:
        if not (p0 <= when <= p1):
            continue
        asg_period += 1
        for i, (b0, b1, _lbl) in enumerate(buckets):
            if _dt(b0) <= when < _dt(b1):
                asg[i] += 1
                break
    asg_prev = sum(1 for _s, w in assigns if q0 <= w < q1)

    # --- badge ---------------------------------------------------------------------------
    badge_period = badge_prev = 0
    badge_series = [0] * len(buckets)      # sparkline kartu "Badge didapat"
    badge_count = {}          # id badge -> jumlah murid yang punya (di kursus mana pun)
    badges_by_student = {}    # badge per kursus: dijumlah semua kursus
    for s in students:
        try:
            got = achievements.earned_all(s["id"])
        except Exception as exc:
            C.log(f"Analytics: badge {s['id']} gagal dibaca: {exc!r}")
            got = []
        badges_by_student[s["id"]] = len(got)
        for bid in {b for _cid, b, _t in got}:
            badge_count[bid] = badge_count.get(bid, 0) + 1
        for _cid, bid, t in got:
            try:
                when = datetime.strptime(t, achievements.FMT)
            except Exception:
                continue
            if p0 <= when <= p1:
                badge_period += 1
                for i, (b0, b1, _lbl) in enumerate(buckets):
                    if _dt(b0) <= when < _dt(b1):
                        badge_series[i] += 1
                        break
            elif q0 <= when < q1:
                badge_prev += 1
    badge_rows = sorted(({"title": achievements.BY_ID[b]["name"],
                          "color": achievements.CAT_COLOR.get(achievements.BY_ID[b]["cat"],
                                                              C.ACCENT),
                          "count": n, "text": f"{n} murid"}
                         for b, n in badge_count.items() if b in achievements.BY_ID),
                        key=lambda r: (-r["count"], r["title"]))[:8]

    # --- kehadiran sesuai jadwal ---------------------------------------------------------
    try:
        slots = schedule.list_slots()
    except Exception as exc:
        C.log(f"Analytics: jadwal gagal dibaca: {exc!r}")
        slots = []
    by_sid = {}
    for rid, s0, s1 in sess:
        if rid in student_ids:
            by_sid.setdefault(rid, []).append((s0, s1))
    active_ids = {s["id"] for s in students if s.get("status") != STATUS_EXPIRED}

    def attendance(a0, a1):
        """(hadir, harus hadir, per jadwal {id: [h, n]}, per murid {id: [h, n]})"""
        pres = exp = 0
        per_slot, per_sid = {}, {}
        for sl, _day, m, here, _o0, _o1 in occurrences(slots, by_sid, active_ids, a0, a1):
            exp += 1
            pres += here
            ps = per_slot.setdefault(sl["id"], [0, 0])
            pm = per_sid.setdefault(m, [0, 0])
            ps[1] += 1
            pm[1] += 1
            if here:
                ps[0] += 1
                pm[0] += 1
        return pres, exp, per_slot, per_sid

    att_pres, att_exp, att_slot, att_sid = attendance(p0, p1)
    prev_pres, prev_exp, _ps, _pm = attendance(q0, q1) if n_days is not None else (0, 0, {}, {})
    att_rate = att_pres / att_exp * 100.0 if att_exp else None
    prev_rate = prev_pres / prev_exp * 100.0 if prev_exp else None
    slot_rows = []
    for sl in slots:
        h, n = att_slot.get(sl["id"], (0, 0))
        if not n:
            continue
        rate = h / n
        slot_rows.append({"title": f"{DAY_SHORT[sl['day']]} {sl['start']}–{sl['end']}",
                          "color": C.ON if rate >= 0.75 else (C.ACCENT if rate >= ABSENT_RATE
                                                              else C.ERROR),
                          "count": h, "frac": rate, "text": f"{round(rate * 100)}%  ({h}/{n})"})
    scheduled = {m for sl in slots for m in sl["students"]}

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
        h, n = att_sid.get(s["id"], (0, 0))
        if n >= 2 and h / n < ABSENT_RATE:
            reasons.append(f"hadir jadwal {h}/{n}")
        if slots and s["id"] not in scheduled:
            reasons.append("belum punya jadwal")
        if reasons:
            attention.append({"id": s["id"], "name": s["name"], "reason": ", ".join(reasons),
                              "idle": idle})
    attention.sort(key=lambda a: (-a["idle"], a["id"]))

    # --- 10 murid paling rajin -------------------------------------------------------------
    top = sorted(student_ids, key=lambda i: (-per_student.get(i, 0.0),
                                            -pf_by_student.get(i, 0), i))
    top = [{"id": i, "name": names.get(i, i), "seconds": per_student.get(i, 0.0),
            "uploads": pf_by_student.get(i, 0), "badges": badges_by_student.get(i, 0)}
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
            "assignments": asg_period,
            "assignments_delta": delta(asg_period, asg_prev),
            "badges": badge_period,
            "badges_delta": delta(badge_period, badge_prev),
            "badge_series": badge_series,
            "attendance": att_rate,
            "attendance_delta": (att_rate - prev_rate) if (att_rate is not None
                                                           and prev_rate is not None) else None,
            "attendance_n": (att_pres, att_exp),
            "slots": len(slots),
            "unscheduled": len(active_ids - scheduled),
        },
        "hours": {"labels": [b[2] for b in buckets], "values": [h / 3600.0 for h in hours]},
        "heat": heat,
        "portfolio": {"labels": [b[2] for b in buckets], "images": pf_img, "videos": pf_vid,
                      "assignments": asg},
        "schedule": slot_rows,
        "badges": badge_rows,
        "courses": course_rows,
        "attention": attention,
        "top": top,
        "teachers": teacher_rows,
        "signups": signup_stats(p0, p1, q0, q1, buckets, compare=n_days is not None),
    }
