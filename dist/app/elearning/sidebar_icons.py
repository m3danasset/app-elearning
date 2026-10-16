"""Ikon Materi (video), Resource (folder) dan Portfolio (album foto) untuk sidebar yang dilipat.

Digambar sendiri dengan matematika murni + Image.putdata (TANPA ImageDraw, sama seperti
photos.py), jadi pasti jalan di .exe. Tepi halus (anti-alias). Ukuran 44 px berbentuk
lingkaran = sama dengan foto murid (Avatar) dan ikon Blender saat sidebar dilipat.
"""

import math

from elearning import config as C

SIZE = 44   # sama dengan Avatar & ikon Blender saat sidebar dilipat

MATERI = "materi"        # ikon video (layar + tombol play)
RESOURCE = "resource"    # ikon folder
PORTFOLIO = "portfolio"  # ikon album foto

_cache = {}


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


# --- jarak bertanda (signed distance) bentuk dasar, satuan = px pada kisi 44 ----
def _rrect(px, py, x0, y0, x1, y1, r):
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    qx = abs(px - cx) - ((x1 - x0) / 2.0 - r)
    qy = abs(py - cy) - ((y1 - y0) / 2.0 - r)
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r


def _seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = min(1.0, max(0.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _poly(px, py, pts):
    d = (px - pts[0][0]) ** 2 + (py - pts[0][1]) ** 2
    s = 1.0
    j = len(pts) - 1
    for i in range(len(pts)):
        ex, ey = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
        wx, wy = px - pts[i][0], py - pts[i][1]
        t = min(1.0, max(0.0, (wx * ex + wy * ey) / (ex * ex + ey * ey)))
        bx, by = wx - ex * t, wy - ey * t
        d = min(d, bx * bx + by * by)
        c1, c2, c3 = py >= pts[i][1], py < pts[j][1], ex * wy > ey * wx
        if (c1 and c2 and c3) or (not c1 and not c2 and not c3):
            s = -s
        j = i
    return s * math.sqrt(d)


def _cov(d):
    """Jarak bertanda -> cakupan piksel 0..1 (tepi halus selebar 1 px)."""
    return min(1.0, max(0.0, 0.5 - d))


# --- glyph: fungsi (x, y) -> cakupan 0..1 --------------------------------------
def _folder(x, y):
    """Folder: badan + tab di kiri atas, hanya garis tepi."""
    sd = min(_rrect(x, y, 9, 16, 35, 32, 3.0),
             _rrect(x, y, 9, 11.5, 20.5, 19.5, 2.6))
    return _cov(abs(sd) - 1.15)


def _video(x, y):
    """Materi video: layar video bergaris tepi + segitiga play di tengah."""
    c = _cov(abs(_rrect(x, y, 8.5, 12, 35.5, 32, 4.0)) - 1.15)
    c = max(c, _cov(_poly(x, y, [(18.6, 16.6), (18.6, 27.4), (27.4, 22.0)])))
    return c


def _album(x, y):
    """Album foto: sampul bergaris tepi + punggung album + satu foto (matahari & gunung)."""
    c = _cov(abs(_rrect(x, y, 10.5, 9, 33.5, 35, 3.5)) - 1.15)               # sampul
    c = max(c, _cov(_seg(x, y, 15.8, 9.5, 15.8, 34.5) - 1.0))                 # punggung
    c = max(c, _cov(abs(_rrect(x, y, 19.5, 14.5, 29.5, 26.5, 1.6)) - 0.8))    # bingkai foto
    c = max(c, _cov(math.hypot(x - 23.2, y - 18.6) - 1.5))                    # matahari
    c = max(c, _cov(_poly(x, y, [(20.6, 25.4), (24.2, 21.4), (26.0, 23.2),
                                  (27.0, 22.2), (28.6, 25.4)])))              # gunung
    return c


def render(kind, active=False, hover=False, size=SIZE, bg=C.CARD):
    """Gambar Pillow RGB size x size (sudah dicampur dengan warna latar bg)."""
    from PIL import Image

    key = (kind, active, hover, size, bg)
    img = _cache.get(key)
    if img is not None:
        return img

    bgc = _rgb(bg)
    if active:
        disc, glyph = _rgb(C.ACCENT), (255, 255, 255)
    else:
        disc = _rgb(C.CARD_HOVER if hover else C.BORDER)
        glyph = _rgb(C.TEXT if hover else "#b4b9c8")
    shape = {PORTFOLIO: _album, RESOURCE: _folder}.get(kind, _video)
    k = 44.0 / size
    r = size / 2.0 - 0.5
    c = (size - 1) / 2.0

    data = []
    for yy in range(size):
        for xx in range(size):
            a = _cov(math.hypot(xx - c, yy - c) - r)                 # lingkaran latar
            px = [bgc[i] + (disc[i] - bgc[i]) * a for i in range(3)]
            g = shape((xx + 0.5) * k, (yy + 0.5) * k) if a > 0 else 0.0
            data.append(tuple(int(round(px[i] + (glyph[i] - px[i]) * g)) for i in range(3)))
    img = Image.new("RGB", (size, size))
    img.putdata(data)
    _cache[key] = img
    return img


def get_photo(kind, active=False, hover=False, size=SIZE, bg=C.CARD):
    """PhotoImage siap pakai di Tk, atau None kalau Pillow tidak tersedia."""
    try:
        from PIL import ImageTk
        return ImageTk.PhotoImage(render(kind, active, hover, size, bg))
    except Exception as exc:
        C.log(f"Ikon sidebar gagal dibuat: {exc!r}")
        return None
