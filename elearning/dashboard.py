"""Isi Dashboard admin & guru: kartu notifikasi / hal yang perlu dikerjakan.

items(role, user) -> daftar kartu (dihitung di thread; hanya MEMBACA data):
  {"key", "level": "urgent" | "todo" | "info" | "done", "icon", "tag", "title", "body",
   "when", "action", "target"}
  level: urgent = perlu ditindak segera (oranye), todo = sebaiknya dikerjakan hari ini (biru),
         info = keterangan (abu), done = sudah beres (hijau, redup).
  target: menu yang dibuka saat kartu / tombolnya diklik (mis. "signups", "schedule").
Urutan: urgent, todo, info, done.
"""

from datetime import date, datetime, timedelta

from elearning import config as C

LEVEL_ORDER = {"urgent": 0, "todo": 1, "info": 2, "done": 3}
INACTIVE_DAYS = 14          # murid tidak login selama ini -> perlu diperhatikan
NEW_WORK_DAYS = 3           # karya murid "baru" (guru): diunggah dalam sekian hari terakhir
DAYS = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
MONTHS = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
          "September", "Oktober", "November", "Desember")


def today_text(d=None):
    d = d or date.today()
    return f"{DAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1]} {d.year}"


def greeting(now=None):
    h = (now or datetime.now()).hour
    return ("Selamat pagi" if h < 11 else "Selamat siang" if h < 15
            else "Selamat sore" if h < 18 else "Selamat malam")


def ago(t, now=None):
    """'baru saja', '25 menit lalu', '3 jam lalu', 'kemarin', '4 hari lalu'."""
    if t is None:
        return ""
    now = now or datetime.now()
    s = (now - t).total_seconds()
    if s < 90:
        return "baru saja"
    if s < 3600:
        return f"{int(s // 60)} menit lalu"
    if s < 86400 and t.date() == now.date():
        return f"{int(s // 3600)} jam lalu"
    days = (now.date() - t.date()).days
    return "kemarin" if days == 1 else f"{days} hari lalu"


def _names(names, n=3):
    names = [x for x in names if x]
    if len(names) <= n:
        return ", ".join(names)
    return ", ".join(names[:n]) + f" + {len(names) - n} lainnya"


def _dt(text, fmt="%Y-%m-%d %H:%M:%S"):
    try:
        return datetime.strptime(text, fmt)
    except Exception:
        return None


# --- potongan kartu (dipakai admin & guru) ------------------------------------------------
def _certificates(out, now):
    from elearning import certificates
    rows = [r for r in certificates.list_requests() if r.get("status") != certificates.DONE]
    if rows:
        out.append({"key": "certs", "level": "urgent", "icon": "check", "tag": "SERTIFIKAT",
                    "title": f"{len(rows)} permintaan sertifikat menunggu",
                    "body": _names([f"{r.get('name', r.get('student'))} "
                                    f"({r.get('title', r.get('course', ''))})" for r in rows], 2),
                    "when": ago(_dt(rows[0].get("at", "")), now), "action": "Proses",
                    "target": "certificates"})
    else:
        out.append({"key": "certs", "level": "done", "icon": "check", "tag": "SERTIFIKAT",
                    "title": "Tidak ada sertifikat yang menunggu",
                    "body": "Semua permintaan sertifikat sudah diproses.", "when": "",
                    "action": "Lihat", "target": "certificates"})


def _classes_today(out, now, teacher_id=None, names=None, teachers=None):
    from elearning import schedule as SCH
    today = now.date()
    slots = [s for s in SCH.list_slots() if s["day"] == today.weekday()
             and (teacher_id is None or s.get("teacher") == teacher_id)]
    mins = now.hour * 60 + now.minute
    tag = "KELAS SAYA" if teacher_id else "KELAS HARI INI"
    if not slots:
        out.append({"key": "classes", "level": "info", "icon": "clock", "tag": tag,
                    "title": "Tidak ada kelas hari ini",
                    "body": "Jadwal kelas minggu ini bisa dilihat di menu Jadwal.", "when": "",
                    "action": "Buka jadwal", "target": "schedule"})
        return
    running = [s for s in slots if SCH.to_min(s["start"]) <= mins < SCH.to_min(s["end"])]
    upcoming = [s for s in slots if SCH.to_min(s["start"]) > mins]
    n_students = len({sid for s in slots for sid in s["students"]})
    names = names or {}
    teachers = teachers or {}

    def desc(s):
        who = teachers.get(s.get("teacher"), "") if not teacher_id else ""
        bits = [f"{s['start']}–{s['end']}", who, f"{len(s['students'])} murid"]
        return "  ·  ".join(b for b in bits if b)

    if running:
        s = running[0]
        studs = _names([names.get(x, x) for x in s["students"]], 4)
        out.append({"key": "classes", "level": "urgent", "icon": "play", "tag": tag,
                    "title": f"Kelas sedang berjalan  ·  {desc(s)}",
                    "body": studs or "Belum ada murid di jadwal ini.",
                    "when": f"selesai {s['end']}", "action": "Lihat jadwal",
                    "target": "schedule"})
    elif upcoming:
        s = upcoming[0]
        left = SCH.to_min(s["start"]) - mins
        when = f"{left} menit lagi" if left < 60 else f"{left // 60} jam lagi"
        out.append({"key": "classes", "level": "todo", "icon": "clock", "tag": tag,
                    "title": f"Kelas berikutnya {desc(s)}",
                    "body": f"{len(slots)} kelas hari ini  ·  {n_students} murid terjadwal",
                    "when": when, "action": "Lihat jadwal", "target": "schedule"})
    else:
        out.append({"key": "classes", "level": "done", "icon": "clock", "tag": tag,
                    "title": f"Semua {len(slots)} kelas hari ini sudah selesai",
                    "body": f"{n_students} murid terjadwal hari ini.", "when": "",
                    "action": "Lihat jadwal", "target": "schedule"})


def _inactive(out, now, students, stats, target):
    from elearning.students import STATUS_EXPIRED
    idle = []
    for s in students:
        if s.get("status") == STATUS_EXPIRED:
            continue
        seen = (stats.get(s["id"]) or {}).get("last_seen")
        if seen is None or (now - seen).days >= INACTIVE_DAYS:
            idle.append(s["name"])
    if idle:
        out.append({"key": "idle", "level": "todo", "icon": "users", "tag": "PERLU DIPERHATIKAN",
                    "title": f"{len(idle)} murid tidak login ≥ {INACTIVE_DAYS} hari",
                    "body": _names(idle), "when": "", "action": "Lihat murid",
                    "target": target})
    else:
        out.append({"key": "idle", "level": "done", "icon": "users", "tag": "PERLU DIPERHATIKAN",
                    "title": "Semua murid aktif belajar",
                    "body": f"Tidak ada murid yang absen ≥ {INACTIVE_DAYS} hari.", "when": "",
                    "action": "Lihat murid", "target": target})


def _online(out, students, teachers, stats):
    on_s = [s["name"] for s in students if (stats.get(s["id"]) or {}).get("online")]
    on_t = [t["name"] for t in teachers if (stats.get(t["id"]) or {}).get("online")]
    total = len(on_s) + len(on_t)
    out.append({"key": "online", "level": "info", "icon": "activity", "tag": "SEDANG ONLINE",
                "title": f"{total} orang sedang online" if total else "Belum ada yang online",
                "body": _names(on_t + on_s, 4) if total else "Murid & guru yang login tampil di "
                                                               "sini.",
                "when": "sekarang", "action": "Lihat", "target": "students"})


# --- per peran --------------------------------------------------------------------------
def _admin(now):
    from elearning import schedule as SCH
    from elearning import sessions, signups
    from elearning import teachers as T
    from elearning.students import STATUS_EXPIRED, list_students
    students = list_students()
    teachers = T.list_teachers()
    names = {s["id"]: s["name"] for s in students}
    tnames = {t["id"]: t["name"] for t in teachers}
    stats = sessions.overview([s["id"] for s in students] + [t["id"] for t in teachers])
    out = []
    # pendaftar dari trial
    pend = [r for r in signups.list_all() if r.get("status") == signups.PENDING]
    if pend:
        out.append({"key": "signups", "level": "urgent", "icon": "user", "tag": "PENDAFTAR BARU",
                    "title": f"{len(pend)} calon murid menunggu persetujuan",
                    "body": _names([f"{r['name']} ({r.get('age', '?')} th)" for r in pend], 2),
                    "when": ago(_dt(pend[0].get("at", "")), now), "action": "Tinjau",
                    "target": "signups"})
    else:
        out.append({"key": "signups", "level": "done", "icon": "user", "tag": "PENDAFTAR BARU",
                    "title": "Tidak ada pendaftar yang menunggu",
                    "body": "Pendaftar dari survey trial muncul di sini.", "when": "",
                    "action": "Lihat", "target": "signups"})
    _certificates(out, now)
    _classes_today(out, now, names=names, teachers=tnames)
    # murid aktif tanpa jadwal
    placed = {sid for s in SCH.list_slots() for sid in s["students"]}
    free = [s["name"] for s in students if s.get("status") != STATUS_EXPIRED
            and s["id"] not in placed]
    if free:
        out.append({"key": "unscheduled", "level": "todo", "icon": "grid", "tag": "JADWAL",
                    "title": f"{len(free)} murid aktif belum punya jadwal",
                    "body": _names(free), "when": "", "action": "Atur jadwal",
                    "target": "schedule"})
    _inactive(out, now, students, stats, "students")
    # laporan guru hari ini
    from elearning import reports
    recs = reports.list_reports(None, now.date(), now.date())
    wrote = {r["teacher"] for r in recs}
    missing = [t["name"] for t in teachers if t["id"] not in wrote]
    if teachers:
        out.append({"key": "reports", "level": "info" if missing else "done", "icon": "report",
                    "tag": "LAPORAN GURU",
                    "title": f"{len(recs)} laporan masuk hari ini" if recs
                    else "Belum ada laporan guru hari ini",
                    "body": ("Belum menulis: " + _names(missing)) if missing
                    else "Semua guru sudah menulis laporan hari ini.",
                    "when": "", "action": "Baca laporan", "target": "reports"})
    expired = [s["name"] for s in students if s.get("status") == STATUS_EXPIRED]
    if expired:
        out.append({"key": "expired", "level": "info", "icon": "lock", "tag": "AKUN EXPIRED",
                    "title": f"{len(expired)} akun murid expired",
                    "body": _names(expired) + "  ·  perpanjang atau hapus di menu Murid.",
                    "when": "", "action": "Kelola", "target": "students"})
    _online(out, students, teachers, stats)
    return out


def _teacher(now, teacher):
    from elearning import portfolio, reports, sessions
    from elearning import teachers as T
    from elearning.courses import courses_for
    from elearning.students import list_students
    tid = teacher["id"]
    students = list_students()
    names = {s["id"]: s["name"] for s in students}
    stats = sessions.overview([s["id"] for s in students])
    out = []
    _classes_today(out, now, teacher_id=tid, names=names)
    # laporan kerja hari ini
    mine = reports.list_reports(tid, now.date(), now.date())
    if mine:
        out.append({"key": "report", "level": "done", "icon": "report", "tag": "LAPORAN KERJA",
                    "title": f"Laporan hari ini sudah ditulis ({len(mine)})",
                    "body": " ".join(mine[0].get("text", "").split())[:90],
                    "when": "", "action": "Lihat", "target": "reports"})
    else:
        out.append({"key": "report", "level": "todo", "icon": "report", "tag": "LAPORAN KERJA",
                    "title": "Tulis laporan kerja hari ini",
                    "body": "Catat kelas, murid, dan hal penting untuk admin.", "when": "",
                    "action": "Tulis laporan", "target": "reports"})
    _certificates(out, now)
    # karya baru murid (portfolio + assignment beberapa hari terakhir)
    since = now - timedelta(days=NEW_WORK_DAYS)
    fresh = []
    for s in students:
        for c in courses_for(s["program"]):
            for sec in (None, portfolio.ASSIGNMENT):
                try:
                    for it in portfolio.list_items(s["id"], c["id"], sec):
                        if it["added"] >= since:
                            fresh.append((it["added"], s["name"]))
                        else:
                            break      # urut terbaru dulu
                except Exception:
                    pass
    fresh.sort(reverse=True)
    if fresh:
        out.append({"key": "work", "level": "todo", "icon": "image", "tag": "KARYA BARU",
                    "title": f"{len(fresh)} karya baru dari murid",
                    "body": _names(list(dict.fromkeys(n for _t, n in fresh))) +
                    "  ·  beri masukan di menu Murid & Kursus.",
                    "when": ago(fresh[0][0], now), "action": "Lihat karya",
                    "target": "students"})
    else:
        out.append({"key": "work", "level": "info", "icon": "image", "tag": "KARYA BARU",
                    "title": "Belum ada karya baru",
                    "body": f"Portfolio & assignment {NEW_WORK_DAYS} hari terakhir tampil di sini.",
                    "when": "", "action": "Lihat murid", "target": "students"})
    _inactive(out, now, students, stats, "students")
    _online(out, students, [], stats)
    return out


def items(role, user):
    now = datetime.now()
    try:
        out = _admin(now) if role == "admin" else _teacher(now, user)
    except Exception as exc:
        import traceback
        C.log("Dashboard gagal dihitung: " + "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)))
        out = []
    out.sort(key=lambda it: LEVEL_ORDER.get(it["level"], 9))
    return out
