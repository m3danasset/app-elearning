"""Foto profil murid.

Guru memilih foto (JPG/PNG/dll) lewat layar guru. Foto dipotong persegi dari
tengah, diperkecil ke 256x256, lalu disimpan sebagai  data\\photos\\<ID>.png
(di samping .exe). Folder data\\ tidak disentuh update.bat.

Hanya memakai Pillow yang memang sudah ikut di dalam .exe. Kalau Pillow tidak
ada, aplikasi tetap jalan dan murid memakai lingkaran berisi inisial.
"""

import math
import os

from elearning import config as C

try:
    from PIL import Image
    HAS_PIL = True
except Exception as exc:  # pragma: no cover
    Image = None
    HAS_PIL = False
    C.log(f"Pillow tidak tersedia, foto profil dinonaktifkan: {exc!r}")

try:
    from PIL import ImageTk
except Exception:
    ImageTk = None

STORED_SIZE = 256
_RESAMPLE = getattr(getattr(Image, "Resampling", Image), "LANCZOS", None) if Image else None
_masks = {}


def _safe(student_id):
    return "".join(ch for ch in str(student_id).upper() if ch.isalnum() or ch in "-_")


def photo_path(student_id):
    return os.path.join(C.PHOTO_DIR, _safe(student_id) + ".png")


def has_photo(student_id):
    return bool(student_id) and os.path.isfile(photo_path(student_id))


# --- menyimpan foto ----------------------------------------------------------
def _fix_orientation(img):
    """Putar sesuai data EXIF (foto HP sering tersimpan 'miring')."""
    try:
        orientation = img.getexif().get(274)
    except Exception:
        return img
    t = getattr(Image, "Transpose", Image)
    ops = {2: t.FLIP_LEFT_RIGHT, 3: t.ROTATE_180, 4: t.FLIP_TOP_BOTTOM,
           5: t.TRANSPOSE, 6: t.ROTATE_270, 7: t.TRANSVERSE, 8: t.ROTATE_90}
    return img.transpose(ops[orientation]) if orientation in ops else img


def _flatten(img):
    """Ubah ke RGB; bagian transparan jadi putih."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img)
    return img.convert("RGB")


def set_photo(student_id, source_path):
    """Jadikan file gambar ini foto profil murid. Error dilempar kalau file tidak bisa dipakai."""
    if not HAS_PIL:
        raise RuntimeError("Pillow tidak tersedia")
    with Image.open(source_path) as opened:
        opened.load()
        img = _flatten(_fix_orientation(opened))
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((STORED_SIZE, STORED_SIZE), _RESAMPLE)

    os.makedirs(C.PHOTO_DIR, exist_ok=True)
    path = photo_path(student_id)
    tmp = path + ".tmp"
    img.save(tmp, format="PNG")
    os.replace(tmp, path)  # ditulis utuh atau tidak sama sekali


def remove_photo(student_id):
    """Hapus foto murid (kembali ke lingkaran inisial). True kalau ada yang dihapus."""
    try:
        os.remove(photo_path(student_id))
        return True
    except FileNotFoundError:
        return False


# --- menampilkan foto --------------------------------------------------------
def _circle_mask(size):
    """Topeng lingkaran dengan tepi halus (dihitung sendiri, tanpa ImageDraw)."""
    mask = _masks.get(size)
    if mask is None:
        r = size / 2.0
        c = r - 0.5
        data = []
        for y in range(size):
            for x in range(size):
                coverage = r - math.hypot(x - c, y - c) + 0.5
                data.append(int(255 * min(1.0, max(0.0, coverage))))
        mask = Image.new("L", (size, size))
        mask.putdata(data)
        _masks[size] = mask
    return mask


def load_avatar(student_id, size):
    """Foto murid berbentuk lingkaran (gambar RGBA ukuran size x size), atau None."""
    if not HAS_PIL or not has_photo(student_id):
        return None
    try:
        with Image.open(photo_path(student_id)) as f:
            img = f.convert("RGB").resize((size, size), _RESAMPLE)
        img.putalpha(_circle_mask(size))
        return img
    except Exception as exc:
        C.log(f"Foto {student_id} tidak bisa dibuka: {exc!r}")
        return None


def _hex_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _disc_mask(size, radius):
    """Topeng lingkaran penuh berjari-jari 'radius' dengan tepi anti-alias."""
    key = (size, round(radius, 2))
    mask = _masks.get(key)
    if mask is None:
        c = (size - 1) / 2.0
        data = []
        for y in range(size):
            for x in range(size):
                coverage = radius - math.hypot(x - c, y - c) + 0.5
                data.append(int(255 * min(1.0, max(0.0, coverage))))
        mask = Image.new("L", (size, size))
        mask.putdata(data)
        _masks[key] = mask
    return mask


def render_avatar(student_id, size, bg, fill, ring, ring_width=2):
    """Gambar avatar bulat utuh (foto atau warna polos + cincin) dengan tepi halus.

    Hasilnya gambar RGB ukuran size x size yang sudah dicampur dengan warna latar
    'bg' (hex, mis. "#1d212c"), jadi tepinya mulus di atas latar itu. Kalau murid
    punya foto, bagian dalam berisi foto; kalau tidak, diisi warna 'fill'.
    Kembalikan None kalau Pillow tidak ada (pemanggil memakai gambar bawaan Tk).
    """
    if not HAS_PIL:
        return None
    outer_r = size / 2.0 - 0.5
    canvas = Image.new("RGB", (size, size), _hex_rgb(bg))
    canvas.paste(_hex_rgb(ring), mask=_disc_mask(size, outer_r))
    inner = _disc_mask(size, outer_r - ring_width)
    photo = None
    if student_id and has_photo(student_id):
        try:
            with Image.open(photo_path(student_id)) as f:
                photo = f.convert("RGB").resize((size, size), _RESAMPLE)
        except Exception as exc:
            C.log(f"Foto {student_id} tidak bisa dibuka: {exc!r}")
    if photo is not None:
        canvas.paste(photo, mask=inner)
    else:
        canvas.paste(_hex_rgb(fill), mask=inner)
    return canvas, photo is not None


def to_photoimage(img):
    """Gambar Pillow -> gambar yang bisa ditampilkan Tk."""
    if ImageTk is None:
        raise RuntimeError("ImageTk tidak tersedia")
    return ImageTk.PhotoImage(img)
