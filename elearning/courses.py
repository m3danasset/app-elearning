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

# --- kursus diatur dari jendela Dev (kurikulum berganti) ------------------------------
# Daftar di atas = BAWAAN. Begitu Dev membuat / mengubah / menghapus / mengurutkan kursus,
# SELURUH daftar disimpan di data\courses.json dan dipakai menggantikan bawaan. COURSES
# diubah DI TEMPAT (list yang sama), jadi semua modul yang sudah mengimpornya ikut baru.
# Data murid (progres, badge, portfolio, video di assets\lessons\<id>) tidak pernah
# dihapus bersama kursus: buat lagi kursus ber-ID sama = semuanya kembali.
import copy as _copy  # noqa: E402
import json as _json  # noqa: E402
import os as _os  # noqa: E402
import re as _re  # noqa: E402

BUILTIN = _copy.deepcopy(COURSES)
PROGRAMS = (("adult", "Dewasa"), ("kids", "SUPERKIDS"), ("trial", "Trial"))
COLORS = (("green", GREEN, "Hijau"), ("blue", BLUE, "Biru"), ("purple", PURPLE, "Ungu"),
          ("pink", PINK, "Merah muda"), ("orange", ORANGE, "Oranye"),
          ("teal", "#2bb3c0", "Toska"), ("yellow", "#e0b419", "Kuning"),
          ("red", "#e5534b", "Merah"))
TITLE_MAX, DESC_MAX, ID_MAX = 30, 120, 30
_ID_RE = _re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_HEX_RE = _re.compile(r"^#[0-9a-fA-F]{6}$")
_order = {}


def _path():
    from elearning import config as C
    return _os.path.join(C.DATA_DIR, "courses.json")


def _clean(c):
    """Satu kursus dari file: dict rapi, atau None kalau rusak."""
    if not isinstance(c, dict):
        return None
    cid, title = c.get("id"), c.get("title")
    if not (isinstance(cid, str) and _ID_RE.match(cid) and isinstance(title, str) and title):
        return None
    if c.get("program") not in dict(PROGRAMS):
        return None
    out = {"id": cid, "program": c["program"], "group": str(c.get("group") or title),
           "title": title, "desc": str(c.get("desc") or ""),
           "desc_en": str(c.get("desc_en") or c.get("desc") or ""),
           "color": c["color"] if _HEX_RE.match(str(c.get("color", ""))) else BLUE}
    if c.get("video") is False:
        out["video"] = False
    return out


def _apply(items):
    COURSES[:] = items
    _order.clear()
    _order.update({c["id"]: i for i, c in enumerate(COURSES)})


def reload():
    """Baca data\\courses.json (kalau ada) ke COURSES. Tidak ada / rusak = bawaan."""
    items = None
    try:
        with open(_path(), encoding="utf-8") as f:
            data = _json.load(f)
        raw = data.get("courses") if isinstance(data, dict) else None
        if isinstance(raw, list):
            seen, items = set(), []
            for c in map(_clean, raw):
                if c is not None and c["id"] not in seen:
                    seen.add(c["id"])
                    items.append(c)
    except FileNotFoundError:
        pass
    except Exception as exc:
        try:
            from elearning import config as C
            C.log(f"data\\courses.json tidak terbaca ({exc!r}) -> kursus bawaan")
        except Exception:
            pass
    _apply(items if items is not None else _copy.deepcopy(BUILTIN))


def customized():
    """True kalau daftar kursus sudah diatur Dev (bukan bawaan)."""
    return _os.path.exists(_path())


def _save(items):
    """Simpan seluruh daftar (tulis utuh atau tidak sama sekali), lalu langsung dipakai."""
    from elearning import config as C
    _os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        _json.dump({"v": 1, "courses": items}, f, ensure_ascii=False, indent=2)
    _os.replace(tmp, _path())
    _apply(items)


def reset_builtin():
    """Kembali ke daftar bawaan (data\\courses.json dihapus)."""
    try:
        _os.remove(_path())
    except FileNotFoundError:
        pass
    _apply(_copy.deepcopy(BUILTIN))


def by_id(cid):
    return next((c for c in COURSES if c["id"] == cid), None)


def title_of(cid, default=None):
    c = by_id(cid)
    return c["title"] if c else (cid if default is None else default)


def order_of(cid):
    return _order.get(cid, 999)


def slug(text):
    """"Basic 3: Sculpting" -> "basic-3-sculpting" (saran ID kursus baru)."""
    s = _re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s[:ID_MAX].strip("-")


def _check(spec, new):
    """Periksa isian kursus; ValueError (pesan siap tampil) kalau salah."""
    title = " ".join(str(spec.get("title", "")).split())
    if not title:
        raise ValueError("Judul kursus belum diisi.")
    if len(title) > TITLE_MAX:
        raise ValueError(f"Judul terlalu panjang (maksimal {TITLE_MAX} huruf).")
    cid = str(spec.get("id", "")).strip().lower()
    if new:
        if not cid:
            raise ValueError("ID kursus belum diisi.")
        if len(cid) > ID_MAX or not _ID_RE.match(cid):
            raise ValueError("ID hanya huruf kecil, angka dan tanda - (mis. basic-3).")
        if by_id(cid) is not None:
            raise ValueError(f"ID {cid} sudah dipakai kursus lain.")
    if spec.get("program") not in dict(PROGRAMS):
        raise ValueError("Pilih program kursus.")
    for key, label in (("desc", "Deskripsi"), ("desc_en", "Deskripsi English")):
        if len(str(spec.get(key, ""))) > DESC_MAX:
            raise ValueError(f"{label} terlalu panjang (maksimal {DESC_MAX} huruf).")
    color = str(spec.get("color", ""))
    if not _HEX_RE.match(color):
        raise ValueError("Pilih warna kursus.")
    out = {"id": cid, "program": spec["program"],
           "group": " ".join(str(spec.get("group") or "").split()).upper() or title.upper(),
           "title": title, "desc": " ".join(str(spec.get("desc", "")).split()),
           "desc_en": " ".join(str(spec.get("desc_en", "")).split()), "color": color}
    if not out["desc_en"]:
        out["desc_en"] = out["desc"]
    if spec.get("video") is False:
        out["video"] = False
    return out


def add_course(spec):
    """Kursus baru di akhir programnya. Kembalikan kursus itu."""
    c = _check(spec, new=True)
    items = _copy.deepcopy(COURSES)
    last = max((i for i, x in enumerate(items) if x["program"] == c["program"]), default=None)
    items.insert(len(items) if last is None else last + 1, c)
    _save(items)
    _make_folder(c)
    return c


def update_course(cid, spec):
    """Ubah judul, grup, deskripsi, warna, video. ID & program tetap."""
    items = _copy.deepcopy(COURSES)
    for i, x in enumerate(items):
        if x["id"] == cid:
            c = _check(dict(spec, id=cid, program=x["program"]), new=False)
            items[i] = c
            _save(items)
            _make_folder(c)
            return c
    raise ValueError("Kursus tidak ditemukan.")


def delete_course(cid):
    items = [x for x in COURSES if x["id"] != cid]
    if len(items) == len(COURSES):
        raise ValueError("Kursus tidak ditemukan.")
    _save(_copy.deepcopy(items))


def move_course(cid, step):
    """Geser kursus ke atas (-1) / bawah (+1) di antara kursus program yang sama."""
    items = _copy.deepcopy(COURSES)
    idx = next((i for i, x in enumerate(items) if x["id"] == cid), None)
    if idx is None:
        return False
    same = [i for i, x in enumerate(items) if x["program"] == items[idx]["program"]]
    pos = same.index(idx) + step
    if not 0 <= pos < len(same):
        return False
    j = same[pos]
    items[idx], items[j] = items[j], items[idx]
    _save(items)
    return True


def removed_builtins():
    """Kursus bawaan yang sudah dihapus Dev (bisa dipulihkan)."""
    have = {c["id"] for c in COURSES}
    return [c for c in BUILTIN if c["id"] not in have]


def restore_builtin(cid):
    c = next((x for x in BUILTIN if x["id"] == cid), None)
    if c is None or by_id(cid) is not None:
        raise ValueError("Kursus bawaan tidak ditemukan.")
    items = _copy.deepcopy(COURSES)
    before = {x["id"] for x in BUILTIN[:BUILTIN.index(c)]}     # sedekat mungkin ke posisi asal
    pos = max((i + 1 for i, x in enumerate(items) if x["id"] in before), default=0)
    items.insert(pos, _copy.deepcopy(c))
    _save(items)
    return c


def lesson_dir(course):
    """Folder video kursus (yang sudah ada, termasuk folder bernama judul)."""
    from elearning import lessons
    return lessons.lesson_folder(course)


def _make_folder(course):
    """Folder video kursus baru (assets\\lessons\\<id>) supaya studio tinggal mengisi."""
    if course.get("video") is False:
        return
    try:
        if not _os.path.isdir(lesson_dir(course)):
            _os.makedirs(lesson_dir(course), exist_ok=True)
    except Exception:
        pass


reload()


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
