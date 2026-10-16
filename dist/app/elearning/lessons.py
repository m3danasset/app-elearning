"""Daftar pelajaran (video) tiap kursus, dibaca otomatis dari folder.

Taruh video DI LUAR .exe (tanpa build ulang), satu folder per kursus:
    <folder .exe>\\assets\\lessons\\basic-1\\Pengenalan Antarmuka.mp4
    <folder .exe>\\assets\\lessons\\basic-1\\Navigasi Viewport.mp4

- Nama folder = id kursus (basic-1, basic-2, intermediate-1, intermediate-2, ai-character,
  ai-interior, superkids-1 ... superkids-6, trial-animation, trial-modeling). Nama kursus
  seperti "BASIC 1" juga dikenali (huruf besar/kecil dan spasi/tanda hubung diabaikan).
- JUDUL pelajaran = nama file video apa adanya (tanpa .mp4). Tidak perlu penomoran khusus.
- URUTAN = urut nama file, dengan angka dibaca sebagai angka (2 sebelum 10).
  Kalau mau mengatur urutan, awali nama file dengan angka: "01 Pengenalan.mp4".
- Format video: .mp4 .mov .mkv .avi .webm .m4v

Subtitle (opsional): taruh di folder yang sama, namanya mengikuti video + kode bahasa:
    Pengenalan Antarmuka.id.srt   (Indonesia)      Pengenalan Antarmuka.en.srt   (English)
Format .srt, .vtt, .ass. Murid memilih subtitle lewat tombol CC di pemutar.

Kalau folder kursus belum ada videonya, dipakai video latar login (assets\\video) sebagai
contoh "01. Judul Blablabla" supaya pemutar bisa dicoba dulu (dengan subtitle contoh).
"""

import os
import re

from elearning import config as C

VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
SUB_EXTS = (".srt", ".vtt", ".ass", ".ssa")
LANG_NAMES = {
    "id": "Indonesia", "ind": "Indonesia", "en": "English", "eng": "English",
    "ms": "Melayu", "may": "Melayu", "msa": "Melayu", "zh": "Mandarin", "chi": "Mandarin",
    "zho": "Mandarin", "ja": "Jepang", "jpn": "Jepang", "ko": "Korea", "kor": "Korea",
    "ar": "Arab", "ara": "Arab",
    "indonesia": "Indonesia", "indonesian": "Indonesia", "bahasa": "Indonesia",
    "id-id": "Indonesia", "english": "English", "inggris": "English", "en-us": "English",
    "en-gb": "English",
}
SAMPLE_COUNT = 3
SAMPLE_TITLE = "Judul Blablabla"


def _videos(folder):
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    return [n for n in names if n.lower().endswith(VIDEO_EXTS) and not n.startswith(".")]


def lang_label(code):
    code = (code or "").strip()
    return LANG_NAMES.get(code.lower(), code.upper()) if code else "Subtitle"


def subtitles_for(video_path):
    """File subtitle di samping video: [{path, lang, label}].

    Nama subtitle = nama video (huruf besar/kecil tidak berpengaruh) + (opsional) bahasa:
    "Judul.srt", "Judul.id.srt", "Judul.en.srt", "Judul - Indonesian.srt", "Judul_en.srt".
    """
    folder, name = os.path.split(video_path)
    stem = os.path.splitext(name)[0].lower()
    out = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return out
    for n in names:
        base, ext = os.path.splitext(n)
        if ext.lower() not in SUB_EXTS or n.startswith("."):
            continue
        low = base.lower().strip()
        if low == stem:
            lang = ""
        elif low.startswith(stem) and not low[len(stem)].isalnum():
            lang = base[len(stem):].strip(" ._-()[]")
        else:
            continue
        out.append({"path": os.path.join(folder, n), "lang": lang,
                    "label": lang_label(lang)})
    return out


def _srt_time(sec):
    return f"00:{sec // 60:02d}:{sec % 60:02d},000"


def _demo_subtitles():
    """Subtitle contoh (Indonesia & English, 10 menit) untuk video contoh. Dibuat sekali."""
    folder = os.path.join(C.DATA_DIR, "_contoh_subtitle")
    out = []
    for lang, text in (("id", "Ini contoh subtitle Bahasa Indonesia"),
                       ("en", "This is a sample English subtitle")):
        path = os.path.join(folder, f"contoh.{lang}.srt")
        if not os.path.exists(path):
            try:
                os.makedirs(folder, exist_ok=True)
                cues = []
                for i in range(120):
                    cues.append(f"{i + 1}\n{_srt_time(i * 5)} --> {_srt_time(i * 5 + 4)}\n"
                                f"{text} #{i + 1}\n")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(cues))
            except OSError as exc:
                C.log(f"Subtitle contoh gagal dibuat: {exc!r}")
                continue
        out.append({"path": path, "lang": lang, "label": lang_label(lang)})
    return out


def _norm(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def lesson_folder(course):
    """Folder video kursus: assets\\lessons\\<id>; nama folder juga boleh berupa judul kursus."""
    exact = os.path.join(C.LESSON_DIR, course["id"])
    if os.path.isdir(exact):
        return exact
    wanted = {_norm(course["id"]), _norm(course.get("title", ""))}
    try:
        for name in sorted(os.listdir(C.LESSON_DIR)):
            if _norm(name) in wanted and os.path.isdir(os.path.join(C.LESSON_DIR, name)):
                return os.path.join(C.LESSON_DIR, name)
    except OSError:
        pass
    return exact


def lessons_for(course):
    """Daftar pelajaran kursus: [{no, title, label, path, sample, subs}], urut nama file."""
    folder = lesson_folder(course)
    names = sorted(_videos(folder), key=_natural_key)
    C.log(f"Pelajaran {course['id']}: folder={folder!r} ada={os.path.isdir(folder)} "
          f"video={len(names)}")
    out = []
    for i, name in enumerate(names, 1):
        path = os.path.join(folder, name)
        title = os.path.splitext(name)[0]
        subs = subtitles_for(path)
        C.log(f"  video {name!r}: subtitle ditemukan={[x['label'] for x in subs]}")
        out.append({"no": f"{i:02d}", "title": title, "label": title, "path": path,
                    "sample": False, "subs": subs})
    if out:
        return out

    # Belum ada video: 3 pelajaran contoh memakai video latar login
    fallback = next((os.path.join(C.VIDEO_DIR, n) for n in _videos(C.VIDEO_DIR)), None)
    demo = _demo_subtitles() if fallback else []
    for i in range(1, SAMPLE_COUNT + 1):
        no = f"{i:02d}"
        out.append({"no": no, "title": SAMPLE_TITLE, "label": f"{no}. {SAMPLE_TITLE}",
                    "path": fallback, "sample": fallback is not None, "subs": demo})
    return out
