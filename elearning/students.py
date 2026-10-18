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
_ID_RE = re.compile(r"^[A-Z0-9_-]{1,10}$")   # maks. 10: kolom ID login juga maks. 10


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
            if _birth_ok(d.get("birth")):      # tanggal lahir (diisi admin), boleh kosong
                clean[str(sid).strip().upper()]["birth"] = d["birth"]
            hidden = d.get("hidden")           # kursus yang disembunyikan admin dari murid
            if isinstance(hidden, list) and hidden:
                clean[str(sid).strip().upper()]["hidden"] = [c for c in hidden
                                                             if isinstance(c, str)]
            pin = d.get("pinterest_limit")     # batas Pinterest khusus murid (diatur guru)
            if isinstance(pin, int) and not isinstance(pin, bool) and -1 <= pin <= 600:
                clean[str(sid).strip().upper()]["pinterest_limit"] = pin
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
            else STATUS_ACTIVE,
            "birth": data.get("birth") or "",
            "hidden": list(data.get("hidden") or []),
            # batas Pinterest per hari (menit) khusus murid ini, diatur guru:
            # None = ikut bawaan (config / Dev), -1 = tanpa batas, 0 = diblokir
            "pinterest_limit": data.get("pinterest_limit")
            if isinstance(data.get("pinterest_limit"), int) else None}


# --- tanggal lahir & umur -------------------------------------------------------------
def _birth_ok(text):
    from datetime import date
    if not isinstance(text, str) or not text:
        return False
    try:
        d = date.fromisoformat(text)
    except ValueError:
        return False
    return date(1900, 1, 1) <= d <= date.today()


def age_of(birth, today=None):
    """Umur (tahun) dari 'YYYY-MM-DD', dihitung dari tanggal hari ini (selalu terbaru).
    None kalau tanggal lahir belum diisi."""
    from datetime import date
    if not _birth_ok(birth):
        return None
    b = date.fromisoformat(birth)
    t = today or date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def age_text(student):
    a = age_of(student.get("birth"))
    return f"{a} tahun" if a is not None else ""


def set_birth(student_id, birth):
    """Admin mengisi tanggal lahir ('YYYY-MM-DD') atau mengosongkannya (None / "")."""
    sid = student_id.strip().upper()
    data = _load()
    if sid not in data:
        raise ValueError(f"Murid {sid} tidak ditemukan.")
    if birth:
        if not _birth_ok(birth):
            raise ValueError("Tanggal lahir tidak benar.")
        data[sid]["birth"] = birth
    else:
        data[sid].pop("birth", None)
    _write(data)
    return lookup_student(sid)


def set_pinterest_limit(student_id, minutes):
    """Guru: batas Pinterest murid ini (menit; None = bawaan, -1 = tanpa batas, 0 = blokir)."""
    sid = student_id.strip().upper()
    data = _load()
    if sid not in data:
        raise ValueError(f"Murid {sid} tidak ditemukan.")
    if minutes is None:
        data[sid].pop("pinterest_limit", None)
    else:
        data[sid]["pinterest_limit"] = max(-1, min(600, int(minutes)))
    _write(data)
    return lookup_student(sid)


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


def set_course_hidden(student_id, course_id, hidden):
    """Sembunyikan (True) / tampilkan (False) satu kursus di halaman murid ini. Langsung
    disimpan. Terpisah dari kunci: kursus tersembunyi tidak tampil sama sekali (terbuka
    maupun terkunci); progres & portfolio murid tetap aman."""
    sid = student_id.strip().upper()
    data = _load()
    if sid not in data:
        raise KeyError(f"Murid {sid} tidak ditemukan")
    hide = set(data[sid].get("hidden") or [])
    if hidden:
        hide.add(course_id)
    else:
        hide.discard(course_id)
    if hide:
        data[sid]["hidden"] = sorted(hide, key=lambda c: _COURSE_ORDER.get(c, 999))
    else:
        data[sid].pop("hidden", None)
    _write(data)
    return list(data[sid].get("hidden") or [])


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
        raise ValueError("ID hanya boleh huruf, angka, - atau _ (maksimal 10 karakter).")
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
    try:
        from elearning import certificates
        certificates.delete_student(sid)
    except Exception as exc:
        C.log(f"Permintaan sertifikat {sid} tidak terhapus: {exc!r}")

# --- jendela Dev: ubah kategori & ID ---------------------------------------------------
def _check_new_id(sid, data):
    if not _ID_RE.match(sid):
        raise ValueError("ID hanya boleh huruf, angka, - atau _ (maksimal 10 karakter).")
    if is_teacher_id(sid):
        raise ValueError("ID tidak boleh diawali GURU (khusus akun guru).")
    if is_admin_id(sid):
        raise ValueError("ID tidak boleh diawali ADMIN (khusus akun admin).")
    if sid.startswith(TRIAL_ID):
        raise ValueError("ID tidak boleh diawali TRIAL (khusus akun trial).")
    if sid in data:
        raise ValueError(f"ID {sid} sudah dipakai murid lain.")


def set_program(student_id, program):
    """Ganti kategori (adult / kids). Kursus yang terbuka disesuaikan: kursus program lama
    dibuang; kalau jadi kosong, kursus pertama program baru dibuka."""
    if program not in ID_PREFIX:
        raise ValueError("Kategori harus dewasa atau anak.")
    sid = student_id.strip().upper()
    data = _load()
    if sid not in data:
        raise ValueError(f"Murid {sid} tidak ditemukan.")
    if data[sid]["program"] == program:
        return lookup_student(sid)
    own = [c["id"] for c in COURSES if c["program"] == program]
    data[sid]["program"] = program
    data[sid]["courses"] = [c for c in data[sid]["courses"] if c in own] or own[:1]
    data[sid].pop("hidden", None)
    _write(data)
    return lookup_student(sid)


def change_id(old_id, new_id):
    """Ganti ID murid BESERTA semua datanya: foto, progres video, badge, portfolio &
    assignment, riwayat login (termasuk arsip), jadwal, kuis, sertifikat, riwayat cari.
    ValueError (pesan siap tampil) kalau ID baru tidak boleh dipakai; data tidak berubah."""
    old = old_id.strip().upper()
    new = new_id.strip().upper()
    if new == old:
        return lookup_student(old)
    data = _load()
    if old not in data:
        raise ValueError(f"Murid {old} tidak ditemukan.")
    _check_new_id(new, data)
    from elearning import achievements, progress
    # folder / file tujuan tidak boleh sudah ada (jangan menimpa data lain)
    moves = [(photos.photo_path(old), photos.photo_path(new)),
             (progress._path(old), progress._path(new)),
             (achievements._path(old), achievements._path(new))]
    for base in (portfolio.root(), portfolio.section_root(portfolio.ASSIGNMENT)):
        moves.append((os.path.join(base, portfolio._safe_id(old)),
                      os.path.join(base, portfolio._safe_id(new))))
    for src, dst in moves:
        if os.path.exists(src) and os.path.exists(dst):
            raise ValueError(f"Data untuk ID {new} sudah ada ({os.path.basename(dst)}).")
    data[new] = data.pop(old)
    _write(data)                     # akun pindah dulu; data di bawah menyusul
    for src, dst in moves:
        try:
            if os.path.exists(src):
                os.replace(src, dst)
        except OSError as exc:
            C.log(f"Ganti ID {old}->{new}: {src!r} tidak bisa dipindah: {exc!r}")
    progress._docs.pop(old, None)
    achievements._cache.pop(old, None)
    _rename_in_records(old, new)
    return lookup_student(new)


def _rename_in_records(old, new):
    """ID lama -> baru di file bersama (riwayat login, jadwal, kuis, sertifikat, recents)."""
    try:
        recs = sessions._read()
        if any(r["id"] == old for r in recs):
            sessions._write([dict(r, id=new) if r["id"] == old else r for r in recs])
        for m in sessions.archive_months():
            a = sessions._archive(m)
            if a is not None and old in a["by_id"]:
                sessions._dump(sessions._archive_path(m),
                               [dict(r, id=new) if r["id"] == old else r for r in a["records"]])
        if sessions._current is not None and sessions._current[0] == old:
            sessions._current = (new,) + tuple(sessions._current[1:])
    except Exception as exc:
        C.log(f"Ganti ID {old}->{new}: riwayat login: {exc!r}")
    try:
        from elearning import schedule
        with schedule._lock:
            slots = schedule._load()
            hit = False
            for sl in slots:
                if old in sl["students"]:
                    sl["students"] = [new if x == old else x for x in sl["students"]]
                    hit = True
            if hit:
                schedule._save(slots)
    except Exception as exc:
        C.log(f"Ganti ID {old}->{new}: jadwal: {exc!r}")
    try:
        from elearning import quizzes
        items = [dict(q) for q in quizzes._read()]
        hit = False
        for q in items:
            if old in q.get("students", []):
                q["students"] = [new if x == old else x for x in q["students"]]
                hit = True
        if hit:
            quizzes._write(items)
    except Exception as exc:
        C.log(f"Ganti ID {old}->{new}: kuis: {exc!r}")
    try:
        from elearning import certificates
        items = certificates._load()
        if any(r.get("student") == old for r in items):
            certificates._write([dict(r, student=new) if r.get("student") == old else r
                                 for r in items])
    except Exception as exc:
        C.log(f"Ganti ID {old}->{new}: sertifikat: {exc!r}")
    try:
        from elearning import recents
        with recents._lock:
            d = recents._load()
            if old in d:
                d[new] = d.pop(old)
                recents._save(d)
    except Exception as exc:
        C.log(f"Ganti ID {old}->{new}: riwayat cari: {exc!r}")
