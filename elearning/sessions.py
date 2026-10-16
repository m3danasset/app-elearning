"""Riwayat masuk/keluar murid & guru, disimpan di  data\\sessions.json  (di samping .exe).

Arsip bulanan: file aktif hanya berisi catatan bulan berjalan (kecil, cepat ditulis tiap
menit). Begitu ganti bulan, sesi bulan-bulan sebelumnya yang sudah selesai dipindah ke
data\\arsip\\sessions-YYYY-MM.json. File arsip tidak ditulis ulang (kecuali murid dihapus),
hanya dibaca saat perlu dan diingat selama file tidak berubah. Tidak ada riwayat dibuang.

Satu catatan per sesi: {"id", "in", "out", "last"}. 'last' diperbarui tiap menit
selama murid masuk. Kalau aplikasi mati mendadak (listrik padam, ditutup paksa)
sehingga 'out' kosong, jam keluar diperkirakan dari 'last' dan ditandai perkiraan.

Pencatatan tidak boleh mengganggu aplikasi: semua kegagalan hanya dicatat di app.log.
"""

import json
import os
import re
from datetime import datetime

from elearning import config as C

FMT = "%Y-%m-%d %H:%M:%S"
ARCHIVE_DIR = os.path.join(C.DATA_DIR, "arsip")
_ARCH_RE = re.compile(r"^sessions-(\d{4}-\d{2})\.json$")
ONLINE_WINDOW = 150      # detik; sesi terbuka dianggap aktif kalau denyutnya sesegar ini
_current = None          # (id, jam masuk) sesi yang sedang terbuka di jalankan ini

_DAYS = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
           "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


# --- baca / tulis -------------------------------------------------------------
def pc_name():
    """Nama komputer ini (seperti di Windows: Settings > System > About)."""
    return os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or ""


def _now():
    return datetime.now().strftime(FMT)


def _parse(text):
    try:
        return datetime.strptime(text, FMT)
    except (TypeError, ValueError):
        return None


_read_cache = {"key": None, "records": []}


def _read():
    """Semua catatan. File hanya dibaca ulang kalau berubah (waktu ubah / ukuran berbeda);
    selebihnya dari ingatan, jadi Panel Admin & Analytics tetap ringan walau riwayat panjang.
    Yang dikembalikan salinan, jadi pemanggil boleh mengubahnya."""
    try:
        st = os.stat(C.SESSIONS_FILE)
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        key = None
    if key is not None and key == _read_cache["key"]:
        return [dict(r) for r in _read_cache["records"]]
    records = _read_file()
    _read_cache["key"] = key
    _read_cache["records"] = records
    return [dict(r) for r in records]


def _read_file():
    try:
        with open(C.SESSIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)
                    and isinstance(r.get("id"), str) and _parse(r.get("in"))]
        raise ValueError("isi file bukan daftar sesi")
    except FileNotFoundError:
        return []
    except Exception as exc:
        C.log(f"data\\sessions.json rusak ({exc!r}) -> dimulai dari kosong")
        try:
            os.replace(C.SESSIONS_FILE, C.SESSIONS_FILE + ".rusak")
        except OSError:
            pass
        return []


def _write(records):
    """Simpan file aktif. Sesi selesai dari bulan sebelumnya dipindah ke arsip dulu."""
    os.makedirs(C.DATA_DIR, exist_ok=True)
    month = datetime.now().strftime("%Y-%m")
    old = {}
    keep = []
    for r in records:
        if r["in"][:7] < month and r.get("out") is not None and not _is_current(r):
            old.setdefault(r["in"][:7], []).append(r)
        else:
            keep.append(r)
    for m, recs in old.items():
        try:
            _archive_add(m, recs)
        except Exception as exc:     # gagal mengarsip: catatan tetap di file aktif
            C.log(f"Gagal mengarsip riwayat {m}: {exc!r}")
            keep.extend(recs)
    if old:
        keep.sort(key=lambda r: r["in"])
    _dump(C.SESSIONS_FILE, keep)


def _dump(path, records):
    tmp = f"{path}.{os.getpid()}.tmp"     # nama unik: aman walau beberapa PC menulis
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# --- arsip bulanan ------------------------------------------------------------------
def _archive_path(month):
    return os.path.join(ARCHIVE_DIR, f"sessions-{month}.json")


def archive_months():
    """Bulan yang punya arsip, urut lama -> baru (mis. ["2026-08", "2026-09"])."""
    try:
        names = os.listdir(ARCHIVE_DIR)
    except OSError:
        return []
    return sorted(m.group(1) for m in map(_ARCH_RE.match, names) if m)


def _archive_add(month, recs):
    """Gabungkan catatan ke arsip bulan itu (tanpa dobel kalau dua PC mengarsip bersamaan)."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    path = _archive_path(month)
    have = _load_json(path)
    seen = {(r["id"], r["in"]) for r in have}
    added = [r for r in recs if (r["id"], r["in"]) not in seen]
    if not added:
        return
    for r in added:
        if r.get("out"):
            r.pop("last", None)      # 'last' hanya perlu selama sesi masih terbuka
    _dump(path, sorted(have + added, key=lambda r: r["in"]))
    C.log(f"Riwayat login {month}: {len(added)} catatan dipindah ke arsip")


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except Exception as exc:
        C.log(f"Arsip {os.path.basename(path)} tidak terbaca: {exc!r}")
        raise
    return [r for r in data if isinstance(r, dict)
            and isinstance(r.get("id"), str) and _parse(r.get("in"))]


_arch_cache = {}   # bulan -> {"key", "records", "by_id", "agg"}


def _archive(month):
    """Isi arsip satu bulan (diingat selama file tidak berubah). Hanya untuk dibaca."""
    path = _archive_path(month)
    try:
        st = os.stat(path)
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        _arch_cache.pop(month, None)
        return None
    hit = _arch_cache.get(month)
    if hit is not None and hit["key"] == key:
        return hit
    try:
        records = _load_json(path)
    except Exception:
        records = []
    by_id = {}
    for r in records:
        by_id.setdefault(r["id"], []).append(r)
    hit = {"key": key, "records": records, "by_id": by_id, "agg": _aggregate(records)}
    _arch_cache[month] = hit
    return hit


def records(since=None):
    """Semua catatan (file aktif + arsip), urut waktu masuk. Hanya untuk DIBACA.

    since: date/datetime; arsip bulan sebelum tanggal itu tidak dibuka sama sekali.
    """
    cur = _read()
    first = since.strftime("%Y-%m") if since is not None else ""
    out = []
    seen = {(r["id"], r["in"]) for r in cur}
    for m in archive_months():
        if m < first:
            continue
        a = _archive(m)
        if a is not None:
            out.extend(r for r in a["records"] if (r["id"], r["in"]) not in seen)
    out.extend(cur)
    return out


def _is_current(rec):
    return (_current is not None and rec.get("out") is None
            and (rec["id"], rec["in"]) == _current)


# --- dipanggil aplikasi ---------------------------------------------------------
def start(student_id):
    """Murid masuk. Sesi lama yang tidak ditutup dirapikan dulu."""
    global _current
    try:
        if _current is not None:
            end()
        records = _read()
        for r in records:
            if r.get("out") is None:       # sisa aplikasi yang mati mendadak
                r["out"] = r.get("last") or r["in"]
                r["auto"] = True
        now = _now()
        records.append({"id": student_id, "in": now, "out": None, "last": now,
                        "pc": pc_name()})
        _write(records)
        _current = (student_id, now)
    except Exception as exc:
        C.log(f"Gagal mencatat masuk {student_id}: {exc!r}")


def _touch(close):
    global _current
    if _current is None:
        return
    try:
        records = _read()
        now = _now()
        for r in records:
            if _is_current(r):
                r["last"] = now
                if close:
                    r["out"] = now
        _write(records)
        if close:
            _current = None
    except Exception as exc:
        C.log(f"Gagal memperbarui riwayat login: {exc!r}")
        if close:
            _current = None


def heartbeat():
    """Tandai murid masih di dalam aplikasi (dipanggil tiap menit)."""
    _touch(close=False)


def end():
    """Murid keluar (tombol Keluar atau jendela ditutup). Aman dipanggil kapan saja."""
    _touch(close=True)


def delete_student(student_id):
    """Hapus seluruh riwayat satu murid."""
    global _current
    try:
        records = _read()
        kept = [r for r in records if r["id"] != student_id]
        if len(kept) != len(records):
            _write(kept)
        if _current is not None and _current[0] == student_id:
            _current = None
        for m in archive_months():
            a = _archive(m)
            if a is not None and student_id in a["by_id"]:
                _dump(_archive_path(m), [r for r in a["records"] if r["id"] != student_id])
    except Exception as exc:
        C.log(f"Gagal menghapus riwayat {student_id}: {exc!r}")


# --- dipakai layar guru -----------------------------------------------------------
def entries(student_id):
    """Riwayat satu murid, terbaru di atas.

    Tiap item: start, end (datetime atau None), seconds, active (masih masuk),
    approx (jam keluar hanya perkiraan karena aplikasi tidak ditutup normal).
    """
    out = []
    mine = [r for r in _read() if r["id"] == student_id]
    seen = {r["in"] for r in mine}
    for m in archive_months():
        a = _archive(m)
        if a is not None:
            mine.extend(r for r in a["by_id"].get(student_id, ()) if r["in"] not in seen)
    for r in mine:
        start_dt = _parse(r["in"])
        active = _is_current(r)
        end_dt = _parse(r.get("out")) if r.get("out") else None
        approx = bool(r.get("auto"))
        if end_dt is None:
            end_dt = _parse(r.get("last")) or start_dt
            approx = not active
        seconds = max(0, int((end_dt - start_dt).total_seconds()))
        out.append({"start": start_dt, "end": None if active else end_dt,
                    "seconds": seconds, "active": active, "approx": approx})
    out.sort(key=lambda e: e["start"], reverse=True)
    return out


def _aggregate(recs, now=None):
    """{id: {count, total, last_in, last_seen, online}} dari sekumpulan catatan."""
    result = {}
    for r in recs:
        start_dt = _parse(r["in"])
        last_dt = _parse(r.get("last")) or start_dt
        end_dt = _parse(r.get("out")) if r.get("out") else None
        seen = end_dt or last_dt
        active = now is not None and (_is_current(r) or (
            r.get("out") is None
            and (now - last_dt).total_seconds() <= ONLINE_WINDOW))
        s = result.setdefault(r["id"], {"count": 0, "total": 0, "last_in": None,
                                        "last_seen": None, "online": False})
        s["count"] += 1
        s["total"] += max(0, int((seen - start_dt).total_seconds()))
        if s["last_in"] is None or start_dt > s["last_in"]:
            s["last_in"] = start_dt
        if s["last_seen"] is None or seen > s["last_seen"]:
            s["last_seen"] = seen
        if active:
            s["online"] = True
    return result


def overview(ids=None):
    """Ringkasan aktivitas per ID (murid maupun guru) sepanjang masa, dipakai Panel Admin.

    Mengembalikan {id: {count, total, last_in, last_seen, online}}. ID yang belum
    pernah masuk tidak ada di hasil. 'online' = ada sesi terbuka yang denyutnya
    (diperbarui tiap menit) masih baru, jadi hanya akurat kalau aplikasi yang sedang
    dipakai murid/guru menulis ke file data yang sama dengan yang dibaca admin.
    Arsip dijumlahkan sekali per file lalu diingat, jadi tetap ringan walau bertahun-tahun.
    """
    cur = _read()
    month = datetime.now().strftime("%Y-%m")
    # catatan bulan lalu yang masih di file aktif (belum sempat diarsip / dua PC berselisih)
    old = {(r["id"], r["in"]) for r in cur if r["in"][:7] < month}
    parts = [_aggregate(cur, datetime.now())]
    for m in archive_months():
        a = _archive(m)
        if a is None:
            continue
        if any(k[1][:7] == m for k in old):     # jarang: hitung ulang tanpa yang dobel
            parts.append(_aggregate([r for r in a["records"]
                                     if (r["id"], r["in"]) not in old]))
        else:
            parts.append(a["agg"])
    wanted = None if ids is None else set(ids)
    result = {}
    for part in parts:
        for rid, p in part.items():
            if wanted is not None and rid not in wanted:
                continue
            s = result.get(rid)
            if s is None:
                result[rid] = dict(p)
                continue
            s["count"] += p["count"]
            s["total"] += p["total"]
            s["online"] = s["online"] or p["online"]
            for k in ("last_in", "last_seen"):
                if p[k] is not None and (s[k] is None or p[k] > s[k]):
                    s[k] = p[k]
    return result


def format_duration(seconds):
    """Durasi singkat: '<1 Mnt', '25 Mnt', '3.5 Jam', '2 Jam'."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "<1 Mnt"
    if seconds < 3600:
        return f"{seconds // 60} Mnt"
    hours = f"{seconds / 3600:.1f}".rstrip("0").rstrip(".")
    return f"{hours} Jam"


def format_date(dt):
    return f"{_DAYS[dt.weekday()]}, {dt.day} {_MONTHS[dt.month - 1]} {dt.year}"


def format_time(dt):
    return dt.strftime("%H:%M")
