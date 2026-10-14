"""Akun guru.

Login guru hanya untuk masuk ke layar pengaturan murid, bukan untuk keamanan
tingkat tinggi (PIN tersimpan apa adanya di file ini). Untuk ganti PIN atau
menambah guru, ubah daftar di bawah ini lalu jalankan update.bat.
"""

TEACHERS = {
    "GURU001": {"name": "Guru 1", "pin": "guru123"},
}


def is_teacher_id(user_id):
    """True kalau ID diawali 'GURU' (ID murid tidak pernah diawali ini)."""
    return user_id.strip().upper().startswith("GURU")


def check_teacher(user_id, pin):
    """Kembalikan {'id','name'} kalau ID dan PIN cocok, kalau tidak None."""
    uid = user_id.strip().upper()
    data = TEACHERS.get(uid)
    if data is None or pin != data["pin"]:
        return None
    return {"id": uid, "name": data["name"]}
