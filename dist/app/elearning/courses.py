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
     "desc": "Mengenal antarmuka dan dasar-dasar Blender.", "color": GREEN},
    {"id": "basic-2", "program": "adult", "group": "BASIC", "title": "BASIC 2",
     "desc": "Modeling, material, dan render dasar.", "color": GREEN},
    {"id": "intermediate-1", "program": "adult", "group": "INTERMEDIATE",
     "title": "INTERMEDIATE 1",
     "desc": "Modeling lanjutan dan pencahayaan.", "color": BLUE},
    {"id": "intermediate-2", "program": "adult", "group": "INTERMEDIATE",
     "title": "INTERMEDIATE 2",
     "desc": "Animasi dan rigging.", "color": BLUE},
    {"id": "ai-character", "program": "adult", "group": "AI",
     "title": "AI CHARACTER",
     "desc": "Membuat karakter dengan bantuan AI.", "color": PURPLE, "video": False},
    {"id": "ai-interior", "program": "adult", "group": "AI",
     "title": "AI INTERIOR",
     "desc": "Merancang interior dengan bantuan AI.", "color": PURPLE, "video": False},
]

KIDS_COURSES = [
    {"id": "superkids-1", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 1",
     "desc": "Berkenalan dengan Blender dan membuat bentuk pertama.", "color": PINK},
    {"id": "superkids-2", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 2",
     "desc": "Membuat dan mewarnai objek 3D sederhana.", "color": PINK},
    {"id": "superkids-3", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 3",
     "desc": "Membuat karakter lucu dari bentuk dasar.", "color": PINK},
    {"id": "superkids-4", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 4",
     "desc": "Membangun dunia kecil: rumah, pohon, dan taman.", "color": PINK},
    {"id": "superkids-5", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 5",
     "desc": "Menggerakkan karakter dengan animasi sederhana.", "color": PINK},
    {"id": "superkids-6", "program": "kids", "group": "SUPERKIDS",
     "title": "SUPERKIDS 6",
     "desc": "Proyek akhir: membuat cerita pendek sendiri.", "color": PINK},
]

TRIAL_COURSES = [
    {"id": "trial-animation", "program": "trial", "group": "TRIAL",
     "title": "ANIMATION",
     "desc": "Coba menggerakkan objek 3D pertamamu dengan animasi sederhana.",
     "color": ORANGE},
    {"id": "trial-modeling", "program": "trial", "group": "TRIAL",
     "title": "MODELING",
     "desc": "Coba membuat bentuk 3D pertamamu dengan modeling dasar.",
     "color": BLUE},
]

COURSES = ADULT_COURSES + KIDS_COURSES + TRIAL_COURSES


def has_video(course):
    """False untuk kursus tanpa video pelajaran (AI CHARACTER, AI INTERIOR)."""
    return course.get("video", True)


def courses_for(program):
    """Kursus yang tampil untuk program tertentu ("adult" atau "kids")."""
    return [c for c in COURSES if c["program"] == program]
