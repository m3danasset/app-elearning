"""Grafik halus untuk Analytics: area melengkung (gradasi) dan donut, tepi anti-alias.

Dihitung untuk semua piksel sekaligus dengan numpy (seperti badge_art), TANPA ImageDraw /
ImageFilter. Hasil: PIL Image RGB di atas warna latar kartu (bg), siap jadi PhotoImage.

area(w, h, series, bg, top)   series = [(nilai_per_titik, warna)], top = nilai sumbu atas
donut(size, parts, bg, thick) parts = [(nilai, warna)]
Tanpa numpy: None (pemanggil menampilkan grafik batang biasa).
"""

import math

try:
    import numpy as np
except Exception:
    np = None

FILL_TOP, FILL_BOTTOM = 0.42, 0.03      # kepekatan gradasi isi area (atas -> bawah)


def _rgb(color):
    color = color.lstrip("#")
    return np.array([int(color[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def points_x(w, n, pad):
    """Posisi x titik data (tengah tiap slot, sama dengan label sumbu)."""
    slot = (w - 2 * pad) / max(1, n)
    return [pad + slot * (i + 0.5) for i in range(n)]


def _monotone(xs, ys, X):
    """Kurva Hermite monoton (Fritsch-Carlson): halus, tidak pernah melewati titik data
    (tidak turun di bawah nol / naik di atas puncak)."""
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    n = len(xs)
    if n == 1:
        return np.full(X.shape, ys[0])
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.empty(n)
    m[0], m[-1] = d[0], d[-1]
    m[1:-1] = (d[:-1] + d[1:]) / 2.0
    m[1:-1][d[:-1] * d[1:] <= 0] = 0.0
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0.0
            continue
        a, b = m[i] / d[i], m[i + 1] / d[i]
        s = a * a + b * b
        if s > 9:
            t = 3.0 / math.sqrt(s)
            m[i], m[i + 1] = t * a * d[i], t * b * d[i]
    Xc = np.clip(X, xs[0], xs[-1])
    idx = np.clip(np.searchsorted(xs, Xc) - 1, 0, n - 2)
    hh = h[idx]
    t = (Xc - xs[idx]) / hh
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * ys[idx] + (t3 - 2 * t2 + t) * hh * m[idx]
            + (-2 * t3 + 3 * t2) * ys[idx + 1] + (t3 - t2) * hh * m[idx + 1])


def area(w, h, series, bg, top, pad=0, line_w=2.0, top_margin=6, grid=(), grid_color=None):
    """Area melengkung bertumpuk-tampil (bukan dijumlah): seri pertama di belakang.
    grid: posisi y (px) garis bantu horizontal, digambar di BELAKANG isi."""
    if np is None or w < 4 or h < 4:
        return None
    from PIL import Image
    w, h = int(w), int(h)
    img = np.empty((h, w, 3), dtype=np.float32)
    img[:] = _rgb(bg)
    if grid_color:
        for gy in grid:
            gy = int(round(gy))
            if 0 <= gy < h:
                img[gy, :, :] = _rgb(grid_color)
    X = np.arange(w, dtype=np.float64) + 0.5
    Y = (np.arange(h, dtype=np.float32) + 0.5)[:, None]      # float32: 2x lebih cepat
    base = h - 0.5
    top = max(top, 1e-9)
    for values, color in series:
        n = len(values)
        if n == 0:
            continue
        xs = points_x(w, n, pad)
        ys = [base - (base - top_margin) * max(0.0, v) / top for v in values]
        if n == 1:
            xs, ys = [xs[0] - 1, xs[0] + 1], [ys[0], ys[0]]
        curve = _monotone(xs, ys, X).astype(np.float32)
        inside = ((X >= xs[0]) & (X <= xs[-1])).astype(np.float32)
        slope = np.gradient(curve)
        cos = (1.0 / np.sqrt(1.0 + slope * slope)).astype(np.float32)
        col = _rgb(color)
        # isi: tepi atas halus + gradasi dari puncak kurva ke dasar
        cov = np.clip(Y - curve[None, :] + 0.5, 0.0, 1.0)
        ymin = float(curve[inside > 0].min()) if inside.any() else 0.0
        g = np.clip((Y - ymin) * np.float32(1.0 / max(1.0, base - ymin)), 0.0, 1.0)
        a = cov * (np.float32(FILL_TOP) + np.float32(FILL_BOTTOM - FILL_TOP) * g)             * inside[None, :]
        img += (col - img) * a[..., None]
        # garis kurva
        dist = np.abs(Y - curve[None, :]) * cos[None, :]
        a = np.clip(np.float32(line_w / 2.0 + 0.5) - dist, 0.0, 1.0) * inside[None, :]
        img += (col - img) * a[..., None]
    return Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8), "RGB")


def donut(size, parts, bg, thick, track, gap_px=3.0):
    """Cincin terbagi per bagian (searah jarum jam dari atas), celah kecil antar bagian.
    bg=None: hasil RGBA transparan (untuk ditaruh di atas gradasi / video)."""
    if np is None or size < 8:
        return None
    from PIL import Image
    size = int(size)
    clear = bg is None
    img = np.zeros((size, size, 3), dtype=np.float32)
    alpha = np.zeros((size, size), dtype=np.float32)
    if not clear:
        img[:] = _rgb(bg)
    c = size / 2.0
    g = np.arange(size, dtype=np.float64) + 0.5
    dx, dy = g[None, :] - c, g[:, None] - c
    R = np.hypot(dx, dy)
    r1 = c - 1.0
    r0 = r1 - thick
    radial = np.clip(np.minimum(R - r0, r1 - R) + 0.5, 0.0, 1.0)
    ang = np.mod(np.arctan2(dx, -dy), 2 * math.pi)        # 0 = atas, searah jarum jam
    total = float(sum(v for v, _c in parts if v > 0))
    if total <= 0:
        a = radial
        img = img * (1 - a[..., None]) + _rgb(track) * a[..., None]
        alpha = alpha + a * (1 - alpha)
    else:
        live = [(v, col) for v, col in parts if v > 0]
        hg = 0.0 if len(live) == 1 else gap_px / 2.0 / max(1.0, (r0 + r1) / 2.0)
        a0 = 0.0
        for v, color in live:
            span = v / total * 2 * math.pi
            rel = np.mod(ang - a0, 2 * math.pi)
            if len(live) == 1:
                cov_a = 1.0
            else:
                d = np.minimum(rel - hg, span - hg - rel)
                cov_a = np.clip(d * R + 0.5, 0.0, 1.0)
            a = radial * cov_a
            img = img * (1 - a[..., None]) + _rgb(color) * a[..., None]
            alpha = alpha + a * (1 - alpha)
            a0 += span
    if clear:       # warna dicampur dengan hitam di atas -> bagi alpha (tanpa pinggir gelap)
        rgb = np.where(alpha[..., None] > 1e-4, img / np.maximum(alpha[..., None], 1e-4), 0)
        out = np.dstack([np.clip(rgb + 0.5, 0, 255), np.clip(alpha * 255 + 0.5, 0, 255)])
        return Image.fromarray(out.astype(np.uint8), "RGBA")
    return Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8), "RGB")
