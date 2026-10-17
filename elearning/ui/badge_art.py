"""Gambar badge: lingkaran + ikon garis minimalis (ketebalan sama, ujung membulat).

Digambar dengan jarak bertanda per piksel seperti ui_icons.py, tapi dihitung sekaligus untuk
semua piksel dengan numpy (sudah ikut di .exe bersama OpenCV): 20 badge siap dalam beberapa
milidetik. TANPA ImageDraw / ImageFilter. Tepi anti-alias selebar 1 px.

image(id_ikon, ukuran, warna, latar, keadaan) -> PIL Image RGB
  keadaan: "on" (sudah didapat), "off" (belum, abu-abu), "secret" (rahasia, tanda tanya)
photo(...) -> PhotoImage (disimpan di cache)
"""

import math

from elearning import config as C

try:
    import numpy as np
except Exception:          # tanpa numpy: badge tampil sebagai titik berwarna (lihat badge_ui)
    np = None

HW = 1.0                   # setengah tebal garis ikon (kisi 20)
_cache = {}


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    """Campur warna a -> b sebanyak t (0..1)."""
    ca, cb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(int(round(ca[i] + (cb[i] - ca[i]) * t)) for i in range(3))


# --- bentuk dasar (array X, Y dalam satuan kisi 20) -----------------------------------------
def _seg(X, Y, a, b, hw=HW):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / (dx * dx + dy * dy), 0.0, 1.0)
    return np.hypot(X - (a[0] + t * dx), Y - (a[1] + t * dy)) - hw


def _lines(X, Y, *pts, hw=HW):
    d = _seg(X, Y, pts[0], pts[1], hw)
    for p, q in zip(pts[1:], pts[2:]):
        d = np.minimum(d, _seg(X, Y, p, q, hw))
    return d


def _ring(X, Y, cx, cy, r, hw=HW):
    return np.abs(np.hypot(X - cx, Y - cy) - r) - hw


def _disc(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def _rrect(X, Y, x0, y0, x1, y1, r):
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    qx = np.abs(X - cx) - ((x1 - x0) / 2.0 - r)
    qy = np.abs(Y - cy) - ((y1 - y0) / 2.0 - r)
    return (np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0))
            + np.minimum(np.maximum(qx, qy), 0.0) - r)


def _box(X, Y, x0, y0, x1, y1, r, hw=HW):
    return np.abs(_rrect(X, Y, x0, y0, x1, y1, r)) - hw


def _arc(X, Y, cx, cy, r, a0, a1, hw=HW):
    """Busur dari sudut a0 ke a1 (derajat, y ke bawah, a0 < a1, tidak melewati +-180)."""
    ring = np.abs(np.hypot(X - cx, Y - cy) - r) - hw
    a = np.degrees(np.arctan2(Y - cy, X - cx))
    outside = np.maximum(a0 - a, a - a1) * math.radians(1.0) * r
    return np.maximum(ring, outside)


def _poly(X, Y, pts):
    """Poligon terisi (jarak bertanda, negatif = di dalam)."""
    d = (X - pts[0][0]) ** 2 + (Y - pts[0][1]) ** 2
    s = np.ones_like(X)
    j = len(pts) - 1
    for i in range(len(pts)):
        ex, ey = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
        wx, wy = X - pts[i][0], Y - pts[i][1]
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0.0, 1.0)
        bx, by = wx - ex * t, wy - ey * t
        d = np.minimum(d, bx * bx + by * by)
        c1, c2, c3 = Y >= pts[i][1], Y < pts[j][1], ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
        j = i
    return s * np.sqrt(d)


def _star_pts(cx, cy, r, inner=0.48):
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        rr = r if i % 2 == 0 else r * inner
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


# --- ikon (kisi 20 x 20) ---------------------------------------------------------------------
def _halo(X, Y):        # balon obrolan
    return np.minimum.reduce([
        _box(X, Y, 2.8, 3.6, 17.2, 13.4, 3.0),
        _lines(X, Y, (6.6, 13.4), (5.8, 17.0), (10.4, 13.4)),
        _disc(X, Y, 6.8, 8.5, 1.05), _disc(X, Y, 10.0, 8.5, 1.05), _disc(X, Y, 13.2, 8.5, 1.05)])


def _cube(X, Y):        # kubus (Blender)
    hexa = [(10, 2.8), (16.6, 6.5), (16.6, 13.5), (10, 17.2), (3.4, 13.5), (3.4, 6.5), (10, 2.8)]
    return np.minimum.reduce([_lines(X, Y, *hexa),
                              _lines(X, Y, (3.6, 6.6), (10, 10.2), (16.4, 6.6)),
                              _seg(X, Y, (10, 10.2), (10, 17.0))])


def _monitor(X, Y):     # layar + tombol putar
    return np.minimum.reduce([_box(X, Y, 2.6, 3.4, 17.4, 13.6, 2.2),
                              _seg(X, Y, (10, 13.8), (10, 16.6)),
                              _seg(X, Y, (6.6, 16.8), (13.4, 16.8)),
                              _poly(X, Y, [(8.5, 6.2), (8.5, 10.8), (12.5, 8.5)])])


def _flag(X, Y):
    return np.minimum(_seg(X, Y, (5.0, 2.8), (5.0, 17.4)),
                      _lines(X, Y, (5.0, 3.6), (15.6, 3.6), (12.6, 7.3), (15.6, 11.0), (5.0, 11.0)))


def _layers(X, Y):
    top = [(10, 3.0), (17.0, 6.8), (10, 10.6), (3.0, 6.8), (10, 3.0)]
    return np.minimum.reduce([_lines(X, Y, *top),
                              _lines(X, Y, (3.0, 10.3), (10, 14.1), (17.0, 10.3)),
                              _lines(X, Y, (3.0, 13.7), (10, 17.5), (17.0, 13.7))])


def _forward(X, Y):
    return np.minimum(_lines(X, Y, (3.8, 4.8), (9.4, 10), (3.8, 15.2)),
                      _lines(X, Y, (10.6, 4.8), (16.2, 10), (10.6, 15.2)))


def _loop(X, Y):        # panah melingkar
    return np.minimum(_arc(X, Y, 10, 10, 6.2, -150, 125),
                      _poly(X, Y, [(2.6, 3.4), (3.0, 9.4), (8.6, 7.2)]))


def _stairs(X, Y):
    return _lines(X, Y, (3.0, 16.8), (3.0, 12.8), (7.6, 12.8), (7.6, 8.6), (12.2, 8.6),
                  (12.2, 4.4), (17.0, 4.4), (17.0, 16.8), (3.0, 16.8))


def _cap(X, Y):         # topi wisuda
    return np.minimum.reduce([
        _lines(X, Y, (10, 3.8), (18.0, 7.8), (10, 11.8), (2.0, 7.8), (10, 3.8)),
        _lines(X, Y, (5.4, 9.8), (5.4, 13.6), (10, 15.8), (14.6, 13.6), (14.6, 9.8)),
        _seg(X, Y, (18.0, 8.0), (18.0, 13.0))])


def _image(X, Y):
    return np.minimum.reduce([_box(X, Y, 2.8, 3.6, 17.2, 16.4, 2.4),
                              _ring(X, Y, 7.4, 8.0, 1.5),
                              _lines(X, Y, (3.4, 15.2), (8.6, 10.6), (11.4, 13.2),
                                     (13.4, 11.4), (16.8, 14.6))])


def _pencil(X, Y):
    body = [(13.0, 3.4), (16.6, 7.0), (7.6, 16.0), (3.4, 16.6), (4.0, 12.4), (13.0, 3.4)]
    return np.minimum(_lines(X, Y, *body), _seg(X, Y, (10.8, 5.6), (14.4, 9.2)))


def _folder_check(X, Y):
    return np.minimum(_lines(X, Y, (2.8, 15.8), (2.8, 4.4), (7.6, 4.4), (9.4, 6.6), (17.2, 6.6),
                             (17.2, 15.8), (2.8, 15.8)),
                      _lines(X, Y, (6.8, 11.4), (9.2, 13.6), (13.4, 9.4)))


def _star(X, Y):
    pts = _star_pts(10, 10.6, 7.6)
    return _lines(X, Y, *(pts + [pts[0]]))


def _calendar_base(X, Y):
    return np.minimum.reduce([_box(X, Y, 2.8, 4.4, 17.2, 17.0, 2.4),
                              _seg(X, Y, (3.0, 8.4), (17.0, 8.4)),
                              _seg(X, Y, (7.0, 2.6), (7.0, 5.8)),
                              _seg(X, Y, (13.0, 2.6), (13.0, 5.8))])


def _calendar(X, Y):
    return np.minimum.reduce([_calendar_base(X, Y), _disc(X, Y, 6.8, 12.6, 1.1),
                              _disc(X, Y, 10.0, 12.6, 1.1), _disc(X, Y, 13.2, 12.6, 1.1)])


def _calendar_check(X, Y):
    return np.minimum(_calendar_base(X, Y), _lines(X, Y, (6.8, 12.6), (9.0, 14.6), (13.4, 10.4)))


def _flame(X, Y):
    outer = [(10, 2.6), (13.8, 7.0), (15.4, 11.0), (14.4, 14.8), (10, 17.4), (5.6, 14.8),
             (4.6, 11.0), (6.6, 7.4), (8.2, 9.6), (10, 2.6)]
    inner = [(10, 10.6), (12.0, 13.4), (10, 15.4), (8.0, 13.4), (10, 10.6)]
    return np.minimum(_lines(X, Y, *outer), _lines(X, Y, *inner))


def _target(X, Y):
    return np.minimum.reduce([_ring(X, Y, 10, 10, 7.0), _ring(X, Y, 10, 10, 3.6),
                              _disc(X, Y, 10, 10, 1.3)])


def _key(X, Y):
    return np.minimum.reduce([_ring(X, Y, 6.4, 10, 3.4), _seg(X, Y, (9.8, 10), (17.2, 10)),
                              _seg(X, Y, (14.2, 10), (14.2, 13.2)),
                              _seg(X, Y, (16.8, 10), (16.8, 12.4))])


def _hourglass(X, Y):
    return np.minimum.reduce([
        _seg(X, Y, (4.6, 3.0), (15.4, 3.0)), _seg(X, Y, (4.6, 17.0), (15.4, 17.0)),
        _lines(X, Y, (6.0, 3.2), (6.0, 5.6), (10, 10), (6.0, 14.4), (6.0, 16.8)),
        _lines(X, Y, (14.0, 3.2), (14.0, 5.6), (10, 10), (14.0, 14.4), (14.0, 16.8)),
        _poly(X, Y, [(7.8, 16.0), (12.2, 16.0), (10, 13.4)])])


def _gift(X, Y):
    return np.minimum.reduce([_box(X, Y, 3.4, 8.4, 16.6, 17.2, 1.6),
                              _box(X, Y, 2.4, 5.4, 17.6, 8.6, 1.2),
                              _seg(X, Y, (10, 5.6), (10, 17.0)),
                              _arc(X, Y, 7.6, 4.0, 2.0, -180, 30),
                              _arc(X, Y, 12.4, 4.0, 2.0, 150, 180),
                              _arc(X, Y, 12.4, 4.0, 2.0, -180, 0)])


def _question(X, Y):
    return np.minimum.reduce([_arc(X, Y, 10, 7.6, 3.6, -180, 60, hw=1.15),
                              _seg(X, Y, (11.8, 10.7), (10, 12.2), hw=1.15),
                              _seg(X, Y, (10, 12.2), (10, 12.8), hw=1.15),
                              _disc(X, Y, 10, 16.2, 1.35)])


SHAPES = {"halo": _halo, "cube": _cube, "monitor": _monitor, "flag": _flag,
          "layers": _layers, "forward": _forward, "loop": _loop, "stairs": _stairs,
          "cap": _cap, "image": _image, "pencil": _pencil, "folder_check": _folder_check,
          "star": _star, "calendar": _calendar, "calendar_check": _calendar_check,
          "flame": _flame, "target": _target, "key": _key, "hourglass": _hourglass,
          "gift": _gift, "question": _question}


# --- penggambar ------------------------------------------------------------------------------
def image(icon, size, color, bg, state="on"):
    """Badge bulat ukuran size x size (RGB, sudah dicampur dengan warna latar)."""
    from PIL import Image
    if np is None:
        return None
    s = int(size)
    px = np.arange(s, dtype=np.float32) + 0.5
    PX, PY = np.meshgrid(px, px)
    c = s / 2.0
    R = s / 2.0 - 0.75
    if state == "on":
        fill, ring, glyph = _mix(bg, color, 0.16), color, color
    else:
        fill, ring, glyph = _mix(bg, "#ffffff", 0.035), C.BORDER, C.LOCKED
    out = np.empty((s, s, 3), dtype=np.float32)
    out[:] = _rgb(bg)

    def paint(dist_px, col):
        a = np.clip(0.5 - dist_px, 0.0, 1.0)[..., None]
        out[:] = out * (1.0 - a) + np.array(_rgb(col), dtype=np.float32) * a

    dc = np.hypot(PX - c, PY - c)
    paint(dc - R, fill)                                         # isi lingkaran
    paint(np.abs(dc - (R - 0.9)) - max(0.75, s / 64.0), ring)   # cincin tipis
    g = s * 0.50                                                # ikon: setengah diameter
    k = 20.0 / g
    X = (PX - (c - g / 2.0)) * k
    Y = (PY - (c - g / 2.0)) * k
    fn = SHAPES.get("question" if state == "secret" else icon, _question)
    paint(fn(X, Y) / k, glyph)
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGB")


def photo(icon, size, color, bg, state="on"):
    key = (icon, int(size), color, bg, state)
    if key in _cache:
        return _cache[key]
    ph = None
    try:
        from PIL import ImageTk
        img = image(icon, size, color, bg, state)
        if img is not None:
            ph = ImageTk.PhotoImage(img)
    except Exception as exc:
        C.log(f"Gambar badge {icon} gagal: {exc!r}")
    _cache[key] = ph
    return ph
