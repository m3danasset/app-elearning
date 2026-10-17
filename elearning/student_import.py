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
