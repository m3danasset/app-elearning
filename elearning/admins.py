"""Akun admin.

Admin masuk ke Panel Admin untuk memantau status aktivitas guru dan murid
(hanya melihat, tidak mengubah data). Sama seperti akun guru, PIN tersimpan
apa adanya di file ini: ini untuk kemudahan di kelas, bukan keamanan tinggi.
Untuk tambah admin, ubah daftar di bawah lalu jalankan update.bat. PIN bisa diganti dari
jendela Dev (Login > Edit PIN): disimpan di data\\admin_pins.json dan menimpa PIN di bawah.
"""

import hmac
import json
import os

from elearning import config as C

ADMINS = {
    "ADMIN001": {"name": "Admin", "pin": "admin123"},
}


PIN_MIN, PIN_MAX = 4, 10   # sama dengan PIN guru (kolom PIN login maks. 10)


def _pins_path():
    return os.path.join(C.DATA_DIR, "admin_pins.json")


def _pins():
    """PIN admin yang diganti dari jendela Dev {ID: PIN}."""
    try:
        with open(_pins_path(), encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def _deleted_path():
    return os.path.join(C.DATA_DIR, "admins_deleted.json")


def _deleted():
    """ID admin yang dihapus dari jendela Dev (akun di ADMINS tetap ada di kode)."""
    try:
        with open(_deleted_path(), encoding="utf-8") as f:
            data = json.load(f)
        return {str(x).upper() for x in data} if isinstance(data, list) else set()
    except (OSError, ValueError, TypeError):
        return set()


NAME_MAX = 40


def _names_path():
    return os.path.join(C.DATA_DIR, "admin_names.json")


def _names():
    """Nama admin yang diganti dari jendela Dev {ID: nama}."""
    try:
        with open(_names_path(), encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def get_name(user_id):
    uid = user_id.strip().upper()
    if uid not in ADMINS:
        return None
    return _names().get(uid, ADMINS[uid]["name"])


def set_name(user_id, name):
    """Ganti nama admin (jendela Dev). ValueError (pesan siap tampil) kalau tidak valid."""
    uid = user_id.strip().upper()
    if uid not in ADMINS or uid in _deleted():
        raise ValueError(f"Admin {uid} tidak ditemukan.")
    name = " ".join(str(name).split())
    if not name:
        raise ValueError("Nama admin belum diisi.")
    if len(name) > NAME_MAX:
        raise ValueError(f"Nama terlalu panjang (maksimal {NAME_MAX} huruf).")
    data = _names()
    data[uid] = name
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = _names_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _names_path())
    return name


def check_pin_text(pin):
    """ValueError kalau PIN tidak valid (dipakai juga untuk cek sebelum menyimpan)."""
    pin = str(pin)
    if len(pin) < PIN_MIN:
        raise ValueError(f"PIN minimal {PIN_MIN} karakter.")
    if len(pin) > PIN_MAX:
        raise ValueError(f"PIN terlalu panjang (maksimal {PIN_MAX} karakter).")
    if any(ch.isspace() for ch in pin):
        raise ValueError("PIN tidak boleh mengandung spasi.")
    return pin


def list_admins():
    """[(ID, nama)] admin yang aktif (yang dihapus di Dev tidak ikut)."""
    gone = _deleted()
    names = _names()
    return [(uid, names.get(uid, a["name"])) for uid, a in ADMINS.items() if uid not in gone]


def delete_admin(user_id):
    """Hapus akun admin (jendela Dev). Admin terakhir tidak boleh dihapus."""
    uid = user_id.strip().upper()
    gone = _deleted()
    if uid not in ADMINS or uid in gone:
        raise ValueError(f"Admin {uid} tidak ditemukan.")
    if len([a for a in ADMINS if a not in gone]) <= 1:
        raise ValueError("Admin terakhir tidak bisa dihapus (minimal harus ada 1 admin).")
    gone.add(uid)
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = _deleted_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(gone), f, indent=2)
    os.replace(tmp, _deleted_path())
    pins = _pins()
    if pins.pop(uid, None) is not None:       # PIN gantiannya ikut dibuang
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(pins, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _pins_path())


def get_pin(user_id):
    uid = user_id.strip().upper()
    if uid not in ADMINS or uid in _deleted():
        return None
    return _pins().get(uid, ADMINS[uid]["pin"])


def set_pin(user_id, pin):
    """Ganti PIN admin (jendela Dev). ValueError (pesan siap tampil) kalau tidak valid."""
    uid = user_id.strip().upper()
    if uid not in ADMINS:
        raise ValueError(f"Admin {uid} tidak ditemukan.")
    pin = str(pin)
    if len(pin) < PIN_MIN:
        raise ValueError(f"PIN minimal {PIN_MIN} karakter.")
    if len(pin) > PIN_MAX:
        raise ValueError(f"PIN terlalu panjang (maksimal {PIN_MAX} karakter).")
    if any(ch.isspace() for ch in pin):
        raise ValueError("PIN tidak boleh mengandung spasi.")
    data = _pins()
    data[uid] = pin
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = _pins_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _pins_path())


def is_admin_id(user_id):
    """True kalau ID diawali 'ADMIN' (ID murid dan guru tidak boleh diawali ini)."""
    return user_id.strip().upper().startswith("ADMIN")


def check_admin(user_id, pin):
    """Kembalikan {'id','name'} kalau ID dan PIN cocok, kalau tidak None."""
    uid = user_id.strip().upper()
    data = ADMINS.get(uid)
    real = get_pin(uid)
    if data is None or real is None:          # tidak ada / dihapus di Dev
        return None
    if not hmac.compare_digest(str(pin).encode("utf-8"), real.encode("utf-8")):
        return None
    return {"id": uid, "name": get_name(uid)}
