"""Impor murid dari sheet jadwal "M3DAN STUDIOS ACADEMY - OKTOBER 2026".

Hanya label PB (murid dewasa / basic), IC (intermediate, murid dewasa) dan SK (SUPERKIDS,
murid anak). Label lain di sheet (AC, AI, II, ZB, BA) TIDAK diimpor.
Tanda * dan + di belakang nama di sheet dibuang.

- Berjalan otomatis SEKALI saat admin login (penanda: data\\import_oktober2026.done) dan bisa
  diulang dari Ctrl+K admin ("Impor murid sheet Oktober 2026").
- Aman diulang: murid dengan nama + kategori yang sama tidak ditambah dua kali.
- Murid baru mendapat ID otomatis (PB... / SK...) dan satu kursus awal yang dibuka:
  PB -> BASIC 1, IC -> INTERMEDIATE 1, SK -> SUPERKIDS 1 (guru bisa mengubahnya).
"""

import os

from elearning import config as C

MARKER = os.path.join(C.DATA_DIR, "import_oktober2026.done")

# label -> (program, kursus awal yang dibuka)
LABELS = {"PB": ("adult", "basic-1"), "IC": ("adult", "intermediate-1"),
          "SK": ("kids", "superkids-1")}

ROSTER = {
    "SK": ["Jayden W", "Louis H", "Davon F", "Mike W", "Ethan N", "Darren F", "Michelle",
           "Yara", "Braiden", "Bryan O", "Beverly", "Dave", "Graciella", "Felicia",
           "Abigail C", "Alexander", "Tirsshan", "Nathan", "Nesya", "Jourell", "Jordan",
           "Jacelyn", "Josephine", "Jeanatte"],
    "PB": ["Daffin W", "Hatten", "Lanina", "James", "Brian M", "Eudora", "Feodora",
           "Darrell", "Hazel", "Darren D", "Warren", "Wesley", "Puspa", "Wilson", "Zhenyu",
           "Shanessa", "Evan D"],
    "IC": ["Gavin", "Marcelo", "Steven", "Regina", "Alya", "Celine", "Kenzo", "Phebe",
           "Marvel W", "Richelin", "Chloe", "Jayden", "Jansen", "Alexander"],
}


def _key(name, program):
    return (" ".join(str(name).lower().split()), program)


def import_roster():
    """Tambahkan murid yang belum ada. Mengembalikan (ditambah, sudah ada, gagal)."""
    from elearning.students import add_student, list_students, set_course_access
    existing = {_key(s["name"], s["program"]) for s in list_students()}
    added, skipped, failed = [], 0, []
    for label, names in ROSTER.items():
        program, course = LABELS[label]
        for name in names:
            if _key(name, program) in existing:
                skipped += 1
                continue
            try:
                s = add_student(name, program)
                existing.add(_key(name, program))
                try:
                    set_course_access(s["id"], course, True)
                except Exception as exc:
                    C.log(f"Impor murid: kursus awal {s['id']} gagal: {exc!r}")
                added.append(f"{s['id']} {name} ({label})")
            except Exception as exc:
                C.log(f"Impor murid {label} {name!r} gagal: {exc!r}")
                failed.append(f"{label} {name}")
    C.log(f"Impor murid Oktober 2026: {len(added)} ditambah, {skipped} sudah ada, "
          f"{len(failed)} gagal. " + "; ".join(added))
    return added, skipped, failed


def run_once():
    """Dipanggil saat admin login. None kalau sudah pernah dijalankan."""
    if os.path.exists(MARKER):
        return None
    result = import_roster()
    if not result[2]:
        try:
            os.makedirs(C.DATA_DIR, exist_ok=True)
            with open(MARKER, "w", encoding="utf-8") as f:
                f.write(f"{len(result[0])} murid ditambah\n")
        except OSError as exc:
            C.log(f"Penanda impor murid gagal ditulis: {exc!r}")
    return result


def summary_text(result):
    added, skipped, failed = result
    text = f"Impor murid sheet Oktober 2026: {len(added)} murid baru ditambahkan"
    if skipped:
        text += f", {skipped} sudah ada"
    if failed:
        text += f", {len(failed)} gagal (lihat app.log)"
    return text + ". Kursus awal: PB = BASIC 1, IC = INTERMEDIATE 1, SK = SUPERKIDS 1."


# --- jadwal dari sheet yang sama (Sabtu & Minggu) ------------------------------------------
SCHEDULE_MARKER = os.path.join(C.DATA_DIR, "import_jadwal_oktober2026.done")
NOTE_TAG = "Sheet Okt 2026"       # penanda catatan jadwal hasil impor (dipakai saat impor ulang)
SAT, SUN = 5, 6

# (hari, guru di sheet, label, nama, jam mulai, jam selesai)
SHEET_SCHEDULE = [
    # SABTU
    (SAT, "Michelle", "SK", "Jayden W", 9, 11), (SAT, "Michelle", "SK", "Louis H", 13, 15),
    (SAT, "Michelle", "SK", "Davon F", 15, 17),
    (SAT, "Jackson", "SK", "Mike W", 9, 11), (SAT, "Jackson", "SK", "Ethan N", 14, 15),
    (SAT, "Jackson", "SK", "Darren F", 15, 17),
    (SAT, "Alex", "SK", "Michelle", 9, 11), (SAT, "Alex", "SK", "Yara", 10, 12),
    (SAT, "Alex", "SK", "Yara", 13, 14), (SAT, "Alex", "SK", "Braiden", 13, 15),
    (SAT, "Alex", "SK", "Bryan O", 10, 12), (SAT, "Alex", "SK", "Beverly", 13, 15),
    (SAT, "Alex", "SK", "Dave", 15, 17), (SAT, "Alex", "SK", "Graciella", 9, 11),
    (SAT, "Alex", "IC", "Gavin", 16, 17), (SAT, "Alex", "SK", "Felicia", 9, 11),
    (SAT, "Alex", "PB", "Daffin W", 14, 17),
    (SAT, "Michelle", "SK", "Abigail C", 10, 12), (SAT, "Michelle", "IC", "Marcelo", 13, 15),
    (SAT, "Jackson", "SK", "Alexander", 9, 11), (SAT, "Jackson", "PB", "Hatten", 11, 12),
    (SAT, "Jackson", "IC", "Steven", 14, 17),
    (SAT, "Grace JT", "IC", "Regina", 10, 12), (SAT, "Grace JT", "PB", "Lanina", 13, 15),
    (SAT, "Grace JT", "PB", "James", 15, 17), (SAT, "Grace JT", "IC", "Alya", 9, 12),
    (SAT, "Grace JT", "IC", "Celine", 9, 12), (SAT, "Grace JT", "PB", "Brian M", 13, 15),
    (SAT, "Alex", "IC", "Kenzo", 9, 12), (SAT, "Alex", "PB", "Eudora", 13, 16),
    (SAT, "Grace JT", "PB", "Feodora", 9, 12), (SAT, "Grace JT", "PB", "Darrell", 10, 12),
    (SAT, "Grace JT", "IC", "Phebe", 9, 12), (SAT, "Grace JT", "PB", "Hazel", 13, 15),
    # MINGGU
    (SUN, "Michelle", "SK", "Tirsshan", 9, 11), (SUN, "Michelle", "PB", "Darren D", 13, 14),
    (SUN, "Michelle", "SK", "Nathan", 14, 16),
    (SUN, "Jackson", "SK", "Nesya", 10, 12), (SUN, "Jackson", "PB", "Warren", 13, 14),
    (SUN, "Jackson", "IC", "Marvel W", 14, 16),
    (SUN, "Alex", "PB", "Wesley", 9, 12), (SUN, "Alex", "IC", "Marcelo", 13, 15),
    (SUN, "Alex", "IC", "Richelin", 15, 17), (SUN, "Alex", "PB", "Puspa", 9, 11),
    (SUN, "Alex", "PB", "Hatten", 11, 12), (SUN, "Alex", "PB", "Wilson", 9, 11),
    (SUN, "Alex", "PB", "Zhenyu", 10, 12), (SUN, "Alex", "PB", "Shanessa", 13, 16),
    (SUN, "Alex", "IC", "Chloe", 14, 16),
    (SUN, "Michelle", "IC", "Jayden", 9, 12), (SUN, "Michelle", "SK", "Jourell", 14, 16),
    (SUN, "Jackson", "IC", "Jansen", 9, 12), (SUN, "Jackson", "SK", "Jordan", 14, 16),
    (SUN, "Grace JT", "PB", "Evan D", 10, 12), (SUN, "Grace JT", "IC", "Alexander", 10, 12),
    (SUN, "Alex", "IC", "Gavin", 10, 12), (SUN, "Alex", "IC", "Celine", 10, 12),
    (SUN, "Alex", "IC", "Regina", 10, 12), (SUN, "Alex", "SK", "Jacelyn", 15, 17),
    (SUN, "Alex", "SK", "Josephine", 15, 17), (SUN, "Alex", "SK", "Jeanatte", 15, 17),
]


def import_schedule():
    """Buat jadwal dari sheet: satu jadwal per (hari, jam, guru) berisi murid-muridnya.
    Jadwal hasil impor sebelumnya (catatan berawalan NOTE_TAG) diganti, jadwal buatan admin
    tidak disentuh. Guru dicocokkan dengan nama akun guru; kalau tidak ada, nama guru ditulis
    di catatan. Mengembalikan (jumlah jadwal, jumlah murid, nama yang tidak ditemukan)."""
    from datetime import date
    from elearning import schedule as SCH
    from elearning import teachers as T
    from elearning.students import list_students
    studs = list_students()
    lookup = {}
    for s in studs:
        lookup.setdefault(_key(s["name"], s["program"]), s["id"])
    teachers = T.list_teachers()

    def teacher_id(name):
        n = name.lower().replace(" jt", "").strip()
        for t in teachers:
            if n and n in t["name"].lower():
                return t["id"]
        return ""

    groups, missing = {}, []
    for day, guru, label, name, a, b in SHEET_SCHEDULE:
        sid = lookup.get(_key(name, LABELS[label][0]))
        if sid is None:
            missing.append(f"{label} {name}")
            continue
        g = groups.setdefault((day, a, b, guru), [])
        if sid not in g:
            g.append(sid)
    for sl in SCH.list_slots():                  # impor ulang: ganti hasil impor lama
        if sl["note"].startswith(NOTE_TAG):
            SCH.delete_slot(sl["id"])
    today = date.today().isoformat()
    n_students = set()
    for (day, a, b, guru), sids in sorted(groups.items()):
        tid = teacher_id(guru)
        SCH.save_slot({"day": day, "start": f"{a:02d}:00", "end": f"{b:02d}:00",
                       "teacher": tid, "students": sids, "since": today,
                       "note": f"{NOTE_TAG} · {guru}" if not tid else NOTE_TAG})
        n_students.update(sids)
    C.log(f"Impor jadwal Oktober 2026: {len(groups)} jadwal, {len(n_students)} murid, "
          f"tidak ditemukan: {missing}")
    return len(groups), len(n_students), missing


def run_schedule_once():
    if os.path.exists(SCHEDULE_MARKER):
        return None
    result = import_schedule()
    try:
        with open(SCHEDULE_MARKER, "w", encoding="utf-8") as f:
            f.write(f"{result[0]} jadwal\n")
    except OSError as exc:
        C.log(f"Penanda impor jadwal gagal ditulis: {exc!r}")
    return result


def schedule_text(result):
    n, m, missing = result
    text = f"Impor jadwal sheet Oktober 2026 (Sabtu & Minggu): {n} jadwal, {m} murid."
    if missing:
        text += f" Tidak ditemukan: {', '.join(missing)}."
    return text
