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
    # laporan guru (sheet tugas): tugas selesai yang belum dicek admin
    from elearning import task_sheet as TS
    sm = TS.summary()
    tname = {t["id"]: t["name"] for t in teachers}
    if teachers:
        unc = sm["unchecked"]
        who = sorted({tname.get(x["teacher"], x["teacher"]) for x in unc})
        out.append({"key": "reports", "level": "todo" if unc else "done", "icon": "report",
                    "tag": "LAPORAN GURU",
                    "title": f"{len(unc)} tugas selesai belum dicek" if unc
                    else "Semua tugas selesai sudah dicek",
                    "body": ("Dari: " + _names(who)) if unc else
                    f"{len(sm['open_week']) + len(sm['open_month'])} tugas guru masih berjalan "
                    "bulan ini.",
                    "when": "", "action": "Cek laporan", "target": "reports"})
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
    # laporan kerja (sheet tugas bulan ini)
    from elearning import task_sheet as TS
    sm = TS.summary(tid)
    week = sm["open_week"]
    if not sm["today"]:                      # laporan harian hari ini belum diisi
        out.append({"key": "daily", "level": "todo", "icon": "report", "tag": "LAPORAN HARIAN",
                    "title": "Isi laporan harian hari ini",
                    "body": "Tulis kegiatan kelas hari ini di bagian Laporan Harian.",
                    "when": "", "action": "Buka sheet", "target": "reports"})
    if week:
        out.append({"key": "report", "level": "todo", "icon": "report", "tag": "LAPORAN KERJA",
                    "title": f"{len(week)} tugas minggu ini belum selesai",
                    "body": " · ".join(x["text"] for x in week[:3])[:110],
                    "when": "", "action": "Buka sheet", "target": "reports"})
    elif sm["done"] or sm["open_month"]:
        out.append({"key": "report", "level": "done", "icon": "report", "tag": "LAPORAN KERJA",
                    "title": "Tugas minggu ini sudah selesai",
                    "body": f"{len(sm['done'])} selesai · {len(sm['open_month'])} tugas bulan "
                            "ini berjalan", "when": "", "action": "Lihat", "target": "reports"})
    else:
        out.append({"key": "report", "level": "todo", "icon": "report", "tag": "LAPORAN KERJA",
                    "title": "Isi tugas di laporan kerja",
                    "body": "Tulis tugas minggu ini & bulan ini, centang DONE kalau selesai.",
                    "when": "", "action": "Buka sheet", "target": "reports"})
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


# --- widget atas (dipilih sendiri per akun; maks. 6 x 2) -----------------------------------
# (id, nama di menu tambah, peran yang boleh, menu yang dibuka saat diklik)
WIDGETS = (
    ("clock", "Jam & kelas berikutnya", ("admin", "teacher"), "schedule"),
    ("done", "Progres beres", ("admin", "teacher"), None),
    ("online", "Sedang online", ("admin", "teacher"), "students"),
    ("date", "Kalender", ("admin", "teacher"), "schedule"),
    ("signups", "Pendaftar menunggu", ("admin",), "signups"),
    ("certs", "Sertifikat menunggu", ("admin", "teacher"), "certificates"),
    ("classes", "Kelas hari ini", ("admin", "teacher"), "schedule"),
    ("students", "Murid aktif", ("admin", "teacher"), "students"),
    ("idle", "Murid tidak aktif", ("admin", "teacher"), "students"),
    ("unscheduled", "Murid tanpa jadwal", ("admin",), "schedule"),
    ("reports", "Tugas selesai hari ini", ("admin", "teacher"), "reports"),
    ("work", "Karya baru murid", ("admin", "teacher"), "students"),
)
WIDGET_BY_ID = {w[0]: w for w in WIDGETS}
DEFAULT_WIDGETS = ("clock", "done", "online")
MAX_WIDGETS = 12          # 6 per baris x 2 baris


def widget_choices(role):
    return [w for w in WIDGETS if role in w[2]]


def _widgets_path():
    import os
    return os.path.join(C.DATA_DIR, "dashboard_widgets.json")


def load_slots(uid, role):
    """12 slot widget (6 x 2) akun ini: [id atau None, ...]. Bawaan kalau belum diatur.
    Format lama (daftar id saja) diisi berurutan mulai slot pertama."""
    import json
    ok = {w[0] for w in widget_choices(role)}
    slots = [None] * MAX_WIDGETS
    try:
        with open(_widgets_path(), encoding="utf-8") as f:
            data = json.load(f)
        ids = data.get(str(uid)) if isinstance(data, dict) else None
    except (OSError, ValueError):
        ids = None
    if not isinstance(ids, list):
        ids = list(DEFAULT_WIDGETS)
    seen = set()
    old = None not in ids and len(ids) < MAX_WIDGETS     # format lama: tanpa slot kosong
    for k, wid in enumerate(ids[:MAX_WIDGETS]):
        if wid in ok and wid not in seen:
            seen.add(wid)
            slots[len(seen) - 1 if old else k] = wid
    return slots


def load_widgets(uid, role):
    return [w for w in load_slots(uid, role) if w]


# --- kartu yang ditutup (tombol x di pojok kartu) ---------------------------------------------
# data\dashboard_dismissed.json = {id akun: {key kartu: {"sig": judul + isi, "t": tanggal}}}.
# Kartu tetap tersembunyi selama isinya sama; isinya berubah (mis. 6 -> 7 murid) = muncul lagi.
DISMISS_KEEP_DAYS = 30      # catatan lebih lama dari ini dibuang


def _dismiss_path():
    import os
    return os.path.join(C.DATA_DIR, "dashboard_dismissed.json")


def _sig(it):
    return f"{it.get('title', '')}\n{it.get('body', '')}"


def _read_dismissed():
    import json
    try:
        with open(_dismiss_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_dismissed(data):
    import json
    import os
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = f"{_dismiss_path()}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _dismiss_path())


def visible(uid, cards):
    """(kartu yang tampil, jumlah yang ditutup) untuk akun ini."""
    mine = _read_dismissed().get(str(uid), {})
    shown = [it for it in cards
             if not (it.get("key") in mine and mine[it["key"]].get("sig") == _sig(it))]
    return shown, len(cards) - len(shown)


def dismiss(uid, it):
    """Tutup satu kartu (sampai isinya berubah)."""
    data = _read_dismissed()
    mine = data.setdefault(str(uid), {})
    limit = (date.today() - timedelta(days=DISMISS_KEEP_DAYS)).isoformat()
    for k in [k for k, v in mine.items() if v.get("t", "") < limit]:
        del mine[k]
    mine[it.get("key", "")] = {"sig": _sig(it), "t": date.today().isoformat()}
    try:
        _write_dismissed(data)
    except OSError as exc:
        C.log(f"Dashboard: kartu tidak bisa ditutup: {exc!r}")


def restore_all(uid):
    """Tampilkan lagi semua kartu yang ditutup akun ini."""
    data = _read_dismissed()
    if data.pop(str(uid), None) is not None:
        try:
            _write_dismissed(data)
        except OSError as exc:
            C.log(f"Dashboard: kartu tidak bisa dikembalikan: {exc!r}")


def save_slots(uid, slots):
    import json
    import os
    try:
        with open(_widgets_path(), encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data[str(uid)] = (list(slots) + [None] * MAX_WIDGETS)[:MAX_WIDGETS]
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = _widgets_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _widgets_path())


def info(role, user, widgets=()):
    """Isi widget atas: jumlah online dan kelas berikutnya hari ini (guru: kelas sendiri)."""
    from elearning import schedule as SCH
    from elearning import sessions
    from elearning import teachers as T
    from elearning.students import list_students
    now = datetime.now()
    out = {"online_s": 0, "online_t": 0, "next": None, "classes": 0}
    try:
        studs = [s["id"] for s in list_students()]
        tchs = [t["id"] for t in T.list_teachers()] if role == "admin" else []
        st = sessions.overview(studs + tchs)
        out["online_s"] = sum(1 for i in studs if (st.get(i) or {}).get("online"))
        out["online_t"] = sum(1 for i in tchs if (st.get(i) or {}).get("online"))
        mins = now.hour * 60 + now.minute
        slots = [s for s in SCH.list_slots() if s["day"] == now.weekday()
                 and (role == "admin" or s.get("teacher") == (user or {}).get("id"))]
        out["classes"] = len(slots)
        for s in slots:
            if SCH.to_min(s["end"]) > mins:
                out["next"] = {"start": s["start"], "end": s["end"],
                               "now": SCH.to_min(s["start"]) <= mins,
                               "students": len(s["students"])}
                break
        _widget_counts(out, role, user, set(widgets), now, studs, st)
    except Exception as exc:
        C.log(f"Dashboard: widget gagal dihitung: {exc!r}")
    return out


def _widget_counts(out, role, user, want, now, studs, stats):
    """Angka untuk widget yang dipilih saja (yang berat, mis. karya baru, hanya kalau perlu)."""
    from elearning.students import STATUS_EXPIRED, list_students
    students = list_students()
    if want & {"students", "idle", "unscheduled", "work"}:
        out["active"] = sum(1 for s in students if s.get("status") != STATUS_EXPIRED)
        out["expired"] = len(students) - out["active"]
    if "idle" in want:
        out["idle"] = sum(1 for s in students if s.get("status") != STATUS_EXPIRED and (
            (stats.get(s["id"]) or {}).get("last_seen") is None
            or (now - stats[s["id"]]["last_seen"]).days >= INACTIVE_DAYS))
    if "signups" in want:
        from elearning import signups
        out["signups"] = signups.pending_count()
    if "certs" in want:
        from elearning import certificates
        out["certs"] = certificates.pending_count()
    if want & {"classes", "unscheduled"}:
        from elearning import schedule as SCH
        slots = SCH.list_slots()
        today = [s for s in slots if s["day"] == now.weekday()
                 and (role == "admin" or s.get("teacher") == (user or {}).get("id"))]
        out["classes_students"] = len({x for s in today for x in s["students"]})
        placed = {x for s in slots for x in s["students"]}
        out["unscheduled"] = sum(1 for s in students if s.get("status") != STATUS_EXPIRED
                                 and s["id"] not in placed)
    if "reports" in want:
        from elearning import task_sheet as TS
        tid = None if role == "admin" else (user or {}).get("id")
        out["reports"] = len(TS.summary(tid)["done_today"])
    if "work" in want:
        from elearning import portfolio
        from elearning.courses import courses_for
        since = now - timedelta(days=NEW_WORK_DAYS)
        n = 0
        for s in students:
            for c in courses_for(s["program"]):
                for sec in (None, portfolio.ASSIGNMENT):
                    try:
                        for it in portfolio.list_items(s["id"], c["id"], sec):
                            if it["added"] < since:
                                break
                            n += 1
                    except Exception:
                        pass
        out["work"] = n


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
