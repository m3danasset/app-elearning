"""Progres belajar murid: lanjut tonton, catatan, emote, dan jawaban kuis.

Satu file per murid:  data\\progress\\<ID>.json   (folder data yang sama dengan guru)
  {"courses": {id kursus: {judul video: {
        "pos"  : detik terakhir yang ditonton (untuk lanjut tonton),
        "pct"  : posisi terjauh yang pernah dicapai (% durasi),
        "sec", "dur", "done", "views", "first", "last",
        "seen" : bagian video yang BENAR-BENAR ditonton: 100 bit (1 bit = 1 % durasi) dalam
                 heksadesimal. Geser ke akhir tidak menambah bit (dipakai untuk badge).
        "old_done": video sudah selesai sebelum "seen" ada (data lama tetap dihitung),
        "note", "note_t"             : catatan singkat (murid dewasa),
        "emote", "emote_t"           : review SUPERKIDS, satu emote per video}}},
   "quiz": {id kuis: {"answer", "correct", "t", "course", "lesson", "question"}}}

Kenapa satu file per murid: posisi video disimpan tiap beberapa detik. File kecil milik
satu murid saja cepat ditulis, dan PC lain (guru / murid lain) tidak pernah menimpanya.
Guru hanya membaca. Semua kegagalan cuma dicatat di app.log, pemutar tetap jalan.
"""

import json
import os
import time
from datetime import datetime

from elearning import config as C
from elearning import lessons

PROGRESS_DIR = os.path.join(C.DATA_DIR, "progress")
OLD_FILE = os.path.join(C.DATA_DIR, "progress.json")     # format lama (satu file)
FMT = "%Y-%m-%d %H:%M:%S"
DONE_PCT = 90          # video dianggap selesai kalau ditonton sejauh ini
SAVE_EVERY = 5         # detik: posisi video disimpan sesering ini selama diputar
NOTE_WORDS = 30
SEGS = 100             # "seen": durasi dibagi 100 bagian
WATCH_PCT = 80         # badge: video dihitung selesai kalau >= sekian % BENAR-BENAR ditonton
last_play = 0.0        # time.time() terakhir video pelajaran berjalan (dibaca pelacak badge)

EMOTES = (("bosan", "Bosan"), ("seru", "Seru"), ("paham", "Paham"), ("bingung", "Bingung"))
_OLD_EMOTE = {"capek": "bosan", "keren": "seru"}   # pilihan dari versi sebelumnya
EMOTE_LABEL = dict(EMOTES)
EMOTE_LABEL_EN = {"bosan": "Bored", "seru": "Fun", "paham": "Got it", "bingung": "Confused"}

_docs = {}       # ID murid -> {"key": (mtime, size), "doc": {...}}  (cache baca)
_live = {}       # (murid, kursus, judul) -> keadaan saat video diputar


def _now():
    return datetime.now().strftime(FMT)


def _path(sid):
    safe = "".join(ch for ch in str(sid).upper() if ch.isalnum() or ch in "-_") or "X"
    return os.path.join(PROGRESS_DIR, safe + ".json")


def _empty():
    return {"courses": {}, "quiz": {}}


def _old_part(sid):
    """Data dari format lama data\\progress.json (versi sebelumnya), kalau ada."""
    try:
        with open(OLD_FILE, encoding="utf-8") as f:
            old = json.load(f)
        part = old.get(sid) if isinstance(old, dict) else None
        if isinstance(part, dict):
            return {"courses": part, "quiz": {}}
    except Exception:
        pass
    return None


def load(sid):
    """Isi file satu murid (dibaca ulang hanya kalau file berubah). Jangan diubah langsung."""
    path = _path(sid)
    try:
        st = os.stat(path)
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        hit = _docs.get(sid)
        if hit is not None and hit["key"] is None:
            return hit["doc"]
        doc = _old_part(sid) or _empty()
        _docs[sid] = {"key": None, "doc": doc}
        return doc
    hit = _docs.get(sid)
    if hit is not None and hit["key"] == key:
        return hit["doc"]
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        if not isinstance(doc, dict):
            raise ValueError("bukan objek")
        doc.setdefault("courses", {})
        doc.setdefault("quiz", {})
    except Exception as exc:
        C.log(f"Progres {sid} tidak terbaca ({exc!r})")
        return hit["doc"] if hit else _empty()
    _docs[sid] = {"key": key, "doc": doc}
    return doc


def _write(sid, doc):
    try:
        os.makedirs(PROGRESS_DIR, exist_ok=True)
        path = _path(sid)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        st = os.stat(path)
        _docs[sid] = {"key": (st.st_mtime_ns, st.st_size), "doc": doc}
        return True
    except Exception as exc:
        C.log(f"Gagal menyimpan progres {sid}: {exc!r}")
        return False


def _edit(sid, cid, title, change):
    """Ubah satu video milik satu murid lalu simpan. Mengembalikan catatannya."""
    doc = json.loads(json.dumps(load(sid)))          # salinan: cache tidak ikut berubah
    rec = doc["courses"].setdefault(cid, {}).setdefault(
        title, {"pos": 0, "pct": 0, "sec": 0, "dur": 0, "done": False, "views": 0,
                "first": _now()})
    change(rec)
    rec["last"] = _now()
    _write(sid, doc)
    return rec


def record(sid, cid, title):
    """Catatan satu video (dict kosong kalau belum pernah dibuka)."""
    return load(sid)["courses"].get(cid, {}).get(title, {})


# --- dipanggil pemutar ----------------------------------------------------------------
def begin(sid, cid, title):
    """Video dibuka: catat kunjungan. Mengembalikan detik untuk lanjut tonton (0 = awal)."""
    rec = _edit(sid, cid, title, lambda r: r.__setitem__("views", int(r.get("views", 0)) + 1))
    _live[(sid, cid, title)] = {"pct": int(rec.get("pct", 0)), "done": bool(rec.get("done")),
                                "pos": float(rec.get("pos", 0)), "dur": float(rec.get("dur", 0)),
                                "saved": float(rec.get("pos", 0)), "saved_t": 0.0,
                                "seen": seen_bits(rec), "prev": None}
    return resume_pos(rec)


def seen_bits(rec):
    try:
        return int(rec.get("seen") or "0", 16)
    except (TypeError, ValueError):
        return 0


def watched_pct(rec):
    """% durasi yang benar-benar ditonton (bukan posisi terjauh)."""
    return bin(seen_bits(rec)).count("1") * 100 // SEGS


def completed(rec):
    """Selesai untuk badge: >= WATCH_PCT % benar-benar ditonton, atau sudah selesai sebelum
    pencatatan "seen" ada (data lama)."""
    if rec.get("old_done") or ("seen" not in rec and rec.get("done")):
        return True
    return watched_pct(rec) >= WATCH_PCT


def _mark_seen(live, p0, p1, dur):
    """Tandai bagian p0..p1 (detik) sebagai ditonton."""
    a = max(0, min(SEGS - 1, int(p0 * SEGS / dur)))
    b = max(0, min(SEGS - 1, int(p1 * SEGS / dur)))
    for i in range(a, b + 1):
        live["seen"] |= 1 << i


def resume_pos(rec):
    pos, dur = float(rec.get("pos", 0) or 0), float(rec.get("dur", 0) or 0)
    if pos < 3 or (dur and pos >= dur - 5):     # hampir selesai / sudah selesai: dari awal
        return 0.0
    return pos


def update(sid, cid, title, pos, dur, ended=False, now=None):
    """Dipanggil berkali-kali saat video berjalan. Menulis file paling sering tiap
    SAVE_EVERY detik (posisi), atau langsung saat video selesai / naik 10 %."""
    if dur <= 0:
        return
    global last_play
    now = time.time() if now is None else now
    key = (sid, cid, title)
    live = _live.setdefault(key, {"pct": 0, "done": False, "pos": 0.0, "dur": 0.0,
                                  "saved": 0.0, "saved_t": 0.0, "seen": 0, "prev": None})
    live.setdefault("seen", 0)
    if not ended:
        last_play = now
        prev = live.get("prev")
        # maju wajar (maks. ~2x kecepatan) = ditonton; lompat / geser tidak dihitung
        if prev is not None and 0 < pos - prev[0] <= (now - prev[1]) * 2.2 + 0.6:
            _mark_seen(live, prev[0], pos, dur)
        live["prev"] = (float(pos), now)
    else:
        live["prev"] = None
    pct = 100 if ended else min(100, int(pos * 100 / dur))
    done = ended or pct >= DONE_PCT
    live["pos"], live["dur"] = (0.0 if ended else float(pos)), float(dur)
    if not ended:
        live["ended_saved"] = False
    big = (pct // 10 > live["pct"] // 10) or (done and not live["done"]) or ended
    moved = abs(live["pos"] - live["saved"]) >= 1
    if not big and not (moved and now - live["saved_t"] >= SAVE_EVERY):
        return
    if ended and live.get("ended_saved"):
        return
    _save_live(sid, cid, title, live, pct, done, ended)
    live["saved_t"] = now
    if ended:
        live["ended_saved"] = True


def _save_live(sid, cid, title, live, pct, done, ended):
    def change(rec):
        if "seen" not in rec and rec.get("done"):
            rec["old_done"] = True        # selesai sebelum pencatatan "seen": tetap dihitung
        rec["pos"] = int(live["pos"])
        rec["pct"] = max(int(rec.get("pct", 0)), pct)
        rec["sec"] = max(int(rec.get("sec", 0)), int(live["dur"] if ended else live["pos"]))
        rec["dur"] = int(live["dur"])
        rec["done"] = bool(rec.get("done")) or done
        rec["seen"] = format(seen_bits(rec) | live.get("seen", 0), "x")
    _edit(sid, cid, title, change)
    live["pct"] = max(live["pct"], pct)
    live["done"] = live["done"] or done
    live["saved"] = live["pos"]


def flush(sid, cid, title):
    """Video ditinggalkan / aplikasi ditutup: simpan posisi terakhir (maks. 1 tulis)."""
    live = _live.get((sid, cid, title))
    if not live or not live.get("dur") or abs(live["pos"] - live["saved"]) < 1:
        return
    pct = min(100, int(live["pos"] * 100 / live["dur"]))
    _save_live(sid, cid, title, live, pct, pct >= DONE_PCT, False)


def last_lesson(sid, cid):
    """Judul video yang terakhir dibuka di kursus itu (untuk lanjut tonton), atau None."""
    best, when = None, ""
    for title, rec in load(sid)["courses"].get(cid, {}).items():
        if rec.get("views") and rec.get("last", "") > when:
            best, when = title, rec.get("last", "")
    return best


# --- catatan & emote --------------------------------------------------------------------
def count_words(text):
    return len(text.split())


def set_note(sid, cid, title, text):
    text = " ".join(text.split()[:NOTE_WORDS]) if text.strip() else ""

    def change(rec):
        if text:
            rec["note"], rec["note_t"] = text, _now()
        else:
            rec.pop("note", None)
            rec.pop("note_t", None)
    if (record(sid, cid, title).get("note") or "") == text:
        return
    _edit(sid, cid, title, change)


def emote_of(rec):
    """Emote (review) murid untuk satu video, atau None. Data versi lama
    ("emotes" per detik) dibaca sebagai emote yang terakhir dipilih."""
    key = rec.get("emote")
    if not key:
        old = rec.get("emotes") or {}
        key = max(old, key=lambda k: old[k].get("t", "")) if old else None
    key = _OLD_EMOTE.get(key, key)
    return key if key in EMOTE_LABEL else None


def set_emote(sid, cid, title, key):
    """Satu emote per video (seperti review). Memilih emote lain menggantikan yang lama."""
    if key not in EMOTE_LABEL or emote_of(record(sid, cid, title)) == key:
        return False

    def change(rec):
        rec["emote"], rec["emote_t"] = key, _now()
        rec.pop("emotes", None)
    _edit(sid, cid, title, change)
    return True


# --- kuis ----------------------------------------------------------------------------------
def answers(sid):
    return load(sid).get("quiz", {})


def save_answer(sid, quiz, answer, correct):
    doc = json.loads(json.dumps(load(sid)))
    doc.setdefault("quiz", {})[quiz["id"]] = {
        "answer": answer, "correct": correct, "t": _now(), "course": quiz["course"],
        "lesson": quiz["lesson"], "question": quiz["question"]}
    return _write(sid, doc)


# --- dipakai guru / export -----------------------------------------------------------------
def all_docs():
    """{ID murid: isi file} semua murid (hanya dibaca)."""
    out = {}
    try:
        names = os.listdir(PROGRESS_DIR)
    except OSError:
        names = []
    for n in names:
        if n.endswith(".json"):
            sid = n[:-5]
            out[sid] = load(sid)
    try:      # murid yang masih tersimpan di format lama saja
        with open(OLD_FILE, encoding="utf-8") as f:
            old = json.load(f)
        for sid, part in (old.items() if isinstance(old, dict) else ()):
            if sid not in out and isinstance(part, dict):
                out[sid] = {"courses": part, "quiz": {}}
    except Exception:
        pass
    return out


def all_progress():
    """{ID murid: {id kursus: {judul: catatan}}} (hanya dibaca)."""
    return {sid: d.get("courses", {}) for sid, d in all_docs().items()}


def lesson_count(course):
    """Jumlah video pelajaran asli di folder kursus (tanpa video contoh, tanpa log)."""
    try:
        return len(lessons._videos(lessons.lesson_folder(course)))
    except Exception:
        return 0


def lesson_titles(course):
    """Judul video kursus berurutan seperti di aplikasi (tanpa log)."""
    try:
        names = sorted(lessons._videos(lessons.lesson_folder(course)), key=lessons._natural_key)
        return [os.path.splitext(n)[0] for n in names]
    except Exception:
        return []


def delete_student(sid):
    try:
        if os.path.exists(_path(sid)):
            os.remove(_path(sid))
        _docs.pop(sid, None)
    except Exception as exc:
        C.log(f"Gagal menghapus progres {sid}: {exc!r}")
