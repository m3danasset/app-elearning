"""Ikon halus (anti-alias) untuk mini player: putar/jeda, mundur 10 detik, speaker, pegangan, knob.

Canvas Tk tidak melakukan anti-alias, jadi lingkaran / diagonal / panah di canvas terlihat bergerigi
(pixelated). Di sini bentuk digambar sendiri dengan matematika murni (jarak bertanda per piksel,
seperti sidebar_icons.py) lalu dijadikan gambar, TANPA ImageDraw / ImageFilter (modul itu tidak ikut
terbungkus di dalam .exe). Hanya memakai Image.new + putdata.

Semua fungsi bentuk mengembalikan jarak bertanda (negatif = di dalam) dalam satuan piksel.
"""

import math

from elearning import config as C

_cache = {}


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _cov(d):
    """Jarak bertanda -> cakupan piksel 0..1 (tepi halus selebar 1 px)."""
    return min(1.0, max(0.0, 0.5 - d))


# --- bentuk dasar --------------------------------------------------------------
def _seg(px, py, ax, ay, bx, by, hw):
    """Garis tebal (ujung membulat): setengah tebal = hw."""
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = min(1.0, max(0.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)) - hw


def _rrect(px, py, x0, y0, x1, y1, r):
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    qx = abs(px - cx) - ((x1 - x0) / 2.0 - r)
    qy = abs(py - cy) - ((y1 - y0) / 2.0 - r)
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r


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


def _arc(px, py, cx, cy, r, hw, a0, a1):
    """Busur tebal dari sudut a0 ke a1 (derajat, sumbu y ke bawah, a0 < a1, tanpa melewati +-180)."""
    ring = abs(math.hypot(px - cx, py - cy) - r) - hw
    a = math.degrees(math.atan2(py - cy, px - cx))
    outside = max(a0 - a, a - a1) * math.radians(1.0) * r     # >0: di luar rentang sudut
    return max(ring, outside)


def _ellipse_ring(px, py, cx, cy, rx, ry, hw):
    k = math.hypot((px - cx) / rx, (py - cy) / ry)
    return abs(k - 1.0) * min(rx, ry) - hw


# --- glyph (satuan piksel pada kisi ukuran jadi) ----------------------------------
def rewind10(x, y):
    """Panah putar mundur + angka 10, kisi 28 x 28."""
    # busur: semua sudut kecuali celah di kiri-atas (-135..-90 derajat)
    ring = abs(math.hypot(x - 14, y - 15) - 9.0) - 1.0
    a = math.degrees(math.atan2(y - 15, x - 14))
    in_gap = min(a + 135.0, -90.0 - a) * math.radians(1.0) * 9.0     # >0 di dalam celah
    arc = max(ring, in_gap)
    head = _poly(x, y, [(14.8, 2.4), (14.8, 9.6), (9.0, 6.0)])       # kepala panah (menunjuk kiri)
    one = min(_seg(x, y, 12.5, 11.8, 12.5, 18.4, 0.9), _seg(x, y, 10.7, 13.4, 12.5, 11.8, 0.9))
    zero = _ellipse_ring(x, y, 17.3, 15.1, 2.4, 3.4, 0.85)
    return min(arc, head, one, zero)


def speaker(x, y):
    """Badan speaker, kisi 28 x 28."""
    return _poly(x, y, [(5, 11), (9, 11), (14, 7), (14, 21), (9, 17), (5, 17)])


def waves(x, y):
    return _arc(x, y, 12.5, 14, 6.5, 1.0, -50, 50)


def cross(x, y):
    return min(_seg(x, y, 17.5, 11, 23.5, 17, 1.0), _seg(x, y, 23.5, 11, 17.5, 17, 1.0))


def grip(x, y):
    """Tiga garis diagonal di pojok kanan-atas, kisi 22 x 26."""
    return min(_seg(x, y, 22 - d - 2.5, 6.5, 22 - 2.5, 6.5 + d, 0.6) for d in (6, 11, 16))


def knob(x, y):
    """Lingkaran penanda posisi, kisi 14 x 14."""
    return math.hypot(x - 7, y - 7) - 5.5


def _play_tri(s):
    cx = cy = s / 2.0
    pts = [(cx - 0.17 * s, cy - 0.30 * s), (cx - 0.17 * s, cy + 0.30 * s), (cx + 0.33 * s, cy)]
    return lambda x, y: _poly(x, y, pts)


def _pause_bars(s):
    cx, cy = s / 2.0, s / 2.0
    w, h, g, r = 0.15 * s, 0.50 * s, 0.14 * s, 0.03 * s

    def sd(x, y):
        return min(_rrect(x, y, cx - g - w / 2, cy - h / 2, cx - g + w / 2, cy + h / 2, r),
                   _rrect(x, y, cx + g - w / 2, cy - h / 2, cx + g + w / 2, cy + h / 2, r))
    return sd


# --- pembuat bentuk umum (dipakai pemutar utama di lesson_view.py) --------------------
def union(*fns):
    return lambda x, y: min(f(x, y) for f in fns)


def circle(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def ring(cx, cy, r, hw):
    return lambda x, y: abs(math.hypot(x - cx, y - cy) - r) - hw


def tri(pts):
    return lambda x, y: _poly(x, y, pts)


def bars(rects, r=0.0):
    """Beberapa persegi panjang (x0, y0, x1, y1) bersudut membulat r."""
    return lambda x, y: min(_rrect(x, y, a, b, c, d, r) for a, b, c, d in rects)


def rrect_ring(x0, y0, x1, y1, r, hw):
    return lambda x, y: abs(_rrect(x, y, x0, y0, x1, y1, r)) - hw


def polylines(lines, hw):
    """Garis patah tebal 2*hw: lines = [[(x, y), (x, y), ...], ...]."""
    segs = [(a, b) for pl in lines for a, b in zip(pl, pl[1:])]
    return lambda x, y: min(_seg(x, y, a[0], a[1], b[0], b[1], hw) for a, b in segs)


def arc(cx, cy, r, hw, a0, a1):
    return lambda x, y: _arc(x, y, cx, cy, r, hw, a0, a1)


# --- penggambar ------------------------------------------------------------------
def render(layers, w, h):
    """Gambar Pillow RGBA w x h (latar transparan). layers = [(fungsi_bentuk, "#warna"), ...]."""
    from PIL import Image
    cols = [(fn, _rgb(col)) for fn, col in layers]
    data = []
    for yy in range(h):
        for xx in range(w):
            px, py = xx + 0.5, yy + 0.5
            oa, orgb = 0.0, (0.0, 0.0, 0.0)
            for fn, col in cols:
                a = _cov(fn(px, py))
                if a <= 0.0:
                    continue
                na = a + oa * (1.0 - a)
                orgb = tuple((col[i] * a + orgb[i] * oa * (1.0 - a)) / na for i in range(3))
                oa = na
            data.append((int(orgb[0] + 0.5), int(orgb[1] + 0.5), int(orgb[2] + 0.5),
                         int(oa * 255 + 0.5)))
    img = Image.new("RGBA", (w, h))
    img.putdata(data)
    return img


def render_overlay(kind, size, key="#010203"):
    """Tombol putar ("play") / jeda ("pause") putih minimalis untuk di atas video.

    Tepinya dicampur dengan abu-abu gelap tipis (jadi tetap terbaca di atas video terang);
    piksel di luar bentuk diisi warna `key` yang dibuat transparan oleh Windows.
    """
    from PIL import Image
    ck = (kind, size, key)
    img = _cache.get(ck)
    if img is not None:
        return img
    fn = _play_tri(size) if kind == "play" else _pause_bars(size)
    white, dark, keyc = (255, 255, 255), (22, 24, 30), _rgb(key)
    data = []
    for yy in range(size):
        for xx in range(size):
            sd = fn(xx + 0.5, yy + 0.5)
            g = _cov(sd)                      # bentuk putih
            o = _cov(sd - 2.0)                # tepi gelap tipis di sekelilingnya
            if o < 0.04:
                data.append(keyc)
            else:
                data.append(tuple(int(dark[i] + (white[i] - dark[i]) * g + 0.5) for i in range(3)))
    img = Image.new("RGB", (size, size))
    img.putdata(data)
    _cache[ck] = img
    return img


def photo(key, make):
    """PhotoImage dari make() (gambar Pillow), disimpan per key; None kalau gagal."""
    if key in _cache:
        return _cache[key]
    try:
        from PIL import ImageTk
        ph = ImageTk.PhotoImage(make())
    except Exception as exc:
        C.log(f"Ikon mini player gagal dibuat ({key!r}): {exc!r}")
        ph = None
    _cache[key] = ph
    return ph
