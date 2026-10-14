"""Akun admin.

Admin masuk ke Panel Admin untuk memantau status aktivitas guru dan murid
(hanya melihat, tidak mengubah data). Sama seperti akun guru, PIN tersimpan
apa adanya di file ini: ini untuk kemudahan di kelas, bukan keamanan tinggi.
Untuk ganti PIN / tambah admin, ubah daftar di bawah lalu jalankan update.bat.
"""

import hmac

ADMINS = {
    "ADMIN001": {"name": "Admin", "pin": "admin123"},
}


def is_admin_id(user_id):
    """True kalau ID diawali 'ADMIN' (ID murid dan guru tidak boleh diawali ini)."""
    return user_id.strip().upper().startswith("ADMIN")


def check_admin(user_id, pin):
    """Kembalikan {'id','name'} kalau ID dan PIN cocok, kalau tidak None."""
    uid = user_id.strip().upper()
    data = ADMINS.get(uid)
    if data is None:
        return None
    if not hmac.compare_digest(str(pin).encode("utf-8"), data["pin"].encode("utf-8")):
        return None
    return {"id": uid, "name": data["name"]}
