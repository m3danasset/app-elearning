"""Laporan kerja guru gaya SHEET (pengganti formulir laporan lama).

Per guru per bulan, tiga bagian seperti sheet tugas studio:
  MINGGU INI | BULAN INI | SUDAH SELESAI
Kolom: No, tugas, DONE (centang guru), LAPORAN (isian guru), CHECK (centang admin).
Centang DONE = tugas otomatis pindah ke "Sudah selesai" (urut waktu selesai); centang dilepas =
kembali ke bagiannya semula. Tugas kosong yang disimpan = dihapus.

data\\report_tasks.json: {"v": 1, "items": [{id, teacher, month "YYYY-MM", section "week" |
"month", text, report, done, done_at, check, check_by, check_at, created, edited}]}
Laporan lama (reports.json) tetap disimpan & tetap ikut export, tapi tidak ditulis lagi.
"""

import json
import os
import threading
from datetime import datetime

from elearning import config as C

FMT = "%Y-%m-%d %H:%M:%S"
SECTIONS = (("day", "LAPORAN HARIAN"), ("week", "MINGGU INI"), ("month", "BULAN INI"))
DAYS = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
TEXT_MAX = 300
REPORT_MAX = 600
MONTHS = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
          "September", "Oktober", "November", "Desember")
_lock = threading.Lock()
_cache = {"key": None, "items": None}


def _path():
    return os.path.join(C.DATA_DIR, "report_tasks.json")


def _now():
    return datetime.now().strftime(FMT)


def this_month():
    return datetime.now().strftime("%Y-%m")


def month_label(month):
    y, m = int(month[:4]), int(month[5:7])
    return f"{MONTHS[m - 1]} {y}"


def shift_month(month, step):
    y, m = int(month[:4]), int(month[5:7]) + step
    while m < 1:
        y, m = y - 1, m + 12
    while m > 12:
        y, m = y + 1, m - 12
    return f"{y:04d}-{m:02d}"


def _load():
    try:
        st = os.stat(_path())
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return []
    if key == _cache["key"] and _cache["items"] is not None:
        return [dict(x) for x in _cache["items"]]
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        items = [x for x in (data.get("items") if isinstance(data, dict) else data) or []
                 if isinstance(x, dict) and x.get("id") and x.get("teacher")]
    except (OSError, ValueError, AttributeError) as exc:
        C.log(f"data\\report_tasks.json tidak terbaca: {exc!r}")
        items = []
    _cache.update(key=key, items=[dict(x) for x in items])
    return items


def _write(items):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"v": 1, "items": items}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path())


def _clean(text, limit, what):
    text = " ".join(str(text or "").split())
    if len(text) > limit:
        raise ValueError(f"{what} terlalu panjang (maksimal {limit} huruf).")
    return text


def items_of(teacher_id, month):
    """Tugas guru di bulan itu, urutan dibuat (tugas selesai urut waktu selesai)."""
    tid = str(teacher_id).upper()
    return sorted((x for x in _load() if x["teacher"] == tid and x.get("month") == month),
                  key=lambda x: (x.get("created", ""), x["id"]))


def day_label(day):
    """"2026-10-19" -> "Senin, 19 Okt"."""
    d = datetime.strptime(day, "%Y-%m-%d")
    return f"{DAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1][:3]}"


def short_date(stamp):
    """"2026-10-19 14:03:00" -> "19/10/26"."""
    try:
        return datetime.strptime(stamp[:10], "%Y-%m-%d").strftime("%d/%m/%y")
    except (TypeError, ValueError):
        return ""


def grouped(teacher_id, month, day=None):
    """{"day": [...laporan harian hari itu], "week": [...belum selesai], "month": [...],
    "done": [...selesai, terlama dulu]}. Laporan harian: hanya tanggal `day`."""
    rows = items_of(teacher_id, month)
    out = {k: [x for x in rows if x.get("section") == k and not x.get("done")]
           for k, _l in SECTIONS}
    out["day"] = [x for x in out["day"] if x.get("day") == day]
    out["done"] = sorted((x for x in rows if x.get("done")),
                         key=lambda x: (x.get("done_at") or "", x["id"]))
    return out


def add(teacher_id, month, section, text, report="", day=None):
    text = _clean(text, TEXT_MAX, "Tugas")
    if not text:
        raise ValueError("Tugas belum diisi.")
    if section not in dict(SECTIONS):
        section = "week"
    now = _now()
    with _lock:
        items = _load()
        n = sum(1 for x in items if x["id"].startswith("T" + now[:10].replace("-", "")))
        rec = {"id": f"T{datetime.now():%Y%m%d%H%M%S}{n:03d}", "teacher": str(teacher_id).upper(),
               "month": month, "section": section, "text": text,
               "report": _clean(report, REPORT_MAX, "Laporan"), "done": False, "done_at": "",
               "check": False, "check_by": "", "check_at": "", "created": now, "edited": now}
        if section == "day":                    # laporan harian: milik satu tanggal
            rec["day"] = day or now[:10]
        while any(x["id"] == rec["id"] for x in items):
            rec["id"] += "x"
        items.append(rec)
        _write(items)
    return rec


def _change(item_id, fn):
    with _lock:
        items = _load()
        for i, x in enumerate(items):
            if x["id"] == item_id:
                new = fn(dict(x))
                if new is None:
                    del items[i]
                else:
                    new["edited"] = _now()
                    items[i] = new
                _write(items)
                return new
    raise ValueError("Tugas tidak ditemukan (mungkin sudah dihapus).")


def set_text(item_id, text):
    """Ubah teks tugas; kosong = tugas dihapus. Kembalikan tugas baru / None (dihapus)."""
    text = _clean(text, TEXT_MAX, "Tugas")
    return _change(item_id, lambda x: dict(x, text=text) if text else None)


def set_report(item_id, report):
    report = _clean(report, REPORT_MAX, "Laporan")
    return _change(item_id, lambda x: dict(x, report=report))


def set_done(item_id, done):
    return _change(item_id, lambda x: dict(x, done=bool(done),
                                           done_at=_now() if done else ""))


def set_check(item_id, on, by=""):
    """Centang CHECK admin (tugas sudah diperiksa)."""
    return _change(item_id, lambda x: dict(x, check=bool(on), check_by=by if on else "",
                                           check_at=_now() if on else ""))


def delete(item_id):
    return _change(item_id, lambda x: None)


def carry_over(teacher_id, to_month):
    """Salin tugas BELUM selesai bulan sebelumnya ke bulan ini (bagian sama). Jumlah disalin."""
    prev = shift_month(to_month, -1)
    have = {(x.get("section"), x["text"]) for x in items_of(teacher_id, to_month)}
    n = 0
    for x in items_of(teacher_id, prev):
        if not x.get("done") and (x.get("section"), x["text"]) not in have:
            if x.get("section") == "day":         # laporan harian tidak dibawa
                continue
            add(teacher_id, to_month, x.get("section", "week"), x["text"], x.get("report", ""))
            n += 1
    return n


def open_previous(teacher_id, month):
    """Jumlah tugas belum selesai di bulan sebelumnya (tawaran "bawa ke bulan ini")."""
    return sum(1 for x in items_of(teacher_id, shift_month(month, -1))
               if not x.get("done") and x.get("section") != "day")


def summary(teacher_id=None, month=None):
    """Untuk Dashboard: {open_week, open_month, done, unchecked, done_today, texts}."""
    month = month or this_month()
    today = datetime.now().strftime("%Y-%m-%d")
    tid = str(teacher_id).upper() if teacher_id else None
    rows = [x for x in _load() if x.get("month") == month and (tid is None or x["teacher"] == tid)]
    if tid is None:                  # semua guru: agenda pribadi admin tidak ikut dihitung
        rows = [x for x in rows if not x["teacher"].startswith("ADMIN")]
    return {"open_day": [x for x in rows if x.get("section") == "day" and not x.get("done")
                         and x.get("day") == today],
            "today": [x for x in rows if x.get("section") == "day" and x.get("day") == today],
            "open_week": [x for x in rows if x.get("section") == "week" and not x.get("done")],
            "open_month": [x for x in rows if x.get("section") == "month" and not x.get("done")],
            "done": [x for x in rows if x.get("done")],
            "unchecked": [x for x in rows if x.get("done") and not x.get("check")],
            "done_today": [x for x in rows if (x.get("done_at") or "").startswith(today)]}


def all_items():
    return _load()


def delete_teacher(teacher_id):
    tid = str(teacher_id).upper()
    with _lock:
        items = _load()
        keep = [x for x in items if x["teacher"] != tid]
        if len(keep) != len(items):
            _write(keep)
