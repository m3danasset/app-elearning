"""Laporan kerja guru, disimpan di  data\\reports.json  (di samping .exe).

Isi laporan datang dari dua sumber:
  1. Catatan yang ditulis guru sendiri: portfolio, catatan murid, kegiatan
     mengajar, kendala, atau hal lain.
  2. Ringkasan OTOMATIS dari data yang sudah ada: siapa saja yang sudah submit
     portfolio pada suatu periode (dibaca dari folder portfolio, guru tidak perlu
     mengetik ulang).

Guru menulis dan mengubah laporannya sendiri. Admin hanya melihat.

Satu catatan: {"id", "teacher", "date", "kind", "student", "text", "created", "edited"}
  date    = tanggal kejadian yang dilaporkan (YYYY-MM-DD)
  student = ID murid yang dimaksud, atau "" untuk laporan umum

Seperti sessions.py, kegagalan membaca file tidak boleh mengganggu aplikasi.
"""

import json
import os
from datetime import date, datetime, timedelta

from elearning import config as C
from elearning import portfolio
from elearning.courses import courses_for
from elearning.students import STATUS_EXPIRED, list_students, lookup_student

FMT = "%Y-%m-%d %H:%M:%S"
DAY_FMT = "%Y-%m-%d"
MAX_KEEP = 5000      # simpan paling banyak sekian laporan terbaru
TEXT_MAX = 2000      # batas panjang satu catatan

# (kode, label) dalam urutan tampil
KINDS = (("portfolio", "Portfolio"),
         ("student", "Catatan murid"),
         ("class", "Kegiatan mengajar"),
         ("issue", "Kendala"),
         ("other", "Lainnya"))
KIND_LABEL = dict(KINDS)
STUDENT_KINDS = ("portfolio", "student")   # jenis yang wajib menyebut murid

# (kode, label) pilihan periode di layar guru dan admin
PERIODS = (("today", "Hari ini"), ("7d", "7 hari"), ("30d", "30 hari"), ("all", "Semua"))


# --- tanggal --------------------------------------------------------------------
def _now():
    return datetime.now().strftime(FMT)


def _iso_day(text):
    try:
        return datetime.strptime(text, DAY_FMT).date()
    except (TypeError, ValueError):
        return None


def parse_day(text):
    """Baca tanggal ketikan guru ('15/10/2026', '15-10-2026', atau '2026-10-15').

    ValueError (pesan siap tampil) kalau tidak bisa dibaca.
    """
    text = str(text).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", DAY_FMT):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError("Tanggal tidak valid. Tulis seperti 15/10/2026.")


def format_day(day):
    return f"{day.day:02d}/{day.month:02d}/{day.year}"


def period(key, today=None):
    """(dari, sampai) tanggal untuk satu pilihan periode; keduanya inklusif.

    'all' mengembalikan (None, None) = tanpa batas.
    """
    today = today or date.today()
    if key == "today":
        return today, today
    if key == "7d":
        return today - timedelta(days=6), today
    if key == "30d":
        return today - timedelta(days=29), today
    return None, None


def in_range(day, since, until):
    return (since is None or day >= since) and (until is None or day <= until)


# --- baca / tulis ---------------------------------------------------------------
def _valid(rec):
    return (isinstance(rec, dict)
            and all(isinstance(rec.get(k), str) for k in ("id", "teacher", "text"))
            and rec.get("kind") in KIND_LABEL
            and _iso_day(rec.get("date")) is not None)


def _read():
    try:
        with open(C.REPORTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("isi file bukan daftar laporan")
        out = []
        for rec in data:
            if _valid(rec):
                rec["student"] = rec["student"] if isinstance(rec.get("student"), str) else ""
                rec["created"] = rec["created"] if isinstance(rec.get("created"), str) else ""
                rec["edited"] = rec["edited"] if isinstance(rec.get("edited"), str) else None
                out.append(rec)
        return out
    except FileNotFoundError:
        return []
    except Exception as exc:
        C.log(f"data\\reports.json rusak ({exc!r}) -> dimulai dari kosong")
        try:
            os.replace(C.REPORTS_FILE, C.REPORTS_FILE + ".rusak")
        except OSError:
            pass
        return []


def _write(records):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = C.REPORTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records[-MAX_KEEP:], f, ensure_ascii=False, indent=1)
    os.replace(tmp, C.REPORTS_FILE)   # tulis utuh atau tidak sama sekali


# --- menulis laporan (dipakai layar guru) -----------------------------------------
def _validate(kind, text, student_id, day):
    """Rapikan dan periksa isian. ValueError (pesan siap tampil) kalau ada yang salah."""
    if kind not in KIND_LABEL:
        raise ValueError("Pilih jenis laporan.")
    text = str(text).strip()
    if not text:
        raise ValueError("Catatan belum diisi.")
    if len(text) > TEXT_MAX:
        raise ValueError(f"Catatan terlalu panjang (maksimal {TEXT_MAX} huruf, "
                         f"sekarang {len(text)}).")
    if not isinstance(day, date):
        raise ValueError("Tanggal belum diisi.")
    if day > date.today():
        raise ValueError("Tanggal tidak boleh di masa depan.")
    sid = str(student_id or "").strip().upper()
    if kind in STUDENT_KINDS and not sid:
        raise ValueError(f"Pilih murid untuk laporan jenis {KIND_LABEL[kind]}.")
    if sid and lookup_student(sid) is None:
        raise ValueError(f"Murid {sid} tidak ditemukan.")
    return kind, text, sid, day


def _new_id(records):
    base = datetime.now().strftime("%Y%m%d%H%M%S")
    used = {r["id"] for r in records}
    n = 1
    while f"{base}-{n}" in used:
        n += 1
    return f"{base}-{n}"


def add(teacher_id, kind, text, student_id="", day=None):
    """Simpan laporan baru. Mengembalikan catatan yang tersimpan."""
    kind, text, sid, day = _validate(kind, text, student_id, day or date.today())
    records = _read()
    rec = {"id": _new_id(records), "teacher": teacher_id, "date": day.strftime(DAY_FMT),
           "kind": kind, "student": sid, "text": text, "created": _now(), "edited": None}
    records.append(rec)
    _write(records)
    return rec


def update(report_id, teacher_id, kind, text, student_id="", day=None):
    """Ubah laporan milik guru itu sendiri."""
    kind, text, sid, day = _validate(kind, text, student_id, day or date.today())
    records = _read()
    for rec in records:
        if rec["id"] == report_id and rec["teacher"] == teacher_id:
            rec.update({"date": day.strftime(DAY_FMT), "kind": kind, "student": sid,
                        "text": text, "edited": _now()})
            _write(records)
            return rec
    raise ValueError("Laporan tidak ditemukan (mungkin sudah dihapus).")


def delete(report_id, teacher_id):
    """Hapus laporan milik guru itu sendiri."""
    records = _read()
    kept = [r for r in records if not (r["id"] == report_id and r["teacher"] == teacher_id)]
    if len(kept) == len(records):
        raise ValueError("Laporan tidak ditemukan (mungkin sudah dihapus).")
    _write(kept)


# --- membaca laporan (layar guru dan Panel Admin) ----------------------------------
def list_reports(teacher_id=None, since=None, until=None):
    """Laporan terbaru dulu. Tiap item sudah berisi 'day' (objek date)."""
    out = []
    for rec in _read():
        if teacher_id is not None and rec["teacher"] != teacher_id:
            continue
        day = _iso_day(rec["date"])
        if not in_range(day, since, until):
            continue
        out.append(dict(rec, day=day))
    out.sort(key=lambda r: (r["date"], r["created"]), reverse=True)
    return out


def portfolio_status(since=None, until=None):
    """Siapa saja yang sudah submit portfolio pada periode ini (murid aktif saja).

    Dibaca langsung dari folder portfolio. Tiap item:
      id, name, program,
      submitted (jumlah file pada periode), images, videos,
      total (semua file sepanjang waktu), last (waktu submit terakhir atau None),
      courses (judul kursus yang dapat submit baru pada periode).
    """
    rows = []
    for s in list_students():
        if s.get("status") == STATUS_EXPIRED:   # murid expired tidak bisa login/submit
            continue
        total = images = videos = 0
        last = None
        titles = []
        for course in courses_for(s["program"]):
            hit = 0
            for item in portfolio.list_items(s["id"], course["id"]):
                total += 1
                if last is None or item["added"] > last:
                    last = item["added"]
                if in_range(item["added"].date(), since, until):
                    hit += 1
                    if item["kind"] == "video":
                        videos += 1
                    else:
                        images += 1
            if hit:
                titles.append(course["title"])
        rows.append({"id": s["id"], "name": s["name"], "program": s["program"],
                     "submitted": images + videos, "images": images, "videos": videos,
                     "total": total, "last": last, "courses": titles})
    return rows
