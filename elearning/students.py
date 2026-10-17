"""Data siswa.

Daftar murid + kursus yang boleh dibuka disimpan di  data\\students.json
(di samping .exe, atau di folder proyek kalau dijalankan dengan python main.py).
File itu dibuat otomatis dari DEMO_STUDENTS di bawah saat pertama kali dipakai,
lalu diubah lewat layar guru (tombol ON/OFF). Mengubah DEMO_STUDENTS setelah file
itu ada TIDAK berpengaruh; edit data\\students.json atau hapus file itu agar dibuat ulang.

'program'  = "adult" (murid dewasa, ID PB...) atau "kids" (murid anak, ID SK...).
             Menentukan 6 kursus mana yang tampil (lihat courses.py).
'courses'  = id kursus yang boleh dibuka siswa itu. Sisanya tampil abu-abu (terkunci).
'status'   = "active" (boleh login) atau "expired" (tidak bisa login). Diatur admin/guru.
             Data lama tanpa 'status' otomatis dianggap active.
"""

import copy
import json
import os
import re

from elearning import config as C
from elearning import photos, portfolio, sessions
from elearning.courses import COURSES
from elearning.admins import is_admin_id
from elearning.teachers import is_teacher_id
from elearning.trial import TRIAL_ID

ADULT_ALL = ["basic-1", "basic-2", "intermediate-1", "intermediate-2",
             "ai-character", "ai-interior"]
KIDS_ALL = ["superkids-1", "superkids-2", "superkids-3",
            "superkids-4", "superkids-5", "superkids-6"]

DEMO_STUDENTS = {
    # --- Murid dewasa ---
    "PB001": {"name": "Murid Dewasa 1", "program": "adult",
              "courses": ["basic-1", "basic-2"]},
    "PB002": {"name": "Murid Dewasa 2", "program": "adult",
              "courses": ["basic-1", "basic-2", "intermediate-1"]},
    "PB003": {"name": "Murid Dewasa 3", "program": "adult",
              "courses": ADULT_ALL},
    # --- Murid anak / bawah umur ---
    "SK001": {"name": "Murid Anak 1", "program": "kids",
              "courses": ["superkids-1", "superkids-2"]},
    "SK002": {"name": "Murid Anak 2", "program": "kids",
              "courses": ["superkids-1", "superkids-2", "superkids-3"]},
    "SK003": {"name": "Murid Anak 3", "program": "kids",
              "courses": KIDS_ALL},
}

STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
STATUSES = (STATUS_ACTIVE, STATUS_EXPIRED)
STATUS_LABEL = {STATUS_ACTIVE: "Active", STATUS_EXPIRED: "Expired"}

_COURSE_ORDER = {c["id"]: i for i, c in enumerate(COURSES)}

ID_PREFIX = {"adult": "PB", "kids": "SK"}   # awalan ID otomatis murid baru
NAME_MAX = 40
_ID_RE = re.compile(r"^[A-Z0-9_-]{1,20}$")


# --- baca / tulis file --------------------------------------------------------
def _valid(data):
    """Buang entri yang rusak; kembalikan dict bersih atau None kalau bukan dict."""
    if not isinstance(data, dict):
        return None
    clean = {}
    for sid, d in data.items():
        if (isinstance(d, dict) and isinstance(d.get("name"), str)
                and d.get("program") in ("adult", "kids")
                and isinstance(d.get("courses"), list)):
            clean[str(sid).strip().upper()] = {
                "name": d["name"], "program": d["program"],
                "courses": [c for c in d["courses"] if isinstance(c, str)],
                "status": (d.get("status") if d.get("status") in STATUSES
                           else STATUS_ACTIVE)}
    return clean


def _write(data):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = C.STUDENTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, C.STUDENTS_FILE)  # tulis utuh atau tidak sama sekali


_load_cache = {"key": None, "data": None}


def _load():
    """Data murid terbaru. File hanya dibaca ulang kalau berubah (lihat _load_file)."""
    try:
        st = os.stat(C.STUDENTS_FILE)
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        key = None
    if key is not None and key == _load_cache["key"] and _load_cache["data"] is not None:
        return copy.deepcopy(_load_cache["data"])
    data = _load_file()
    try:
        st = os.stat(C.STUDENTS_FILE)
        _load_cache["key"] = (st.st_mtime_ns, st.st_size)
        _load_cache["data"] = copy.deepcopy(data)
    except OSError:
        _load_cache["key"] = None
    return data


def _load_file():
    """Baca data terbaru dari file (dibuat dari data contoh kalau belum ada)."""
    try:
        with open(C.STUDENTS_FILE, encoding="utf-8") as f:
            data = _valid(json.load(f))
        if data is not None:
            return data
        raise ValueError("isi file bukan daftar murid")
    except FileNotFoundError:
        pass
    except Exception as exc:
        # File rusak: simpan salinannya, lalu mulai lagi dari data contoh
        C.log(f"data\\students.json rusak ({exc!r}) -> dibuat ulang dari data contoh")
        try:
            os.replace(C.STUDENTS_FILE, C.STUDENTS_FILE + ".rusak")
        except OSError:
            pass
    data = copy.deepcopy(DEMO_STUDENTS)
    try:
        _write(data)
    except OSError as exc:
        C.log(f"Gagal membuat data\\students.json: {exc!r}")
    return data


# --- dipakai layar lain -------------------------------------------------------
def lookup_student(student_id):
    """Kembalikan {'id','name','program','courses','status'}, atau None kalau ID tidak ada."""
    sid = student_id.strip().upper()
    data = _load().get(sid)
    if data is None:
        return None
    return _entry(sid, data)


def _entry(sid, data):
    return {"id": sid, "name": data["name"], "program": data["program"],
            "courses": list(data["courses"]),
            "status": data.get("status") if data.get("status") in STATUSES
            else STATUS_ACTIVE}


def list_students():
    """Semua murid, urut berdasarkan ID. Data dibaca SEKALI (dulu sekali per murid,
    berat di PC low-end kalau murid ratusan)."""
    data = _load()
    return [_entry(sid, data[sid]) for sid in sorted(data)]


def set_course_access(student_id, course_id, allowed):
    """Buka (True) atau kunci (False) satu kursus untuk satu murid, langsung disimpan.

    Kalau gagal menyimpan, error dilempar (data lama tidak berubah)."""
    sid = student_id.strip().upper()
    data = _load()
    if sid not in data:
        raise KeyError(f"Murid {sid} tidak ditemukan")
    courses = set(data[sid]["courses"])
    if allowed:
        courses.add(course_id)
    else:
        courses.discard(course_id)
    data[sid]["courses"] = sorted(
        courses, key=lambda c: _COURSE_ORDER.get(c, 999))
    _write(data)
    return list(data[sid]["courses"])


def set_status(student_id, status):
    """Ubah status murid: 'active' atau 'expired'. Langsung disimpan.

    Murid expired tidak bisa login. Akses kursus dan riwayatnya tidak berubah,
    jadi kalau diaktifkan lagi semuanya kembali seperti semula.
    Kalau gagal, ValueError (pesan siap tampil) atau OSError dilempar; data lama tidak berubah."""
    if status not in STATUSES:
        raise ValueError("Status harus active atau expired.")
    sid = student_id.strip().upper()
    data = _load()
    if sid not in data:
        raise ValueError(f"Murid {sid} tidak ditemukan.")
    data[sid]["status"] = status
    _write(data)
    return lookup_student(sid)


# --- tambah murid / ubah nama (dipakai layar guru) ----------------------------
def _clean_name(name):
    """Rapikan nama (spasi ganda dibuang). ValueError kalau kosong / terlalu panjang."""
    name = " ".join(str(name).split())
    if not name:
        raise ValueError("Nama belum diisi.")
    if len(name) > NAME_MAX:
        raise ValueError(f"Nama terlalu panjang (maksimal {NAME_MAX} huruf).")
    return name


def next_student_id(program):
    """ID kosong berikutnya, mis. PB004 kalau PB001-PB003 sudah ada."""
    prefix = ID_PREFIX.get(program, "PB")
    used = [int(sid[len(prefix):]) for sid in _load()
            if sid.startswith(prefix) and sid[len(prefix):].isdigit()]
    return f"{prefix}{(max(used) + 1 if used else 1):03d}"


def add_student(name, program, student_id=None):
    """Tambah murid baru; semua kursusnya terkunci dulu (guru yang membuka).

    ID dibuat otomatis kalau student_id kosong. Kalau ada masalah, ValueError
    dilempar dengan pesan yang siap ditampilkan ke guru (data tidak berubah).
    """
    name = _clean_name(name)
    if program not in ID_PREFIX:
        raise ValueError("Pilih kategori murid (dewasa / anak).")
    data = _load()
    sid = (student_id or "").strip().upper() or next_student_id(program)
    if not _ID_RE.match(sid):
        raise ValueError("ID hanya boleh huruf, angka, - atau _ (maksimal 20 karakter).")
    if is_teacher_id(sid):
        raise ValueError("ID tidak boleh diawali GURU (khusus akun guru).")
    if is_admin_id(sid):
        raise ValueError("ID tidak boleh diawali ADMIN (khusus akun admin).")
    if sid.startswith(TRIAL_ID):
        raise ValueError("ID tidak boleh diawali TRIAL (khusus akun trial).")
    if sid in data:
        raise ValueError(f"ID {sid} sudah dipakai murid lain.")
    data[sid] = {"name": name, "program": program, "courses": [],
                 "status": STATUS_ACTIVE}
    _write(data)
    return lookup_student(sid)


def rename_student(student_id, new_name):
    """Ganti nama murid (ID, foto, dan akses kursus tidak berubah)."""
    new_name = _clean_name(new_name)
    sid = student_id.strip().upper()
    data = _load()
    if sid not in data:
        raise ValueError(f"Murid {sid} tidak ditemukan.")
    data[sid]["name"] = new_name
    _write(data)
    return lookup_student(sid)


def reset_progress(student_id):
    """Guru me-reset progres murid: posisi & status video, catatan, emote, jawaban kuis,
    dan semua badge. Akun, akses kursus, foto, portfolio, dan riwayat login TETAP ada."""
    sid = student_id.strip().upper()
    from elearning import achievements, progress
    progress.delete_student(sid)
    for key in [k for k in progress._live if k[0] == sid]:
        progress._live.pop(key, None)
    if os.path.exists(progress._path(sid)):
        raise ValueError("Progres tidak bisa dihapus. Pastikan folder data bisa ditulis.")
    if not achievements.reset(sid):
        raise ValueError("Badge tidak bisa di-reset. Pastikan folder data bisa ditulis.")
    C.log(f"Progres {sid} di-reset oleh guru")


def delete_student(student_id):
    """Hapus akun murid beserta foto, riwayat login, dan portfolio-nya. Tidak bisa dibatalkan."""
    sid = student_id.strip().upper()
    data = _load()
    if sid not in data:
        raise ValueError(f"Murid {sid} tidak ditemukan.")
    del data[sid]
    _write(data)   # akun hilang dulu; kalau langkah di bawah gagal, akun tetap terhapus
    try:
        photos.remove_photo(sid)
    except OSError as exc:
        C.log(f"Foto {sid} tidak bisa dihapus: {exc!r}")
    sessions.delete_student(sid)
    portfolio.delete_student(sid)
    try:   # keluarkan dari semua jadwal kelas
        from elearning import schedule
        schedule.remove_student(sid)
    except Exception as exc:
        C.log(f"Jadwal {sid} tidak bisa diperbarui: {exc!r}")
    try:
        from elearning import progress, quizzes
        progress.delete_student(sid)
        quizzes.remove_student(sid)
    except Exception as exc:
        C.log(f"Progres {sid} tidak terhapus: {exc!r}")
    try:
        from elearning import achievements
        achievements.delete_student(sid)
    except Exception as exc:
        C.log(f"Badge {sid} tidak terhapus: {exc!r}")
