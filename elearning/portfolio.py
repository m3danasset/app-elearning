"""Portfolio murid: gambar dan video hasil karya, dipisah per murid dan per kursus.

Murid mengunggah lewat tombol Portfolio di sidebar kursus. File DISALIN ke:

    data\\portfolio\\<ID murid>\\<id kursus>\\<tanggal-jam>_<nama file>.<ext>

Thumbnail kecil dibuat otomatis dan disimpan di folder _thumbs di sebelahnya,
lalu ditampilkan di layar guru (tab Portfolio). Folder data\\ tidak disentuh
update.bat maupun build.bat, jadi portfolio aman saat revisi kode.

Hanya memakai Pillow dan OpenCV yang memang sudah ikut di dalam .exe.

Kalau guru dan murid memakai PC berbeda: buat file  data\\portfolio_path.txt  yang
isinya satu baris lokasi folder portfolio bersama (mis. \\\\PC-GURU\\portfolio), di
semua PC. Tanpa file itu, portfolio disimpan di data\\portfolio\\ PC masing-masing.
"""

import os
import re
import shutil
from datetime import datetime

from elearning import config as C
from elearning import photos

Image = photos.Image
HAS_PIL = photos.HAS_PIL

try:
    import cv2
except Exception as exc:  # pragma: no cover
    cv2 = None
    C.log(f"OpenCV tidak tersedia, thumbnail video memakai kotak polos: {exc!r}")

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
MAX_MB = 1000                 # batas ukuran satu file
THUMB_W, THUMB_H = 176, 110   # ukuran thumbnail

PATH_FILE = os.path.join(C.DATA_DIR, "portfolio_path.txt")
_NAME_RE = re.compile(r"^(\d{8}-\d{6})(?:-\d+)?_(.*)$")


# --- lokasi folder -----------------------------------------------------------
def root():
    """Folder utama portfolio (bisa dialihkan lewat data\\portfolio_path.txt)."""
    try:
        with open(PATH_FILE, "r", encoding="utf-8-sig") as f:
            custom = f.readline().strip().strip('"')
        if custom:
            return custom
    except OSError:
        pass
    return os.path.join(C.DATA_DIR, "portfolio")


def _safe_id(value):
    return "".join(ch for ch in str(value) if ch.isalnum() or ch in "-_") or "x"


def course_dir(student_id, course_id):
    return os.path.join(root(), _safe_id(str(student_id).upper()), _safe_id(course_id))


def _thumb_dir(student_id, course_id):
    return os.path.join(course_dir(student_id, course_id), "_thumbs")


def kind_of(path):
    """\"image\", \"video\", atau None kalau formatnya tidak didukung."""
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    return None


def _clean_stem(name):
    stem = os.path.splitext(os.path.basename(name))[0]
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "-", stem).strip(" .-_")
    stem = re.sub(r"[\s-]+", "-", stem)
    return (stem or "file")[:50]


# --- thumbnail ---------------------------------------------------------------
def _cover(img, w, h):
    """Perkecil lalu potong dari tengah sampai tepat w x h."""
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    nw, nh = max(w, round(iw * scale)), max(h, round(ih * scale))
    img = img.resize((nw, nh), photos._RESAMPLE)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _video_frame(path):
    """Satu gambar dari video (sedikit setelah awal supaya tidak hitam). None kalau gagal."""
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            return None
        total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        if total > 60:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * 0.1))
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        if not ok:
            return None
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    finally:
        cap.release()


def _make_thumb(src_path, kind, dest_path):
    """Buat thumbnail JPEG. Kembalikan True kalau gambar aslinya terbaca."""
    img = None
    if kind == "image":
        with Image.open(src_path) as opened:
            opened.load()
            img = photos._flatten(photos._fix_orientation(opened))
    else:
        img = _video_frame(src_path)
    ok = img is not None
    if img is None:
        img = Image.new("RGB", (THUMB_W, THUMB_H), (38, 43, 57))   # kotak polos
    else:
        img = _cover(img, THUMB_W, THUMB_H)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    tmp = dest_path + ".tmp"
    img.save(tmp, format="JPEG", quality=82)
    os.replace(tmp, dest_path)
    return ok


def thumb_path(item_path):
    folder, name = os.path.split(item_path)
    return os.path.join(folder, "_thumbs", name + ".jpg")


def load_thumb(item_path):
    """Gambar thumbnail (Pillow). Dibuat ulang kalau belum ada; kotak polos kalau gagal."""
    if not HAS_PIL:
        return None
    tp = thumb_path(item_path)
    try:
        if not os.path.isfile(tp):
            _make_thumb(item_path, kind_of(item_path) or "image", tp)
        with Image.open(tp) as f:
            return f.convert("RGB")
    except Exception as exc:
        C.log(f"Thumbnail {item_path!r} gagal: {exc!r}")
        return Image.new("RGB", (THUMB_W, THUMB_H), (38, 43, 57))


# --- menambah / membaca / menghapus ---------------------------------------------
def add_file(student_id, course_id, source_path):
    """Salin file milik murid ke portfolio. Mengembalikan path file baru.

    Melempar ValueError (pesan siap tampil) kalau file tidak bisa dipakai.
    """
    if not HAS_PIL:
        raise ValueError("Pillow tidak tersedia, portfolio tidak bisa dipakai.")
    kind = kind_of(source_path)
    if kind is None:
        raise ValueError("format tidak didukung")
    try:
        size = os.path.getsize(source_path)
    except OSError:
        raise ValueError("file tidak bisa dibaca")
    if size > MAX_MB * 1024 * 1024:
        raise ValueError(f"terlalu besar (maksimal {MAX_MB} MB)")

    folder = course_dir(student_id, course_id)
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ext = os.path.splitext(source_path)[1].lower()
    stem = _clean_stem(source_path)
    final, n = os.path.join(folder, f"{stamp}_{stem}{ext}"), 1
    while os.path.exists(final):   # nama sama dalam detik yang sama
        n += 1
        final = os.path.join(folder, f"{stamp}-{n}_{stem}{ext}")

    part = final + ".part"
    try:
        shutil.copyfile(source_path, part)
        os.replace(part, final)    # muncul utuh atau tidak sama sekali
    except OSError as exc:
        _silent_remove(part)
        C.log(f"Gagal menyalin {source_path!r} ke portfolio: {exc!r}")
        raise ValueError("gagal disalin (disk penuh atau file sedang dipakai?)")

    try:
        readable = _make_thumb(final, kind, thumb_path(final))
    except Exception as exc:
        _silent_remove(final)
        _silent_remove(thumb_path(final))
        C.log(f"File {source_path!r} tidak bisa dibaca sebagai {kind}: {exc!r}")
        raise ValueError("gambar rusak atau tidak bisa dibaca")
    if not readable and kind == "video":
        C.log(f"Thumbnail video {final!r} memakai kotak polos (video tidak terbaca OpenCV).")
    return final


def _silent_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _parse_name(filename):
    """(waktu unggah, nama tampil) dari nama file tersimpan."""
    m = _NAME_RE.match(filename)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S"), m.group(2)
        except ValueError:
            pass
    return None, filename


def list_items(student_id, course_id):
    """Isi portfolio satu murid di satu kursus, terbaru dulu. List dict."""
    folder = course_dir(student_id, course_id)
    items = []
    try:
        names = os.listdir(folder)
    except OSError:
        return items
    for name in names:
        path = os.path.join(folder, name)
        if name.startswith(".") or name.endswith((".part", ".tmp")) or not os.path.isfile(path):
            continue
        kind = kind_of(name)
        if kind is None:
            continue
        added, shown = _parse_name(name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        items.append({"path": path, "name": shown, "kind": kind, "size": st.st_size,
                      "added": added or datetime.fromtimestamp(st.st_mtime)})
    items.sort(key=lambda i: i["added"], reverse=True)
    return items


def count(student_id, course_id):
    return len(list_items(student_id, course_id))


def remove_item(path):
    """Hapus satu file portfolio beserta thumbnail-nya. Hanya file di dalam folder portfolio."""
    real, base = os.path.realpath(path), os.path.realpath(root())
    if os.path.commonpath([real, base]) != base:
        raise ValueError("File di luar folder portfolio.")
    _silent_remove(thumb_path(path))
    os.remove(path)


def delete_student(student_id):
    """Hapus seluruh portfolio seorang murid (dipanggil saat murid dihapus)."""
    folder = os.path.join(root(), _safe_id(str(student_id).upper()))
    shutil.rmtree(folder, ignore_errors=True)


def format_size(n):
    if n >= 1024 * 1024 * 1024:
        return f"{n / 1024 ** 3:.1f} GB"
    if n >= 1024 * 1024:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{max(1, n // 1024)} KB"


def open_file(path):
    """Buka file dengan aplikasi bawaan Windows (penampil gambar / pemutar video)."""
    if hasattr(os, "startfile"):
        os.startfile(path)   # noqa: S606 - hanya path file milik portfolio
    else:  # pragma: no cover  (untuk uji di Linux/Mac)
        import subprocess
        import sys
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])
