"""Badge (achievement) murid: 20 badge, sama untuk murid dewasa dan SUPERKIDS.

Satu file per murid:  data\\achievements\\<ID>.json   (aman setelah logout, aman dari update.bat)
  {"badges": {id badge: {"t": "YYYY-mm-dd HH:MM:SS", "shown": true/false, "by": "guru"?}}}

- Badge dari data (video, karya, hari belajar) dihitung ulang oleh evaluate(): dipanggil di
  thread terpisah (lihat ui/badge_ui.py), jadi aplikasi tidak tersendat.
- Badge dari kejadian (login, buka Blender, easter egg) diberikan langsung lewat award().
- Badge yang sudah didapat tidak pernah hilang otomatis; hanya "Masuk Galeri" yang bisa dicabut
  guru (badge pemberian guru).
- "shown" = notifikasi sudah tampil. Badge yang didapat di PC lain tetap diberi tahu sekali.
- Akun trial tidak mendapat badge (ID-nya dipakai bersama).
"""

import json
import os
import threading
from datetime import datetime

from elearning import config as C
from elearning import portfolio, progress, sessions
from elearning.courses import courses_for, has_video

ACH_DIR = os.path.join(C.DATA_DIR, "achievements")
FMT = "%Y-%m-%d %H:%M:%S"

GREEN, BLUE, ORANGE, PURPLE, GOLD = "#3fb68b", "#4a90e2", "#ea7600", "#b06bff", "#e8b44a"

CATEGORIES = (("mulai", "Mulai", GREEN), ("belajar", "Belajar", BLUE),
              ("karya", "Karya", ORANGE), ("konsisten", "Konsisten", PURPLE),
              ("rahasia", "Rahasia", GOLD))
CAT_COLOR = {k: c for k, _n, c in CATEGORIES}

# (id, kategori, nama, cara mendapat, ikon)  -- ikon digambar di ui/badge_art.py
_DEFS = (
    ("halo", "mulai", "Halo", "Masuk ke aplikasi untuk pertama kali.", "halo"),
    ("siap_berkarya", "mulai", "Siap Berkarya", "Buka Blender dari aplikasi.", "cube"),
    ("belajar_praktik", "mulai", "Belajar Sambil Praktik",
     "Putar video pelajaran saat Blender terbuka.", "monitor"),

    ("langkah_pertama", "belajar", "Langkah Pertama", "Tonton 1 video sampai selesai.", "flag"),
    ("lima_video", "belajar", "Lima Video", "Tonton 5 video sampai selesai.", "layers"),
    ("lanjut_terus", "belajar", "Lanjut Terus", "Tonton 15 video sampai selesai.", "forward"),
    ("pantang_menyerah", "belajar", "Pantang Menyerah",
     "Ulangi satu video sampai 3 kali dan selesaikan.", "loop"),
    ("level_selesai", "belajar", "Level Selesai",
     "Selesaikan semua video di satu kursus.", "stairs"),
    ("tamat_kursus", "belajar", "Tamat Kursus",
     "Tuntaskan semua kursus yang terbuka (min. 2).", "cap"),

    ("karya_pertama", "karya", "Karya Pertama", "Unggah karya pertamamu.", "image"),
    ("rajin_berkarya", "karya", "Rajin Berkarya",
     "Unggah 5 karya (Portfolio + Assignment).", "pencil"),
    ("portofolio_lengkap", "karya", "Portofolio Lengkap",
     "Isi Portfolio dan Assignment di kursus yang sama.", "folder_check"),
    ("masuk_galeri", "karya", "Masuk Galeri", "Karyamu dipilih guru untuk galeri.", "star"),

    ("tiga_hari", "konsisten", "Tiga Hari", "Belajar di 3 hari yang berbeda.", "calendar"),
    ("seminggu_penuh", "konsisten", "Seminggu Penuh", "Belajar di 7 hari yang berbeda.",
     "calendar_check"),
    ("sebulan", "konsisten", "Sebulan", "Belajar di 30 hari yang berbeda.", "flame"),

    ("pemburu_logo", "rahasia", "Pemburu Logo", "Ada yang tersembunyi di balik logo.", "target"),
    ("kode_rahasia", "rahasia", "Kode Rahasia", "Ketik kata rahasia di kolom cari.", "key"),
    ("si_sabar", "rahasia", "Si Sabar", "Diam sejenak di layar utama.", "hourglass"),
    ("hari_spesial", "rahasia", "Hari Spesial", "Belajar di hari yang spesial.", "gift"),
)

BADGES = [{"id": i, "cat": cat, "name": n, "desc": d, "icon": ic,
           "color": CAT_COLOR[cat], "secret": cat == "rahasia",
           "teacher": i == "masuk_galeri"} for i, cat, n, d, ic in _DEFS]
BY_ID = {b["id"]: b for b in BADGES}
TOTAL = len(BADGES)

# Ambang badge dari data
VIDEOS_1, VIDEOS_5, VIDEOS_15 = 1, 5, 15
REWATCH = 3
UPLOADS_5 = 5
DAYS_3, DAYS_7, DAYS_30 = 3, 7, 30

_lock = threading.Lock()
_cache = {}      # ID -> (kunci file, isi)


# --- baca / tulis ----------------------------------------------------------------------
def _path(sid):
    safe = "".join(ch for ch in str(sid).upper() if ch.isalnum() or ch in "-_") or "X"
    return os.path.join(ACH_DIR, safe + ".json")


def _now():
    return datetime.now().strftime(FMT)


def _load(sid):
    path = _path(sid)
    try:
        st = os.stat(path)
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return {"badges": {}}
    hit = _cache.get(sid)
    if hit is not None and hit[0] == key:
        return json.loads(json.dumps(hit[1]))
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        if not isinstance(doc, dict) or not isinstance(doc.get("badges"), dict):
            raise ValueError("format salah")
    except Exception as exc:
        C.log(f"Badge {sid} tidak terbaca ({exc!r}) -> dianggap kosong")
        return {"badges": {}}
    _cache[sid] = (key, doc)
    return json.loads(json.dumps(doc))


def _write(sid, doc):
    try:
        os.makedirs(ACH_DIR, exist_ok=True)
        path = _path(sid)
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        st = os.stat(path)
        _cache[sid] = ((st.st_mtime_ns, st.st_size), json.loads(json.dumps(doc)))
        return True
    except Exception as exc:
        C.log(f"Gagal menyimpan badge {sid}: {exc!r}")
        return False


def _eligible(student):
    return bool(student) and student.get("program") in ("adult", "kids") \
        and not str(student.get("id", "")).upper().startswith("TRIAL")


# --- API ---------------------------------------------------------------------------------
def earned(sid):
    """{id badge: waktu didapat (teks)} milik satu murid."""
    with _lock:
        return {k: v.get("t", "") for k, v in _load(sid)["badges"].items() if k in BY_ID}


def award(sid, *ids, by=None):
    """Beri badge. Mengembalikan daftar id yang BARU didapat (yang sudah ada diabaikan)."""
    ids = [i for i in ids if i in BY_ID]
    if not sid or not ids:
        return []
    with _lock:
        doc = _load(sid)
        new = [i for i in ids if i not in doc["badges"]]
        if not new:
            return []
        for i in new:
            rec = {"t": _now(), "shown": False}
            if by:
                rec["by"] = by
            doc["badges"][i] = rec
        if not _write(sid, doc):
            return []
    C.log(f"Badge {sid}: {', '.join(new)}")
    return new


def revoke(sid, bid):
    """Cabut badge pemberian guru (hanya "Masuk Galeri")."""
    if not BY_ID.get(bid, {}).get("teacher"):
        return False
    with _lock:
        doc = _load(sid)
        if doc["badges"].pop(bid, None) is None:
            return False
        return _write(sid, doc)


def unshown(sid):
    """Badge yang sudah didapat tapi notifikasinya belum tampil (urut waktu)."""
    with _lock:
        items = [(v.get("t", ""), k) for k, v in _load(sid)["badges"].items()
                 if k in BY_ID and not v.get("shown")]
    return [k for _t, k in sorted(items)]


def mark_shown(sid, *ids):
    with _lock:
        doc = _load(sid)
        changed = False
        for i in ids:
            rec = doc["badges"].get(i)
            if rec is not None and not rec.get("shown"):
                rec["shown"] = True
                changed = True
        if changed:
            _write(sid, doc)


def reset(sid):
    """Guru me-reset progres murid: semua badge hilang. Hari belajar dihitung ulang mulai
    sekarang ("since"), supaya badge Konsisten tidak langsung kembali dari riwayat lama."""
    with _lock:
        return _write(sid, {"badges": {}, "since": _now()})


def _since(sid):
    with _lock:
        text = _load(sid).get("since")
    try:
        return datetime.strptime(text, FMT) if text else None
    except ValueError:
        return None


def delete_student(sid):
    try:
        if os.path.exists(_path(sid)):
            os.remove(_path(sid))
        _cache.pop(sid, None)
    except Exception as exc:
        C.log(f"Gagal menghapus badge {sid}: {exc!r}")


# --- dihitung dari data ---------------------------------------------------------------------
def _special_today():
    days = getattr(C, "SPECIAL_DAYS", ())
    return datetime.now().strftime("%m-%d") in days


def on_login(student):
    """Dipanggil saat murid masuk. Mengembalikan badge baru (Halo, Hari Spesial)."""
    if not _eligible(student):
        return []
    ids = ["halo"]
    if _special_today():
        ids.append("hari_spesial")
    return award(student["id"], *ids)


def evaluate(student):
    """Hitung badge dari data (video, karya, hari belajar). AMAN dipanggil dari thread:
    tidak menyentuh Tk. Mengembalikan badge yang baru didapat."""
    if not _eligible(student):
        return []
    sid = student["id"]
    have = earned(sid)
    want = []

    # --- video: hanya yang benar-benar ditonton (lihat progress.completed) ---
    try:
        courses = progress.load(sid).get("courses", {})
        done = 0
        rewatched = False
        finished_courses = 0
        open_video_courses = 0
        allowed = set(student.get("courses", ()))
        for course in courses_for(student["program"]):
            if not has_video(course):
                continue
            recs = courses.get(course["id"], {})
            titles = progress.lesson_titles(course)
            for rec in recs.values():
                if progress.completed(rec):
                    done += 1
                    if int(rec.get("views", 0)) >= REWATCH:
                        rewatched = True
            if titles:
                all_done = all(progress.completed(recs.get(t, {})) for t in titles)
                if all_done:
                    finished_courses += 1
                if course["id"] in allowed:
                    open_video_courses += 1
                    if not all_done:
                        open_video_courses = -10**6   # ada kursus terbuka yang belum tuntas
        if done >= VIDEOS_1:
            want.append("langkah_pertama")
        if done >= VIDEOS_5:
            want.append("lima_video")
        if done >= VIDEOS_15:
            want.append("lanjut_terus")
        if rewatched:
            want.append("pantang_menyerah")
        if finished_courses >= 1:
            want.append("level_selesai")
        if open_video_courses >= 2:
            want.append("tamat_kursus")
    except Exception as exc:
        C.log(f"Badge video {sid}: {exc!r}")

    # --- karya ---
    try:
        total = 0
        both = False
        for course in courses_for(student["program"]):
            n_pf = portfolio.count(sid, course["id"])
            n_as = portfolio.count(sid, course["id"], portfolio.ASSIGNMENT)
            total += n_pf + n_as
            both = both or (n_pf > 0 and n_as > 0)
        if total >= 1:
            want.append("karya_pertama")
        if total >= UPLOADS_5:
            want.append("rajin_berkarya")
        if both:
            want.append("portofolio_lengkap")
    except Exception as exc:
        C.log(f"Badge karya {sid}: {exc!r}")

    # --- hari belajar (berbeda, bukan harus berturut-turut) ---
    try:
        since = _since(sid)
        days = {e["start"].date() for e in sessions.entries(sid)
                if e.get("start") and (since is None or e["start"] >= since)}
        if len(days) >= DAYS_3:
            want.append("tiga_hari")
        if len(days) >= DAYS_7:
            want.append("seminggu_penuh")
        if len(days) >= DAYS_30:
            want.append("sebulan")
    except Exception as exc:
        C.log(f"Badge hari belajar {sid}: {exc!r}")

    if _special_today():
        want.append("hari_spesial")
    want = [w for w in want if w not in have]
    return award(sid, *want) if want else []


def summary(student):
    """(jumlah didapat, total) untuk ditampilkan di sidebar / panel guru."""
    if not _eligible(student):
        return 0, TOTAL
    return len(earned(student["id"])), TOTAL
