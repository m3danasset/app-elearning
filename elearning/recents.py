"""Riwayat "Terakhir dibuka" untuk search palette (Ctrl+K), per akun.

Disimpan di data\\recents.json:  {ID akun: [{"key": "...", "t": waktu}, ...]}
Yang disimpan hanya kunci (mis. "course:basic-1", "student:PB001"); judul dan
fungsinya diambil dari data terbaru saat palette dibuka, jadi murid / kursus yang
sudah dihapus atau diganti namanya tidak tampil salah.

Akun trial dipakai bersama: riwayatnya hanya disimpan di memori (tidak ke file).
"""

import json
import os
import threading
import time

from elearning import config as C

RECENTS_FILE = os.path.join(C.DATA_DIR, "recents.json")
MAX_PER_USER = 20

_lock = threading.Lock()
_memory = {}     # riwayat yang tidak disimpan ke file (akun trial)
_data = None     # isi file (dimuat sekali)


def _load():
    global _data
    if _data is not None:
        return _data
    data = {}
    try:
        with open(RECENTS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            for uid, rows in raw.items():
                if isinstance(rows, list):
                    data[str(uid)] = [r for r in rows
                                      if isinstance(r, dict) and isinstance(r.get("key"), str)]
    except FileNotFoundError:
        pass
    except Exception as exc:
        C.log(f"Riwayat cari rusak, dimulai dari kosong: {exc!r}")
    _data = data
    return _data


def _save(data):
    try:
        os.makedirs(C.DATA_DIR, exist_ok=True)
        tmp = RECENTS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, RECENTS_FILE)  # tulis utuh atau tidak sama sekali
    except Exception as exc:
        C.log(f"Riwayat cari gagal disimpan: {exc!r}")


def get(user_id, persist=True):
    """Kunci yang terakhir dibuka (terbaru dulu)."""
    with _lock:
        store = _load() if persist else _memory
        return [r["key"] for r in store.get(str(user_id), [])]


def add(user_id, key, persist=True):
    if not user_id or not key:
        return
    with _lock:
        store = _load() if persist else _memory
        rows = [r for r in store.get(str(user_id), []) if r.get("key") != key]
        rows.insert(0, {"key": key, "t": int(time.time())})
        store[str(user_id)] = rows[:MAX_PER_USER]
        if persist:
            _save(store)
