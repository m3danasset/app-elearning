"""Ikon garis halus (gaya claude.ai) + latar membulat untuk sidebar baru.

Sama seperti aa_icons.py / sidebar_icons.py: digambar dengan matematika murni (jarak
bertanda per piksel) lalu Image.new + putdata. TANPA ImageDraw / ImageFilter, jadi
pasti jalan di dalam .exe. Semua gambar sudah dicampur dengan warna latarnya
(RGB, bukan transparan) supaya tepinya mulus di Tk.

icon(nama, warna, latar, ukuran)   -> PhotoImage ikon (kisi 20 x 20 diskalakan)
pill(lebar, tinggi, isi, latar, ...) -> PhotoImage persegi panjang bersudut bulat
dot(warna, latar, ukuran)          -> PhotoImage titik bulat (status online, warna kursus)
"""

import math

from elearning import config as C
from elearning.ui import aa_icons as A

_cache = {}
_img_cache = {}

STROKE = 0.78   # setengah tebal garis, satuan kisi 20


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _cov(d):
    return min(1.0, max(0.0, 0.5 - d))


def _seg(x, y, a, b, hw=STROKE):
    return A._seg(x, y, a[0], a[1], b[0], b[1], hw)


def _lines(x, y, *pts, hw=STROKE):
    return min(_seg(x, y, p, q, hw) for p, q in zip(pts, pts[1:]))


def _ring(x, y, cx, cy, r, hw=STROKE):
    return abs(math.hypot(x - cx, y - cy) - r) - hw


def _box(x, y, x0, y0, x1, y1, r, hw=STROKE):
    return abs(A._rrect(x, y, x0, y0, x1, y1, r)) - hw


# --- bentuk ikon (jarak bertanda pada kisi 20 x 20) -------------------------------
def _search(x, y):
    return min(_ring(x, y, 8.6, 8.6, 5.2), _seg(x, y, (12.5, 12.5), (16.6, 16.6)))


def _panel(x, y):
    return min(_box(x, y, 2.8, 3.8, 17.2, 16.2, 2.6), _seg(x, y, (7.8, 4.2), (7.8, 15.8)))


def _home(x, y):
    return min(_lines(x, y, (2.8, 9.2), (10, 3.2), (17.2, 9.2)),
               _lines(x, y, (4.8, 7.8), (4.8, 16.6), (15.2, 16.6), (15.2, 7.8)),
               _lines(x, y, (8.4, 16.4), (8.4, 11.6), (11.6, 11.6), (11.6, 16.4)))


def _grid(x, y):
    return min(_box(x, y, 3, 3, 8.8, 8.8, 1.6), _box(x, y, 11.2, 3, 17, 8.8, 1.6),
               _box(x, y, 3, 11.2, 8.8, 17, 1.6), _box(x, y, 11.2, 11.2, 17, 17, 1.6))


def _play(x, y):
    return min(_box(x, y, 2.6, 4.2, 17.4, 15.8, 2.6),
               A._poly(x, y, [(8.2, 7.2), (8.2, 12.8), (12.9, 10.0)]))


def _folder(x, y):
    return _lines(x, y, (2.8, 15.6), (2.8, 4.6), (7.6, 4.6), (9.4, 6.6), (17.2, 6.6),
                  (17.2, 15.6), (2.8, 15.6))


def _image(x, y):
    return min(_box(x, y, 2.8, 3.8, 17.2, 16.2, 2.4), _ring(x, y, 7.4, 8.2, 1.4),
               _lines(x, y, (3.4, 15.0), (8.6, 10.6), (11.4, 13.0), (13.4, 11.2), (16.8, 14.4)))


def _users(x, y):
    return min(_ring(x, y, 7.6, 6.8, 3.0),
               A._arc(x, y, 7.6, 17.2, 5.6, STROKE, -180, 0),
               A._arc(x, y, 13.4, 6.8, 2.6, STROKE, -90, 90),
               _lines(x, y, (14.4, 11.9), (16.0, 12.8), (17.4, 16.2)))


def _user(x, y):
    return min(_ring(x, y, 10, 6.6, 3.2), A._arc(x, y, 10, 17.4, 6.0, STROKE, -180, 0))


def _file(x, y):
    return min(_lines(x, y, (11.8, 2.8), (4.4, 2.8), (4.4, 17.2), (15.6, 17.2), (15.6, 6.6),
                      (11.8, 2.8)),
               _lines(x, y, (11.6, 3.0), (11.6, 6.8), (15.4, 6.8)),
               _seg(x, y, (7.4, 10.4), (12.6, 10.4)), _seg(x, y, (7.4, 13.6), (12.6, 13.6)))


def _plus(x, y):
    return min(_seg(x, y, (10, 4.2), (10, 15.8), 0.9), _seg(x, y, (4.2, 10), (15.8, 10), 0.9))


def _chevrons(x, y):
    return min(_lines(x, y, (6.6, 8.0), (10, 4.8), (13.4, 8.0)),
               _lines(x, y, (6.6, 12.0), (10, 15.2), (13.4, 12.0)))


def _chev_down(x, y):
    return _lines(x, y, (6.2, 8.2), (10, 12.0), (13.8, 8.2))


def _chev_right(x, y):
    return _lines(x, y, (8.2, 6.2), (12.0, 10), (8.2, 13.8))


def _lock(x, y):
    return min(_box(x, y, 4.6, 9.0, 15.4, 17.0, 2.0),
               A._arc(x, y, 10, 7.2, 3.4, STROKE, -180, 0),
               _seg(x, y, (6.6, 7.2), (6.6, 9.2)), _seg(x, y, (13.4, 7.2), (13.4, 9.2)))


def _logout(x, y):
    return min(_lines(x, y, (8.6, 3.2), (4.0, 3.2), (4.0, 16.8), (8.6, 16.8)),
               _seg(x, y, (8.4, 10), (16.4, 10)),
               _lines(x, y, (13.2, 6.6), (16.6, 10), (13.2, 13.4)))


def _refresh(x, y):
    return min(A._arc(x, y, 10, 10, 6.0, STROKE, -150, 120),
               A._poly(x, y, [(3.0, 3.6), (3.4, 9.0), (8.4, 7.2)]))


def _close(x, y):
    return min(_seg(x, y, (5.4, 5.4), (14.6, 14.6)), _seg(x, y, (14.6, 5.4), (5.4, 14.6)))


def _report(x, y):   # papan klip: laporan guru
    return min(_box(x, y, 4.2, 4.0, 15.8, 17.4, 2.0),
               _box(x, y, 7.4, 2.6, 12.6, 5.6, 1.0),
               _seg(x, y, (7.4, 10.0), (12.6, 10.0)), _seg(x, y, (7.4, 13.4), (11.2, 13.4)))


def _teacher(x, y):   # orang + papan: guru
    return min(_ring(x, y, 6.6, 7.2, 2.6),
               A._arc(x, y, 6.6, 17.4, 5.0, STROKE, -180, 0),
               _box(x, y, 11.4, 3.2, 17.4, 9.8, 1.2))


def _activity(x, y):
    return _lines(x, y, (2.6, 10.4), (6.0, 10.4), (8.2, 4.4), (11.8, 15.6), (14.0, 10.4),
                  (17.4, 10.4))


SHAPES = {
    "search": _search, "panel": _panel, "home": _home, "grid": _grid, "play": _play,
    "folder": _folder, "image": _image, "users": _users, "user": _user, "file": _file,
    "plus": _plus, "chevrons": _chevrons, "chev_down": _chev_down,
    "chev_right": _chev_right, "lock": _lock, "logout": _logout, "refresh": _refresh,
    "close": _close, "report": _report, "teacher": _teacher, "activity": _activity,
}


# --- penggambar -------------------------------------------------------------------
def _render_icon(name, color, bg, size, disc=None):
    from PIL import Image
    fn = SHAPES[name]
    k = 20.0 / size
    col, bgc = _rgb(color), _rgb(bg)
    dc = _rgb(disc) if disc else None
    c = (size - 1) / 2.0
    data = []
    for yy in range(size):
        for xx in range(size):
            base = bgc
            if dc is not None:   # ikon di dalam lingkaran berwarna (mis. "Tambah murid")
                a = _cov(math.hypot(xx - c, yy - c) - (size / 2.0 - 0.5))
                base = tuple(bgc[i] + (dc[i] - bgc[i]) * a for i in range(3))
            # skala jarak kembali ke piksel supaya tepi anti-alias selebar 1 px
            g = _cov(fn((xx + 0.5) * k, (yy + 0.5) * k) / k)
            data.append(tuple(int(round(base[i] + (col[i] - base[i]) * g)) for i in range(3)))
    img = Image.new("RGB", (size, size))
    img.putdata(data)
    return img


def _render_pill(w, h, r, fill, bg, border=None):
    from PIL import Image
    r = min(r, w / 2.0, h / 2.0)
    f, b = _rgb(fill), _rgb(bg)
    bc = _rgb(border) if border else None
    img = Image.new("RGB", (w, h), f)
    if bc is not None:   # garis tepi 1 px (lurus); sudutnya dihitung di bawah
        for box in ((0, 0, w, 1), (0, h - 1, w, h), (0, 0, 1, h), (w - 1, 0, w, h)):
            img.paste(bc, box)

    def color(px, py):
        sd = A._rrect(px, py, 0, 0, w, h, r)
        a = _cov(sd)
        inner = f
        if bc is not None:
            e = _cov(sd + 1.0)    # 1 = bagian dalam, 0 = di garis tepi
            inner = tuple(bc[i] + (f[i] - bc[i]) * e for i in range(3))
        return tuple(int(round(b[i] + (inner[i] - b[i]) * a)) for i in range(3))

    # Hanya 4 sudut yang dihitung per piksel (cepat, juga untuk tombol / kartu besar)
    c = int(math.ceil(r)) + 1
    xs = list(range(min(c, w))) + list(range(max(c, w - c), w))
    ys = list(range(min(c, h))) + list(range(max(c, h - c), h))
    for yy in ys:
        for xx in xs:
            img.putpixel((xx, yy), color(xx + 0.5, yy + 0.5))
    return img


def round_mask(w, h, r):
    """Masker 'L' persegi panjang bersudut bulat (255 = di dalam), tepi halus.
    Dipakai untuk membulatkan sudut foto slideshow, splash, dll."""
    from PIL import Image
    w, h = max(2, int(w)), max(2, int(h))
    key = ("mask", w, h, r)
    m = _img_cache.get(key)
    if m is not None:
        return m
    m = Image.new("L", (w, h), 255)
    c = int(math.ceil(r)) + 1
    xs = list(range(min(c, w))) + list(range(max(c, w - c), w))
    ys = list(range(min(c, h))) + list(range(max(c, h - c), h))
    for yy in ys:
        for xx in xs:
            a = _cov(A._rrect(xx + 0.5, yy + 0.5, 0, 0, w, h, r))
            m.putpixel((xx, yy), int(round(a * 255)))
    _img_cache[key] = m
    return m


def _render_dot(color, bg, size, r):
    from PIL import Image
    col, b = _rgb(color), _rgb(bg)
    c = size / 2.0
    data = []
    for yy in range(size):
        for xx in range(size):
            a = _cov(math.hypot(xx + 0.5 - c, yy + 0.5 - c) - r)
            data.append(tuple(int(round(b[i] + (col[i] - b[i]) * a)) for i in range(3)))
    img = Image.new("RGB", (size, size))
    img.putdata(data)
    return img


_MAX_SHAPES = 800   # batas gambar pill/potongan di memori (ukuran jendela terus berubah)


def _photo(key, make):
    if key in _cache:
        return _cache[key]
    if key[0] in ("pill", "crop"):
        shapes = [k for k in _cache if k[0] in ("pill", "crop")]
        if len(shapes) > _MAX_SHAPES:   # buang yang lama; widget yang masih memakai tetap aman
            for k in shapes[: len(shapes) // 2]:
                _cache.pop(k, None)
                _img_cache.pop(k, None)
    try:
        from PIL import ImageTk
        img = make()
        _img_cache[key] = img
        ph = ImageTk.PhotoImage(img)
    except Exception as exc:
        C.log(f"Ikon sidebar gagal dibuat ({key!r}): {exc!r}")
        ph = None
    _cache[key] = ph
    return ph


def icon(name, color=C.TEXT, bg=C.SIDEBAR, size=18, disc=None):
    """PhotoImage ikon garis, atau None kalau Pillow tidak ada."""
    return _photo(("icon", name, color, bg, size, disc),
                  lambda: _render_icon(name, color, bg, size, disc))


def pill(w, h, fill, bg, r=8, border=None):
    """PhotoImage persegi panjang bersudut bulat (latar baris yang dipilih / kolom cari)."""
    w, h = max(2, int(w)), max(2, int(h))
    return _photo(("pill", w, h, fill, bg, r, border),
                  lambda: _render_pill(w, h, r, fill, bg, border))


def pill_crop(w, h, fill, bg, x0, x1, r=8, border=None):
    """Potongan vertikal pill (dipakai sebagai 'tutup' supaya teks berjalan tidak keluar)."""
    w, h = max(2, int(w)), max(2, int(h))
    x0, x1 = max(0, int(x0)), min(w, int(x1))
    if x1 - x0 < 1:
        return None
    pill(w, h, fill, bg, r, border)   # pastikan gambar dasarnya sudah ada
    base = _img_cache.get(("pill", w, h, fill, bg, r, border))
    if base is None:
        return None
    return _photo(("crop", w, h, fill, bg, r, border, x0, x1),
                  lambda: base.crop((x0, 0, x1, h)))


def dot(color, bg, size=10, r=3.6):
    return _photo(("dot", color, bg, size, r), lambda: _render_dot(color, bg, size, r))
