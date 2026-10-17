"""Badge (achievement) murid PER KURSUS: tiap kursus punya set 20 badge sendiri, sama untuk
murid dewasa dan SUPERKIDS.

Satu file per murid:  data\\achievements\\<ID>.json   (aman setelah logout, aman dari update.bat)
  {"courses": {id kursus: {"badges": {id badge: {"t": "YYYY-mm-dd HH:MM:SS", "shown": bool,
                                                 "by": "guru"?}},
                           "days": ["YYYY-mm-dd", ...]}},
   "since": "...", "badges": {...lama, global; disimpan tapi tidak dipakai lagi}}

- Badge dari data (video, karya, hari belajar di kursus itu) dihitung ulang oleh evaluate()
  per kursus, di thread terpisah (lihat ui/badge_ui.py).
- Badge dari kejadian (buka kursus, buka Blender, easter egg) diberikan lewat award() ke
  kursus yang sedang / terakhir dibuka.
- "days" = hari murid membuka kursus itu (badge Konsisten), dicatat mark_day().
- Badge yang sudah didapat tidak hilang otomatis; hanya "Masuk Galeri" bisa dicabut guru.
- "shown" = notifikasi sudah tampil. Akun trial tidak mendapat badge.
- Nama & cara mendapat ada dua bahasa: "name"/"desc" (Indonesia, guru & admin) dan
  "name_en"/"desc_en" (English, layar murid).
"""

import json
import os
import threading
from datetime import datetime

from elearning import config as C
from elearning import portfolio, progress
from elearning.courses import courses_for, has_video

ACH_DIR = os.path.join(C.DATA_DIR, "achievements")
FMT = "%Y-%m-%d %H:%M:%S"

GREEN, BLUE, ORANGE, PURPLE, GOLD = "#3fb68b", "#4a90e2", "#ea7600", "#b06bff", "#e8b44a"

CATEGORIES = (("mulai", "Mulai", GREEN), ("belajar", "Belajar", BLUE),
              ("karya", "Karya", ORANGE), ("konsisten", "Konsisten", PURPLE),
              ("rahasia", "Rahasia", GOLD))
CAT_COLOR = {k: c for k, _n, c in CATEGORIES}

CAT_EN = {"mulai": "Getting Started", "belajar": "Learning", "karya": "Artwork",
          "konsisten": "Consistency", "rahasia": "Secret"}

# (id, kategori, nama, cara mendapat, nama EN, cara EN, ikon) -- ikon di ui/badge_art.py
_DEFS = (
    ("halo", "mulai", "Halo", "Buka kursus ini untuk pertama kali.",
     "Hello", "Open this course for the first time.", "halo"),
    ("siap_berkarya", "mulai", "Siap Berkarya", "Buka Blender dari aplikasi di kursus ini.",
     "Ready to Create", "Open Blender from the app in this course.", "cube"),
    ("belajar_praktik", "mulai", "Belajar Sambil Praktik",
     "Putar video kursus ini saat Blender terbuka.",
     "Learn by Doing", "Play a video of this course while Blender is open.", "monitor"),

    ("langkah_pertama", "belajar", "Langkah Pertama", "Tonton 1 video sampai selesai.",
     "First Step", "Finish 1 video.", "flag"),
    ("lima_video", "belajar", "Lima Video", "Tonton 5 video sampai selesai.",
     "Five Videos", "Finish 5 videos.", "layers"),
    ("lanjut_terus", "belajar", "Lanjut Terus", "Tonton 15 video sampai selesai.",
     "Keep Going", "Finish 15 videos.", "forward"),
    ("pantang_menyerah", "belajar", "Pantang Menyerah",
     "Ulangi satu video sampai 3 kali dan selesaikan.",
     "Never Give Up", "Watch one video 3 times and finish it.", "loop"),
    ("level_selesai", "belajar", "Level Selesai", "Selesaikan semua video di kursus ini.",
     "Level Complete", "Finish every video in this course.", "stairs"),
    ("tamat_kursus", "belajar", "Tamat Kursus",
     "Semua video selesai + Portfolio dan Assignment terisi di kursus ini.",
     "Course Master", "Finish every video and fill Portfolio and Assignment in this course.",
     "cap"),

    ("karya_pertama", "karya", "Karya Pertama", "Unggah karya pertama di kursus ini.",
     "First Artwork", "Upload your first artwork in this course.", "image"),
    ("rajin_berkarya", "karya", "Rajin Berkarya",
     "Unggah 5 karya (Portfolio + Assignment) di kursus ini.",
     "Busy Creator", "Upload 5 artworks (Portfolio + Assignment) in this course.", "pencil"),
    ("portofolio_lengkap", "karya", "Portofolio Lengkap",
     "Isi Portfolio dan Assignment di kursus ini.",
     "Complete Portfolio", "Fill both Portfolio and Assignment in this course.", "folder_check"),
    ("masuk_galeri", "karya", "Masuk Galeri", "Karyamu dipilih guru untuk galeri.",
     "Hall of Fame", "Your teacher picked your artwork for the gallery.", "star"),

    ("tiga_hari", "konsisten", "Tiga Hari", "Buka kursus ini di 3 hari yang berbeda.",
     "Three Days", "Study this course on 3 different days.", "calendar"),
    ("seminggu_penuh", "konsisten", "Seminggu Penuh", "Buka kursus ini di 7 hari yang berbeda.",
     "Full Week", "Study this course on 7 different days.", "calendar_check"),
    ("sebulan", "konsisten", "Sebulan", "Buka kursus ini di 30 hari yang berbeda.",
     "One Month", "Study this course on 30 different days.", "flame"),

    ("pemburu_logo", "rahasia", "Pemburu Logo", "Ada yang tersembunyi di balik logo.",
     "Logo Hunter", "Something is hidden behind the logo.", "target"),
    ("kode_rahasia", "rahasia", "Kode Rahasia", "Ketik kata rahasia di kolom cari.",
     "Secret Code", "Type the secret word in the search box.", "key"),
    ("si_sabar", "rahasia", "Si Sabar", "Diam sejenak di halaman kursus.",
     "Patience", "Stay still for a while on the course page.", "hourglass"),
    ("hari_spesial", "rahasia", "Hari Spesial", "Belajar di hari yang spesial.",
     "Special Day", "Study on a special day.", "gift"),
)

BADGES = [{"id": i, "cat": cat, "name": n, "desc": d, "name_en": ne, "desc_en": de,
           "icon": ic, "color": CAT_COLOR[cat], "secret": cat == "rahasia",
           "teacher": i == "masuk_galeri"} for i, cat, n, d, ne, de, ic in _DEFS]
BY_ID = {b["id"]: b for b in BADGES}
TOTAL = len(BADGES)

# Ambang badge dari data (dibatasi jumlah video kursus: kursus 8 video tetap bisa "15 video")
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


def _empty():
    return {"courses": {}}


def _load(sid):
    path = _path(sid)
    try:
        st = os.stat(path)
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return _empty()
    hit = _cache.get(sid)
    if hit is not None and hit[0] == key:
        return json.loads(json.dumps(hit[1]))
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        if not isinstance(doc, dict):
            raise ValueError("format salah")
        if not isinstance(doc.get("courses"), dict):
            doc["courses"] = {}
    except Exception as exc:
        C.log(f"Badge {sid} tidak terbaca ({exc!r}) -> dianggap kosong")
        return _empty()
    _cache[sid] = (key, doc)
    return json.loads(json.dumps(doc))


def _course(doc, cid):
    c = doc["courses"].setdefault(str(cid), {})
    if not isinstance(c.get("badges"), dict):
        c["badges"] = {}
    return c


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
def earned(sid, cid):
    """{id badge: waktu didapat (teks)} milik satu murid di satu kursus."""
    with _lock:
        c = _load(sid)["courses"].get(str(cid)) or {}
        return {k: v.get("t", "") for k, v in (c.get("badges") or {}).items() if k in BY_ID}


def earned_all(sid):
    """[(id kursus, id badge, waktu)] semua badge murid di semua kursus (Analytics / Excel)."""
    with _lock:
        out = []
        for cid, c in _load(sid)["courses"].items():
            for k, v in (c.get("badges") or {}).items():
                if k in BY_ID:
                    out.append((cid, k, v.get("t", "")))
        return out


def award(sid, cid, *ids, by=None):
    """Beri badge di kursus cid. Mengembalikan [(cid, id)] yang BARU didapat."""
    ids = [i for i in ids if i in BY_ID]
    if not sid or not cid or not ids:
        return []
    with _lock:
        doc = _load(sid)
        c = _course(doc, cid)
        new = [i for i in ids if i not in c["badges"]]
        if not new:
            return []
        for i in new:
            rec = {"t": _now(), "shown": False}
            if by:
                rec["by"] = by
            c["badges"][i] = rec
        if not _write(sid, doc):
            return []
    C.log(f"Badge {sid} [{cid}]: {', '.join(new)}")
    return [(str(cid), i) for i in new]


def revoke(sid, cid, bid):
    """Cabut badge pemberian guru (hanya "Masuk Galeri")."""
    if not BY_ID.get(bid, {}).get("teacher"):
        return False
    with _lock:
        doc = _load(sid)
        c = doc["courses"].get(str(cid)) or {}
        if (c.get("badges") or {}).pop(bid, None) is None:
            return False
        return _write(sid, doc)


def unshown(sid):
    """[(cid, id)] badge yang sudah didapat tapi notifikasinya belum tampil (urut waktu)."""
    with _lock:
        items = [(v.get("t", ""), cid, k) for cid, c in _load(sid)["courses"].items()
                 for k, v in (c.get("badges") or {}).items()
                 if k in BY_ID and not v.get("shown")]
    return [(cid, k) for _t, cid, k in sorted(items)]


def mark_shown(sid, cid, *ids):
    with _lock:
        doc = _load(sid)
        c = doc["courses"].get(str(cid)) or {}
        changed = False
        for i in ids:
            rec = (c.get("badges") or {}).get(i)
            if rec is not None and not rec.get("shown"):
                rec["shown"] = True
                changed = True
        if changed:
            _write(sid, doc)


def mark_day(sid, cid):
    """Catat hari ini sebagai hari belajar di kursus cid (badge Konsisten)."""
    today = datetime.now().strftime("%Y-%m-%d")
    with _lock:
        doc = _load(sid)
        c = _course(doc, cid)
        days = c.setdefault("days", [])
        if today in days:
            return
        days.append(today)
        _write(sid, doc)


def reset(sid):
    """Guru me-reset progres murid: semua badge (semua kursus) hilang."""
    with _lock:
        return _write(sid, {"courses": {}, "since": _now()})


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


def on_open_course(student, cid):
    """Murid membuka kursus: Halo (+ Hari Spesial) di kursus itu, hari belajar dicatat."""
    if not _eligible(student) or not cid:
        return []
    mark_day(student["id"], cid)
    ids = ["halo"]
    if _special_today():
        ids.append("hari_spesial")
    return award(student["id"], cid, *ids)


def _courses_of(student):
    """Kursus yang dinilai: kursus program murid yang terbuka untuknya."""
    allowed = set(student.get("courses", ()))
    return [c for c in courses_for(student["program"]) if c["id"] in allowed]


def evaluate(student):
    """Hitung badge dari data per kursus (video, karya, hari belajar). AMAN dipanggil dari
    thread: tidak menyentuh Tk. Mengembalikan [(cid, id)] yang baru didapat."""
    if not _eligible(student):
        return []
    sid = student["id"]
    new = []
    try:
        all_recs = progress.load(sid).get("courses", {})
    except Exception as exc:
        C.log(f"Badge progres {sid}: {exc!r}")
        all_recs = {}
    with _lock:
        doc = _load(sid)
    for course in _courses_of(student):
        cid = course["id"]
        have = set(((doc["courses"].get(cid) or {}).get("badges") or {}))
        want = []
        all_done = False
        # --- video: hanya yang benar-benar ditonton (lihat progress.completed) ---
        try:
            if has_video(course):
                recs = all_recs.get(cid, {})
                titles = progress.lesson_titles(course)
                done = sum(1 for t in titles if progress.completed(recs.get(t, {})))
                rewatched = any(progress.completed(r) and int(r.get("views", 0)) >= REWATCH
                                for r in recs.values())
                n = len(titles)
                if n and done >= min(VIDEOS_1, n):
                    want.append("langkah_pertama")
                if n and done >= min(VIDEOS_5, n):
                    want.append("lima_video")
                if n and done >= min(VIDEOS_15, n):
                    want.append("lanjut_terus")
                if rewatched:
                    want.append("pantang_menyerah")
                all_done = bool(n) and done >= n
                if all_done:
                    want.append("level_selesai")
        except Exception as exc:
            C.log(f"Badge video {sid}/{cid}: {exc!r}")
        # --- karya di kursus ini ---
        try:
            n_pf = portfolio.count(sid, cid)
            n_as = portfolio.count(sid, cid, portfolio.ASSIGNMENT)
            if n_pf + n_as >= 1:
                want.append("karya_pertama")
            if n_pf + n_as >= UPLOADS_5:
                want.append("rajin_berkarya")
            if n_pf > 0 and n_as > 0:
                want.append("portofolio_lengkap")
            if all_done and n_pf > 0 and n_as > 0:
                want.append("tamat_kursus")
        except Exception as exc:
            C.log(f"Badge karya {sid}/{cid}: {exc!r}")
        # --- hari belajar di kursus ini (berbeda, bukan harus berturut-turut) ---
        days = len(set((doc["courses"].get(cid) or {}).get("days") or ()))
        if days >= DAYS_3:
            want.append("tiga_hari")
        if days >= DAYS_7:
            want.append("seminggu_penuh")
        if days >= DAYS_30:
            want.append("sebulan")
        want = [w for w in want if w not in have]
        if want:
            new += award(sid, cid, *want)
    return new


def summary(student, cid):
    """(jumlah didapat di kursus cid, total) untuk sidebar / panel guru."""
    if not _eligible(student) or not cid:
        return 0, TOTAL
    return len(earned(student["id"], cid)), TOTAL
