"""Resource kursus (file tambahan dari guru: .blend, tekstur, PDF, gambar, video, ...).

Taruh file di  assets\\resources\\<id kursus>\\  (nama folder juga boleh judul kursus,
mis. "BASIC 1"). Kelas trial memakai satu folder bersama: assets\\resources\\trial\\ .
Boleh berisi subfolder. Murid hanya bisa melihat, membuka, dan
menyimpan ke flashdisk lewat file browser di halaman Resource (tidak bisa menghapus).
"""

import os
import re

from elearning import config as C

RESOURCE_DIR = os.path.join(C.APP_DIR, "assets", "resources")


def _norm(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


TRIAL_FOLDER = "trial"   # semua kelas trial (ANIMATION, MODELING) memakai SATU folder ini


def course_folder(course):
    """Folder resource kursus (mungkin belum ada). Kelas trial: satu folder bersama."""
    if course.get("program") == "trial":
        return os.path.join(RESOURCE_DIR, TRIAL_FOLDER)
    exact = os.path.join(RESOURCE_DIR, course["id"])
    if os.path.isdir(exact):
        return exact
    wanted = {_norm(course["id"]), _norm(course.get("title", ""))}
    try:
        for name in sorted(os.listdir(RESOURCE_DIR)):
            full = os.path.join(RESOURCE_DIR, name)
            if _norm(name) in wanted and os.path.isdir(full):
                return full
    except OSError:
        pass
    return exact


def summary(course, limit=2000):
    """(jumlah file, jumlah folder) di folder resource; berhenti menghitung di `limit`."""
    files = folders = 0
    for base, dirs, names in os.walk(course_folder(course)):
        dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
        folders += len(dirs)
        files += sum(1 for n in names if not n.startswith((".", "~$"))
                     and not re.search(r"\.blend\d+$", n, re.IGNORECASE))   # .blend1 = cadangan
        if files + folders >= limit:
            break
    return files, folders
