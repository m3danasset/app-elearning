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


WEEKDAYS = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")


def _categories(students):
    """Murid aktif per label seperti sheet jadwal: PB (dewasa), IC (intermediate), SK (anak)."""
    out = {"PB": 0, "IC": 0, "SK": 0}
    for s in students:
        if s.get("status") == STATUS_EXPIRED:
            continue
        if s["program"] == "kids":
            out["SK"] += 1
        elif any(c.startswith("intermediate") for c in s.get("courses", ())):
            out["IC"] += 1
        else:
            out["PB"] += 1
    return [("Dewasa (PB)", out["PB"]), ("Intermediate (IC)", out["IC"]),
            ("SUPERKIDS (SK)", out["SK"])]


def _tasks(teachers):
    """Sheet laporan guru bulan ini per guru: [{title, done, total, unchecked}]."""
    try:
        from elearning import task_sheet as TS
        month = TS.this_month()
        rows = []
        for t in teachers:
            items = [x for x in TS.items_of(t["id"], month)]
            done = sum(1 for x in items if x.get("done"))
            rows.append({"title": t["name"], "done": done, "total": len(items),
                         "unchecked": sum(1 for x in items if x.get("done")
                                          and not x.get("check"))})
        rows.sort(key=lambda r: (-r["total"], r["title"]))
        return rows
    except Exception as exc:
        C.log(f"Analytics: sheet laporan guru gagal: {exc!r}")
        return []


def _student_survey(p0, p1, program):
    try:
        from elearning import student_survey
        return student_survey.stats(p0, p1, program)
    except Exception as exc:
        C.log(f"Analytics: survey murid gagal: {exc!r}")
        return {"count": 0, "tally": [], "texts": [], "latest": []}


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
        "student_survey": _student_survey(p0, p1, program),
        "categories": _categories(students),
        "weekday": [sum(row) for row in heat],
        "tasks": _tasks(teachers),
        "activity": _activity_totals(students, p0, p1),
    }


# --- Insight (Analytics > Insight): kesimpulan otomatis dari hasil compute() ------------------
# Satu insight = {level good | warn | bad | info, icon, title, body, action, target}. Diurut:
# bad, warn, good, info. Dibuat dari data yang SUDAH dihitung (tanpa membaca file lagi), kecuali
# rekap aktivitas Live Kelas (_activity_totals, ikut compute di thread).
INSIGHT_ORDER = {"bad": 0, "warn": 1, "good": 2, "info": 3}


def _activity_totals(students, p0, p1):
    """Menit per jenis aktivitas (Live Kelas) semua murid dalam periode."""
    try:
        from elearning import presence
    except Exception:
        return {}
    out = {k: 0.0 for k in presence.KINDS}
    days = set()
    for s in students:
        for day, d in presence.activity_days(s["id"]).items():
            try:
                t = datetime.strptime(day, "%Y-%m-%d")
            except ValueError:
                continue
            if (p0 and t < datetime(p0.year, p0.month, p0.day)) or (p1 and t > p1):
                continue
            days.add(day)
            for k in presence.KINDS:
                out[k] += d.get(k, 0) / 60.0
    out["days"] = len(days)
    return out


def _pct(v):
    return f"{abs(v):.0f}%"


def insights(d):
    out = []
    k = d.get("kpi", {})
    add = out.append
    # --- tren belajar --------------------------------------------------------------------
    sd = k.get("seconds_delta")
    if sd is not None and abs(sd) >= 10:
        up = sd > 0
        add({"level": "good" if up else "warn", "icon": "activity",
             "title": f"Jam belajar {'naik' if up else 'turun'} {_pct(sd)}",
             "body": f"{fmt_hours(k.get('seconds', 0))} di {d.get('period_label', '')} "
                     "dibanding periode sebelumnya.",
             "action": "" if up else "Cek murid yang jarang login di bawah.", "target": ""})
    if k.get("learners") is not None and k.get("active"):
        rate = k["learners"] / k["active"]
        if rate < 0.5:
            add({"level": "warn", "icon": "users",
                 "title": (f"Hanya {k['learners']} dari {k['active']} murid aktif belajar"
                           if k["learners"] else "Belum ada murid yang belajar di periode ini"),
                 "body": f"{round(rate * 100)}% murid aktif login di periode ini.",
                 "action": "Hubungi murid yang belum login.", "target": "students"})
    # --- murid perlu perhatian --------------------------------------------------------------
    att = d.get("attention") or []
    if att:
        names = ", ".join(a["name"] for a in att[:5]) + (f" +{len(att) - 5}" if len(att) > 5 else "")
        add({"level": "bad" if len(att) >= 5 else "warn", "icon": "user",
             "title": f"{len(att)} murid perlu diperhatikan",
             "body": names + ".", "action": "Buka daftar murid / hubungi orang tua.",
             "target": "students"})
    if k.get("unscheduled"):
        add({"level": "warn", "icon": "clock",
             "title": f"{k['unscheduled']} murid aktif belum punya jadwal",
             "body": "Murid tanpa jadwal lebih mudah berhenti datang.",
             "action": "Atur jadwal di menu Jadwal.", "target": "schedule"})
    # --- kehadiran jadwal ---------------------------------------------------------------
    att_rate = k.get("attendance")
    if att_rate is not None:
        lvl = "good" if att_rate >= 80 else "warn" if att_rate >= 60 else "bad"
        add({"level": lvl, "icon": "check",
             "title": f"Kehadiran jadwal {att_rate:.0f}%",
             "body": "Hadir = login min. 10 menit di jam jadwal.",
             "action": "" if lvl == "good" else "Lihat jadwal dengan kehadiran terendah.",
             "target": "schedule"})
    low = [r for r in d.get("schedule") or [] if r.get("frac", 1) < 0.5]
    if low:
        add({"level": "bad", "icon": "clock",
             "title": f"{len(low)} jadwal kehadirannya di bawah 50%",
             "body": ", ".join(f"{r['title']} ({r['text'].split()[0]})" for r in low[:4]) + ".",
             "action": "Pertimbangkan pindah jam / gabung kelas.", "target": "schedule"})
    # --- jam ramai ------------------------------------------------------------------------
    heat = d.get("heat") or []
    best = None
    for di, row in enumerate(heat):
        for hi, v in enumerate(row):
            if v > 0 and (best is None or v > best[0]):
                best = (v, di, list(HEAT_HOURS)[hi])
    if best:
        add({"level": "info", "icon": "clock",
             "title": f"Paling ramai: {DAY_SHORT[best[1]]} {best[2]:02d}.00",
             "body": f"Rata-rata {best[0]:.1f} murid login di jam itu.",
             "action": "Pastikan guru & PC cukup di jam ini.", "target": "schedule"})
    # --- kursus -----------------------------------------------------------------------------
    courses = [c for c in d.get("courses") or [] if c.get("count")]
    if courses:
        top_c = max(courses, key=lambda c: c["count"])
        add({"level": "info", "icon": "play", "title": f"Kursus terbanyak: {top_c['title']}",
             "body": f"{top_c['count']} murid membuka kursus ini.", "action": "",
             "target": ""})
    # --- karya & badge ----------------------------------------------------------------------
    ud = k.get("uploads_delta")
    if ud is not None and abs(ud) >= 20:
        add({"level": "good" if ud > 0 else "warn", "icon": "image",
             "title": f"Upload portfolio {'naik' if ud > 0 else 'turun'} {_pct(ud)}",
             "body": f"{k.get('uploads', 0)} file di periode ini.", "action": "", "target": ""})
    if k.get("uploads", 0) == 0 and k.get("learners"):
        add({"level": "warn", "icon": "image", "title": "Belum ada portfolio masuk",
             "body": "Murid belajar tapi belum mengunggah karya.",
             "action": "Ingatkan murid unggah hasil latihan.", "target": ""})
    # --- pendaftar trial --------------------------------------------------------------------
    su = d.get("signups") or {}
    if su.get("pending"):
        old = su.get("oldest_days")
        add({"level": "bad" if (old or 0) >= 3 else "warn", "icon": "user",
             "title": f"{su['pending']} pendaftar trial menunggu",
             "body": (f"Yang paling lama sudah {old} hari." if old else "Belum diproses."),
             "action": "Hubungi & setujui di menu Pendaftar.", "target": "signups"})
    if su.get("conv") is not None and su.get("total", 0) >= 3:
        add({"level": "good" if su["conv"] >= 50 else "info", "icon": "activity",
             "title": f"Konversi trial {su['conv']:.0f}%",
             "body": f"{su.get('approved', 0)} dari {su['total']} pendaftar jadi murid.",
             "action": "", "target": ""})
    if su.get("sources"):
        src = su["sources"][0]
        add({"level": "info", "icon": "search", "title": f"Sumber pendaftar terbanyak: {src[0]}",
             "body": f"{src[1]} pendaftar tahu dari sini.", "action": "Perkuat promosi di sini.",
             "target": ""})
    # --- survey murid -----------------------------------------------------------------------
    ss = d.get("student_survey") or {}
    for q, counts, answered in (ss.get("tally") or [])[:2]:
        if not answered:
            continue
        opt, n = max(counts, key=lambda x: x[1])
        add({"level": "info", "icon": "quiz", "title": f"Survey: \"{opt}\" paling banyak dipilih",
             "body": f"{q['text']}  ·  {n} dari {answered} murid.", "action": "",
             "target": "survey"})
    # --- laporan guru -----------------------------------------------------------------------
    tasks = d.get("tasks") or []
    unc = sum(t.get("unchecked", 0) for t in tasks)
    if unc:
        add({"level": "warn", "icon": "report", "title": f"{unc} tugas guru belum dicek",
             "body": ", ".join(t["title"] for t in tasks if t.get("unchecked")) + ".",
             "action": "Cek di Agenda & Laporan > Laporan guru.", "target": "reports"})
    idle_t = [t["title"] for t in tasks if t.get("total") == 0]
    if idle_t and tasks:
        add({"level": "info", "icon": "report",
             "title": f"{len(idle_t)} guru belum mengisi laporan bulan ini",
             "body": ", ".join(idle_t[:5]) + ".", "action": "", "target": "reports"})
    # --- aktivitas Live Kelas ---------------------------------------------------------------
    act = d.get("activity") or {}
    total = sum(act.get(x, 0) for x in ("video", "blender", "browse", "page", "idle"))
    if total >= 30:
        idle_pct = act.get("idle", 0) / total * 100
        blend_pct = act.get("blender", 0) / total * 100
        add({"level": "good" if blend_pct >= 30 else "info", "icon": "play",
             "title": f"{blend_pct:.0f}% waktu kelas dipakai di Blender",
             "body": f"Video {act.get('video', 0) / total * 100:.0f}%  ·  browsing "
                     f"{act.get('browse', 0) / total * 100:.0f}%  ·  diam {idle_pct:.0f}%  "
                     f"(dari Live Kelas, {act.get('days', 0)} hari).", "action": "",
             "target": "live"})
        if idle_pct >= 25:
            add({"level": "warn", "icon": "clock", "title": f"Murid diam {idle_pct:.0f}% waktu",
                 "body": "Tidak ada input mouse / keyboard >= 5 menit saat app terbuka.",
                 "action": "Pantau di Live Kelas saat kelas berjalan.", "target": "live"})
    out.sort(key=lambda x: INSIGHT_ORDER.get(x["level"], 9))
    return out
