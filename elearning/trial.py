"""Akun trial untuk calon murid.

Ketik ID  TRIAL  di layar login, tanpa PIN. Calon murid langsung melihat dua pilihan:
ANIMATION dan MODELING (lihat TRIAL_COURSES di courses.py).

- Akun ini tidak disimpan di data\\students.json (tidak muncul di layar guru dan admin).
- Masuk/keluar akun trial tidak dicatat di riwayat login (ID-nya dipakai bersama
  oleh banyak calon murid, jadi tidak ada gunanya per orang).
- Fitur Portfolio dimatikan untuk trial, supaya hasil karya calon murid tidak
  tercampur di satu ID bersama.
"""

from elearning.courses import courses_for

TRIAL_ID = "TRIAL"
TRIAL_NAME = "Calon Murid"
PROGRAM = "trial"


def is_trial_id(user_id):
    """True kalau yang diketik persis TRIAL (huruf besar/kecil tidak berpengaruh)."""
    return str(user_id).strip().upper() == TRIAL_ID


def is_trial(student):
    return bool(student) and student.get("program") == PROGRAM


def trial_student():
    """Data 'murid' untuk akun trial, bentuknya sama dengan lookup_student()."""
    return {"id": TRIAL_ID, "name": TRIAL_NAME, "program": PROGRAM,
            "courses": [c["id"] for c in courses_for(PROGRAM)], "status": "active"}
