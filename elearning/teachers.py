"""Akun guru.

Daftar guru disimpan di  data\\teachers.json  (di samping .exe), jadi aman saat
update.bat dijalankan. Admin menambah, mengubah (nama / PIN / foto) dan menghapus
guru lewat Panel Admin, tab Guru. File itu dibuat otomatis dari DEFAULT_TEACHERS
saat pertama kali dipakai; mengubah DEFAULT_TEACHERS sesudahnya TIDAK berpengaruh.

Login guru hanya untuk masuk ke layar guru, bukan keamanan tingkat tinggi
(PIN tersimpan apa adanya di file itu). Foto guru disimpan di data\\photos\\<ID>.png,
sama seperti foto murid (ID guru selalu diawali GURU, jadi tidak pernah bentrok).
"""

import copy
import hmac
import json
import os
import re

from elearning import config as C
from elearning import photos, sessions

DEFAULT_TEACHERS = {
    "GURU001": {"name": "Guru 1", "pin": "guru123"},
}

PREFIX = "GURU"
NAME_MAX = 40
PIN_MIN, PIN_MAX = 4, 10   # maks. 10: kolom PIN di layar login juga maks. 10
_NUM_RE = re.compile(r"^GURU(\d+)$")


def is_teacher_id(user_id):
    """True kalau ID diawali 'GURU' (ID murid tidak pernah diawali ini)."""
    return user_id.strip().upper().startswith(PREFIX)


# --- baca / tulis file --------------------------------------------------------
def _valid(data):
    """Buang entri yang rusak; kembalikan dict bersih atau None kalau bukan dict."""
    if not isinstance(data, dict):
        return None
    clean = {}
    for tid, d in data.items():
        tid = str(tid).strip().upper()
        if (is_teacher_id(tid) and isinstance(d, dict)
                and isinstance(d.get("name"), str) and isinstance(d.get("pin"), str)):
            clean[tid] = {"name": d["name"], "pin": d["pin"]}
    return clean


def _write(data):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = C.TEACHERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, C.TEACHERS_FILE)  # tulis utuh atau tidak sama sekali


def _load():
    """Baca data terbaru dari file (dibuat dari DEFAULT_TEACHERS kalau belum ada)."""
    try:
        with open(C.TEACHERS_FILE, encoding="utf-8") as f:
            data = _valid(json.load(f))
        if data is not None:
            return data
        raise ValueError("isi file bukan daftar guru")
    except FileNotFoundError:
        pass
    except Exception as exc:
        # File rusak: simpan salinannya, lalu mulai lagi dari data bawaan
        C.log(f"data\\teachers.json rusak ({exc!r}) -> dibuat ulang dari data bawaan")
        try:
            os.replace(C.TEACHERS_FILE, C.TEACHERS_FILE + ".rusak")
        except OSError:
            pass
    data = copy.deepcopy(DEFAULT_TEACHERS)
    try:
        _write(data)
    except OSError as exc:
        C.log(f"Gagal membuat data\\teachers.json: {exc!r}")
    return data


# --- dipakai layar lain -------------------------------------------------------
def list_teachers():
    """Semua guru [{'id','name'}], urut berdasarkan ID. PIN tidak ikut."""
    data = _load()
    return [{"id": tid, "name": data[tid]["name"]} for tid in sorted(data)]


def get_teacher(teacher_id):
    """{'id','name'} atau None kalau ID tidak ada."""
    tid = teacher_id.strip().upper()
    data = _load().get(tid)
    return None if data is None else {"id": tid, "name": data["name"]}


def check_teacher(user_id, pin):
    """Kembalikan {'id','name'} kalau ID dan PIN cocok, kalau tidak None."""
    uid = user_id.strip().upper()
    data = _load().get(uid)
    if data is None:
        return None
    if not hmac.compare_digest(str(pin).encode("utf-8"), data["pin"].encode("utf-8")):
        return None
    return {"id": uid, "name": data["name"]}


# --- tambah / ubah / hapus guru (dipakai Panel Admin) --------------------------
def _clean_name(name):
    """Rapikan nama (spasi ganda dibuang). ValueError kalau kosong / terlalu panjang."""
    name = " ".join(str(name).split())
    if not name:
        raise ValueError("Nama guru belum diisi.")
    if len(name) > NAME_MAX:
        raise ValueError(f"Nama terlalu panjang (maksimal {NAME_MAX} huruf).")
    return name


def _clean_pin(pin):
    pin = str(pin)
    if len(pin) < PIN_MIN:
        raise ValueError(f"PIN minimal {PIN_MIN} karakter.")
    if len(pin) > PIN_MAX:
        raise ValueError(f"PIN terlalu panjang (maksimal {PIN_MAX} karakter).")
    if any(ch.isspace() for ch in pin):
        raise ValueError("PIN tidak boleh mengandung spasi.")
    return pin


def _numbers_in_use(data):
    """Nomor ID yang sudah dipakai: guru yang ada + guru yang pernah menulis laporan.

    Laporan guru yang sudah dihapus tetap tersimpan, jadi nomornya tidak dipakai lagi
    (supaya laporan lama tidak 'pindah' ke guru baru).
    """
    ids = set(data)
    try:
        from elearning import reports   # di sini, bukan di atas file (menghindari impor melingkar)
        ids.update(r["teacher"] for r in reports.list_reports())
    except Exception as exc:
        C.log(f"Gagal membaca laporan untuk nomor ID guru: {exc!r}")
    nums = []
    for tid in ids:
        m = _NUM_RE.match(str(tid).strip().upper())
        if m:
            nums.append(int(m.group(1)))
    return nums


def next_teacher_id():
    """ID kosong berikutnya, mis. GURU002 kalau GURU001 sudah ada."""
    used = _numbers_in_use(_load())
    return f"{PREFIX}{(max(used) + 1 if used else 1):03d}"


def add_teacher(name, pin):
    """Tambah guru baru dengan ID otomatis (GURU002, GURU003, ...).

    ValueError (pesan siap tampil) kalau nama / PIN tidak valid; data tidak berubah.
    """
    name = _clean_name(name)
    pin = _clean_pin(pin)
    data = _load()
    tid = f"{PREFIX}{(max(_numbers_in_use(data) or [0]) + 1):03d}"
    data[tid] = {"name": name, "pin": pin}
    _write(data)
    return {"id": tid, "name": name}


def get_pin(teacher_id):
    """PIN guru saat ini (hanya untuk jendela Dev), None kalau guru tidak ada."""
    data = _load().get(teacher_id.strip().upper())
    return None if data is None else data["pin"]


def update_teacher(teacher_id, name, pin=None):
    """Ganti nama guru; kalau pin diisi, PIN-nya ikut diganti (None / kosong = tidak berubah)."""
    name = _clean_name(name)
    tid = teacher_id.strip().upper()
    data = _load()
    if tid not in data:
        raise ValueError(f"Guru {tid} tidak ditemukan.")
    data[tid]["name"] = name
    if pin:
        data[tid]["pin"] = _clean_pin(pin)
    _write(data)
    return {"id": tid, "name": name}


def delete_teacher(teacher_id):
    """Hapus akun guru beserta foto dan riwayat masuk/keluarnya. Tidak bisa dibatalkan.

    Laporan kerja yang pernah ditulis guru itu TIDAK dihapus (tetap bisa dilihat admin).
    """
    tid = teacher_id.strip().upper()
    data = _load()
    if tid not in data:
        raise ValueError(f"Guru {tid} tidak ditemukan.")
    del data[tid]
    _write(data)   # akun hilang dulu; kalau langkah di bawah gagal, akun tetap terhapus
    try:
        photos.remove_photo(tid)
    except OSError as exc:
        C.log(f"Foto {tid} tidak bisa dihapus: {exc!r}")
    sessions.delete_student(tid)   # fungsi ini menghapus riwayat berdasarkan ID, berlaku juga untuk guru
