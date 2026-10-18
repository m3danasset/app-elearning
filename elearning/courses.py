"""Daftar kursus.

Teks deskripsi di bawah masih CONTOH, silakan ganti sesuai kurikulum.
Urutan di sini = urutan tampil di layar. 'id' dipakai untuk mencocokkan
kursus yang boleh dibuka tiap siswa (lihat students.py).

'program' menentukan siapa yang melihat kursus ini:
  "adult" = murid dewasa (ID PB...)      "kids" = murid anak/bawah umur (ID SK...)
  "trial" = calon murid (ID TRIAL, tanpa PIN; lihat trial.py)
"""

GREEN = "#3fb68b"
BLUE = "#4a90e2"
PURPLE = "#b06bff"
PINK = "#ff5c93"
ORANGE = "#ea7600"

ADULT_COURSES = [
    {"id": "basic-1", "program": "adult", "group": "BASIC", "title": "BASIC 1",
     "desc": "Mengenal antarmuka dan dasar-dasar Blender.",
     "desc_en": "Get to know the Blender interface and basics.", "color": GREEN},
    {"id": "basic-2", "program": "adult", "group": "BASIC", "title": "BASIC 2",
     "desc": "Modeling, material, dan render dasar.",
     "desc_en": "Modeling, materials, and basic rendering.", "color": GREEN},
    {"id": "intermediate-1", "program": "adult", "group": "INTERMEDIATE",
     "title": "INTERMEDIATE 1",
     "desc": "Modeling lanjutan dan pencahayaan.",
     "desc_en": "Advanced modeling and lighting.", "color": BLUE},
    {"id": "intermediate-2", "program": "adult", "group": "INTERMEDIATE",
     "title": "INTERMEDIATE 2",
     "desc": "Animasi dan rigging.",
     "desc_en": "Animation and rigging.", "color": BLUE},
    {"id": "ai-character", "program": "adult", "group": "AI",
     "title": "AI CHARACTER",
     "desc": "Membuat karakter dengan bantuan AI.",
     "desc_en": "Create characters with the help of AI.", "color": PURPLE, "video": False},
    {"id": "ai-interior", "program": "adult", "group": "AI",
     "title": "AI INTERIOR",
     "desc": "Merancang interior dengan bantuan AI.",
     "desc_en": "Design interiors with the help of AI.", "color": PURPLE, "video": False},
]

KIDS_COURSES = [
    {"id": "superkids-1", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 1",
     "desc": "Berkenalan dengan Blender dan membuat bentuk pertama.",
     "desc_en": "Meet Blender and make your first shapes.", "color": PINK},
    {"id": "superkids-2", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 2",
     "desc": "Membuat dan mewarnai objek 3D sederhana.",
     "desc_en": "Make and color simple 3D objects.", "color": PINK},
    {"id": "superkids-3", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 3",
     "desc": "Membuat karakter lucu dari bentuk dasar.",
     "desc_en": "Build cute characters from basic shapes.", "color": PINK},
    {"id": "superkids-4", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 4",
     "desc": "Membangun dunia kecil: rumah, pohon, dan taman.",
     "desc_en": "Build a small world: houses, trees, and parks.", "color": PINK},
    {"id": "superkids-5", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 5",
     "desc": "Menggerakkan karakter dengan animasi sederhana.",
     "desc_en": "Bring characters to life with simple animation.", "color": PINK},
    {"id": "superkids-6", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 6",
     "desc": "Proyek akhir: membuat cerita pendek sendiri.",
     "desc_en": "Final project: make your own short story.", "color": PINK},
]

TRIAL_COURSES = [
    {"id": "trial-animation", "program": "trial", "group": "TRIAL",
     "title": "ANIMATION",
     "desc": "Coba menggerakkan objek 3D pertamamu dengan animasi sederhana.",
     "desc_en": "Try moving your first 3D object with simple animation.",
     "color": ORANGE},
    {"id": "trial-modeling", "program": "trial", "group": "TRIAL",
     "title": "MODELING",
     "desc": "Coba membuat bentuk 3D pertamamu dengan modeling dasar.",
     "desc_en": "Try making your first 3D shape with basic modeling.",
     "color": BLUE},
]

COURSES = ADULT_COURSES + KIDS_COURSES + TRIAL_COURSES


def has_video(course):
    """False untuk kursus tanpa video pelajaran (AI CHARACTER, AI INTERIOR)."""
    return course.get("video", True)


def ai_only(student):
    """True kalau semua kursus yang dibuka murid ini grup AI (config.WEB_AI_GROUPS)."""
    from elearning import config as C
    group = {c["id"]: c.get("group") for c in COURSES}
    opened = [group.get(cid) for cid in (student or {}).get("courses", [])]
    return bool(opened) and all(g in C.WEB_AI_GROUPS for g in opened)


def courses_for(program):
    """Kursus yang tampil untuk program tertentu ("adult" atau "kids")."""
    return [c for c in COURSES if c["program"] == program]


def visible_for(student):
    """Kursus yang TAMPIL di halaman murid ini: kursus programnya, minus yang disembunyikan
    admin (students.json "hidden"). Dibaca ulang dari file supaya perubahan admin langsung
    berlaku tanpa login ulang."""
    hidden = set(student.get("hidden") or ())
    try:
        from elearning.students import lookup_student
        fresh = lookup_student(student["id"]) if student.get("id") else None
        if fresh is not None:
            hidden = set(fresh.get("hidden") or ())
    except Exception:
        pass
    # layar murid: deskripsi English (desc_en), data aslinya tidak diubah
    return [dict(c, desc=c.get("desc_en", c["desc"]))
            for c in courses_for(student["program"]) if c["id"] not in hidden]
