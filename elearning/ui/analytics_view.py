"""Halaman Analytics di Panel Admin.

Seluruh isi (kartu angka, grafik, daftar) digambar di SATU canvas (AnalyticsBoard).
Canvas Tk menggambar isinya di memori dulu lalu menampilkannya sekaligus, jadi:
  - ganti periode / program / tampilan Lengkap-Ringkas,
  - jendela <-> layar penuh,
tidak pernah menampilkan keadaan setengah jadi (tombol terpotong, kotak kosong, blok
hitam) dan sangat ringan untuk PC dengan grafis terintegrasi.

Data dihitung di thread terpisah (analytics.compute) dan disimpan sebentar per filter.
"""

import math
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from elearning import analytics as A
from elearning import config as C
from elearning.ui import ui_icons as I
from elearning.ui.controls import RoundButton, RoundSelect
from elearning.ui.sidebar import HIGHLIGHT

BLUE = "#7cc8ff"          # warna kedua grafik (sama dengan loading bar splash)
PURPLE, GOLD = "#b39af0", "#e3c26f"
GRID = "#2f2e2b"
GREEN, RED = C.ON, C.ERROR
GAP = 12


def _nice_max(v):
    if v <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(v))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


def _num(v, decimals=1):
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.{decimals}f}".replace(".", ",")


def _mix(a, b, t):
    ca, cb = I._rgb(a), I._rgb(b)
    return "#%02x%02x%02x" % tuple(int(round(ca[i] + (cb[i] - ca[i]) * t)) for i in range(3))


class AnalyticsBoard(tk.Canvas):
    """Satu canvas berisi seluruh halaman. set_data(data, view) lalu digambar ulang utuh."""

    def __init__(self, master, on_open=None):
        super().__init__(master, bg=C.BG, highlightthickness=0, bd=0, height=200)
        self.on_open = on_open
        self.data = None
        self.view = "full"
        self._imgs = []
        self._tips = []          # (x0, y0, x1, y1, [baris teks], y_atas) area berketerangan
        self._width = 0
        self._tip_img = None
        self._art = {}           # gambar grafik halus (area / donut) per ukuran & data
        self.query = ""          # kata dari kolom cari admin: nama yang cocok disorot
        self.f = {
            "title": tkfont.Font(family=C.FONT, size=11, weight="bold"),
            "sub": tkfont.Font(family=C.FONT, size=9),
            "small": tkfont.Font(family=C.FONT, size=8),
            "label": tkfont.Font(family=C.FONT, size=9),
            "big": tkfont.Font(family=C.FONT, size=20, weight="bold"),
            "mid": tkfont.Font(family=C.FONT, size=15, weight="bold"),
            "name": tkfont.Font(family=C.FONT, size=10),
            "val": tkfont.Font(family=C.FONT, size=10, weight="bold"),
            "dbold": tkfont.Font(family=C.FONT, size=9, weight="bold"),
        }
        self.bind("<Configure>", self._on_configure)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self.delete("tip"))

    # --- api ------------------------------------------------------------------------------
    def set_data(self, data, view):
        self.data, self.view = data, view
        self.redraw()

    def _on_configure(self, e):
        if e.width != self._width:   # tinggi berubah karena isi sendiri: tidak perlu gambar ulang
            self._width = e.width
            self.redraw()

    # --- gambar ---------------------------------------------------------------------------
    def redraw(self):
        w = self.winfo_width()
        if w < 200 or self.data is None:
            return
        self.delete("all")
        self._imgs, self._tips = [], []
        h = (self._compact if self.view == "compact" else self._full)(self.data, w)
        if int(self.cget("height")) != int(h):
            self.configure(height=int(h))

    def _img(self, ph, x, y, anchor="nw"):
        if ph is not None:
            self._imgs.append(ph)
            self.create_image(x, y, image=ph, anchor=anchor)

    def _text(self, x, y, text, font="label", fill=C.TEXT, anchor="nw", width=None, tags=()):
        f = self.f[font]
        if width is not None and f.measure(text) > width:   # potong dengan "..."
            while text and f.measure(text + "...") > width:
                text = text[:-1]
            text = text.rstrip() + "..."
        return self.create_text(x, y, text=text, font=f, fill=fill, anchor=anchor, tags=tags)

    def _card(self, x, y, w, h, title=None, sub="", compact=False):
        """Latar kartu membulat + judul. Kembalikan (x, y, lebar) area isi."""
        self._img(I.pill(int(w), int(h), C.CARD, C.BG, r=12 if compact else 14,
                         border=C.BORDER), x, y)
        px, py = (14, 12) if compact else (18, 16)
        if title:
            self._text(x + px, y + py, title, "title")
            if sub:
                self._text(x + w - px, y + py + 2, sub, "sub", C.MUTED, anchor="ne",
                           width=w - 2 * px - self.f["title"].measure(title) - 16)
            return x + px, y + py + (28 if compact else 32), w - 2 * px
        return x + px, y + py, w - 2 * px

    def _tiles(self, d, x, y, w, compact):
        k = d["kpi"]
        s0, s1 = d["range"]
        span = f"{A._day_label(s0)} – {A._day_label(s1)} {s1.year}"
        prev = "vs sebelumnya"
        att = k.get("attendance")
        h, n = k.get("attendance_n", (0, 0))
        att_note = (prev if k.get("attendance_delta") is not None else f"{h}/{n} hadir") \
            if att is not None else ("belum ada jadwal" if not k.get("slots")
                                     else "belum ada jadwal selesai")
        pf = d["portfolio"]
        uploads = [a + b for a, b in zip(pf["images"], pf["videos"])]
        total = k["active"] + k["expired"]
        # (label, nilai, catatan, selisih, satuan selisih, visual)
        # visual: ("bar", 0..1, warna) progress bar | ("spark", nilai per periode, warna)
        items = (
            ("Murid aktif", str(k["active"]), f"{k['expired']} expired  ·  "
                                              f"{k.get('unscheduled', 0)} tanpa jadwal", None,
             "%", ("bar", k["active"] / total if total else 0, GREEN)),
            ("Jam belajar", A.fmt_hours(k["seconds"]),
             prev if k["seconds_delta"] is not None else span, k["seconds_delta"], "%",
             ("spark", d["hours"]["values"], C.ACCENT)),
            ("Kehadiran jadwal", "–" if att is None else f"{_num(att, 0)}%", att_note,
             k.get("attendance_delta"), " poin", ("bar", (att or 0) / 100.0, C.ACCENT)),
            ("Portfolio masuk", f"{k['uploads']} file",
             prev if k["uploads_delta"] is not None else span, k["uploads_delta"], "%",
             ("spark", uploads, BLUE)),
            ("Assignment masuk", f"{k.get('assignments', 0)} file",
             prev if k.get("assignments_delta") is not None else span,
             k.get("assignments_delta"), "%", ("spark", pf.get("assignments", []), GREEN)),
            ("Badge didapat", str(k.get("badges", 0)),
             prev if k.get("badges_delta") is not None else span, k.get("badges_delta"), "%",
             ("spark", k.get("badge_series", []), PURPLE)),
        )
        gap = 8 if compact else GAP
        tw = (w - (len(items) - 1) * gap) / len(items)
        th = 84 if compact else 132
        for i, (label, value, note, delta, unit, viz) in enumerate(items):
            tx = x + i * (tw + gap)
            cx, cy, cw = self._card(tx, y, tw, th, compact=compact)
            self._text(cx, cy, label, "label", C.MUTED)
            self._text(cx, cy + 16, value, "mid" if compact else "big", width=cw)
            if compact:
                self._delta(cx, cy + 40, delta, note, cx + cw, unit)
                continue
            if viz is not None and viz[0] == "bar":
                self._progress(cx, cy + 62, cw, viz[1], viz[2])
            elif viz is not None:
                self._sparkline(cx, cy + 50, int(cw), 24, viz[1], viz[2])
            self._delta(cx, cy + 82, delta, note, cx + cw, unit)
        return y + th, span

    def _sparkline(self, x, y, w, h, values, color):
        """Gelombang kecil di kartu angka (tanpa sumbu). Kosong: garis datar tipis."""
        from elearning.ui import chart_art as CA
        values = [float(v) for v in values]
        if not values or max(values) <= 0:
            self._img(I.pill(int(w), 2, C.SIDEBAR_ACTIVE, C.CARD, r=1), x, y + h - 2)
            return
        top = max(values) * 1.1
        key = ("spark", int(w), int(h), color, tuple(round(v, 3) for v in values))
        self._img(self._art_img(key, lambda: CA.area(int(w), int(h), [(values, color)], C.CARD,
                                                     top, line_w=1.6, top_margin=2)), x, y)

    # --- grafik halus (chart_art: numpy, anti-alias) ---------------------------------------
    def _art_img(self, key, make):
        ph = self._art.get(key)
        if ph is None:
            try:
                from elearning import photos
                img = make()
                ph = photos.to_photoimage(img) if img is not None else None
            except Exception as exc:
                C.log(f"Analytics: grafik gagal digambar: {exc!r}")
                ph = None
            if len(self._art) > 40:
                self._art.clear()
            self._art[key] = ph
        return ph

    def _progress(self, x, y, w, frac, color, h=8):
        w = int(w)
        self._img(I.pill(w, h, C.SIDEBAR_ACTIVE, C.CARD, r=h / 2), x, y)
        fw = int(w * max(0.0, min(1.0, frac)))
        if fw >= h:
            self._img(I.pill(fw, h, color, C.SIDEBAR_ACTIVE, r=h / 2), x, y)

    def _delta(self, x, y, delta, note, right, unit="%"):
        """Panah naik / turun + keterangan abu-abu (gaya kartu angka)."""
        if delta is not None:
            up = delta >= 0
            flat = abs(delta) < 0.5
            t = self._text(x, y, f"{'' if flat else ('▲ ' if up else '▼ ')}"
                                 f"{_num(abs(delta), 0)}{unit}", "dbold",
                           C.MUTED if flat else GREEN if up else RED)
            x = self.bbox(t)[2] + 6
        if note:
            self._text(x, y, note, "label", C.MUTED, width=max(10, right - x))

    def _area_chart(self, x, y, w, h, labels, series, unit="", integer=True):
        """Grafik area melengkung (gradasi) + sumbu + keterangan saat kursor di atasnya."""
        from elearning.ui import chart_art as CA
        vals = [v for _n, values, _c in series for v in values]
        if not vals or max(vals) <= 0:
            self._text(x + w / 2, y + h / 2, "Belum ada data pada periode ini.", "name",
                       C.MUTED, anchor="center")
            return
        if integer:
            top = max(4, math.ceil(max(vals) * 1.15 / 4) * 4)
            fmt = lambda v: str(int(round(v)))
        else:
            top = max(0.4, _nice_max(max(vals) * 1.1))
            fmt = _num
        L, B = 34, 22
        x0, x1, y0, y1 = x + L, x + w, y + 6, y + h - B
        pw, ph = int(x1 - x0), int(y1 - y0)
        grid = [ph - 0.5 - (ph - 6) * k / 4 for k in range(5)]
        key = ("area", pw, ph, top, C.ACCENT,
               tuple((tuple(round(q, 3) for q in v), c) for _n, v, c in series))
        img = self._art_img(key, lambda: CA.area(pw, ph, [(v, c) for _n, v, c in series],
                                                 C.CARD, top, grid=grid, grid_color=GRID))
        self._img(img, x0, y0)
        for k in range(5):
            self._text(x0 - 8, y0 + grid[k], fmt(top * k / 4), "small", C.MUTED,
                       anchor="e")
        n = len(labels)
        xs = CA.points_x(pw, n, 0)
        slot = pw / max(1, n)
        step = max(1, math.ceil((self.f["small"].measure(max(labels, key=len)) + 8) / slot))
        for i in range(n):
            cx = x0 + xs[i]
            if i % step == 0:
                self._text(cx, y1 + 6, labels[i], "small", C.MUTED, anchor="n")
            high = max(v[i] for _n, v, _c in series)
            ty = y0 + (ph - 0.5) - (ph - 6) * high / top
            self._tips.append((cx - slot / 2, y0, cx + slot / 2, y1,
                               [labels[i]] + [f"{nm}: {fmt(v[i])}{unit}"
                                              for nm, v, _c in series],
                               ty))

    def _donut(self, x, y, w, h, parts, total, noun="pendaftar"):
        from elearning.ui import chart_art as CA
        palette = (C.ACCENT, BLUE, GREEN, PURPLE, GOLD, C.MUTED)
        size = int(max(80, min(h - 8, w * 0.48, 176)))
        thick = max(12, int(size * 0.15))
        cols = [(v, palette[i % len(palette)]) for i, (_l, v) in enumerate(parts)]
        key = ("donut", size, thick, C.ACCENT, tuple(cols))
        img = self._art_img(key, lambda: CA.donut(size, cols, C.CARD, thick,
                                                  C.SIDEBAR_ACTIVE))
        dy = y + (h - size) / 2
        self._img(img, x, dy)
        self._text(x + size / 2, dy + size / 2 - 8, str(total), "big", anchor="center")
        self._text(x + size / 2, dy + size / 2 + 16, noun, "small", C.MUTED, anchor="center")
        lx = x + size + 22
        if not parts:
            self._text(lx, y + h / 2, "Belum ada data.", "name", C.MUTED, anchor="w")
            return
        row = 26
        ly = y + (h - len(parts) * row) / 2
        for i, (label, v) in enumerate(parts):
            yy = ly + i * row + row / 2
            self._img(I.dot(palette[i % len(palette)], C.CARD), lx, yy, anchor="w")
            pct = f"{round(v / total * 100)}%" if total else "0%"
            pw = self.f["val"].measure(pct)
            self._text(x + w, yy, pct, "val", anchor="e")
            self._text(lx + 16, yy, label, "label", C.TEXT, anchor="w",
                       width=max(20, x + w - pw - 12 - lx - 16))
            self._tips.append((lx, yy - row / 2, x + w, yy + row / 2,
                               [label, f"{v} {noun}"], yy - 8))

    def _table(self, x, y, w, cols, rows, empty):
        """cols: [(judul, posisi 0..1, anchor)], rows: [[(teks, warna, font)...]]."""
        for title, fx, anchor in cols:
            self._text(x + w * fx, y, title, "small", C.MUTED, anchor=anchor)
        y += 22
        self.create_line(x, y - 4, x + w, y - 4, fill=GRID)
        if not rows:
            self._text(x, y + 6, empty, "name", C.MUTED)
            return y + 30
        for r in rows:
            for (title, fx, anchor), (text, color, font) in zip(cols, r):
                lim = None
                if anchor == "nw":
                    nxt = [c[1] for c in cols if c[1] > fx]
                    lim = w * ((min(nxt) if nxt else 1.0) - fx) - 10
                self._text(x + w * fx, y + 6, text, font, color, anchor=anchor, width=lim)
            y += 30
            self.create_line(x, y - 1, x + w, y - 1, fill=GRID)
        return y

    # --- bagian Pendaftar dari trial ----------------------------------------------------------
    def _signup_tiles(self, su, x, y, w, span, compact=False):
        prev = "vs sebelumnya"
        gap = 8 if compact else GAP
        tw = (w - 3 * gap) / 4
        th = 100 if compact else 124
        big = "mid" if compact else "big"
        off = (40, 48, 60) if compact else (52, 58, 74)
        for i in range(4):
            tx = x + i * (tw + gap)
            cx, cy, cw = self._card(tx, y, tw, th, compact=compact)
            right = cx + cw
            if i == 0:
                conv = su.get("conv")
                self._text(cx, cy, "Konversi jadi murid", "label", C.MUTED)
                self._text(cx, cy + 16, "–" if conv is None else f"{_num(conv, 0)}%", big)
                self._progress(cx, cy + off[1], cw, (conv or 0) / 100.0, C.ACCENT)
                self._delta(cx, cy + off[2], su.get("conv_delta"),
                            f"{su['approved']} dari {su['total']} pendaftar", right, " poin")
            elif i == 1:
                self._text(cx, cy, "Pendaftar baru", "label", C.MUTED)
                self._text(cx, cy + 16, str(su["total"]), big)
                vals = su["series"]["new"]
                sw, sh = int(cw * 0.55), int(off[1] - 6)
                if any(vals) and sw > 40:
                    from elearning.ui import chart_art as CA
                    top = max(1, max(vals)) * 1.1
                    img = self._art_img(("spark", sw, sh, tuple(vals)), lambda: CA.area(
                        sw, sh, [(vals, BLUE)], C.CARD, top, line_w=1.6, top_margin=3))
                    self._img(img, right - sw, cy + 4)
                self._delta(cx, cy + off[2], su.get("total_delta"),
                            prev if su.get("total_delta") is not None else span, right)
            elif i == 2:
                self._text(cx, cy, "Menunggu persetujuan", "label", C.MUTED)
                self._text(cx, cy + 16, str(su["pending"]), big,
                           C.ACCENT if su["pending"] else C.TEXT)
                od = su.get("oldest_days")
                self._text(cx, cy + off[2], "semua sudah diproses" if not su["pending"] else
                           ("masuk hari ini" if not od else f"tertua menunggu {od} hari"),
                           "label", C.MUTED, width=cw)
                if not compact:
                    self._text(cx, cy + off[1] - 4, f"{su['rejected']} ditolak  ·  "
                                                    f"{su['approved']} jadi murid",
                               "small", C.MUTED, width=cw)
            else:
                age, kids = su.get("avg_age"), su.get("kids_pct")
                self._text(cx, cy, "Rata-rata umur", "label", C.MUTED)
                self._text(cx, cy + 16, "–" if age is None else f"{_num(age, 0)} th", big)
                self._progress(cx, cy + off[1], cw, (kids or 0) / 100.0, BLUE)
                self._text(cx, cy + off[2], "–" if kids is None else
                           f"anak \u2264 12 th: {_num(kids, 0)}%", "label", C.MUTED, width=cw)
        return y + th

    def _signup_full(self, d, y, W):
        su = d.get("signups")
        if not su:
            return y
        s0, s1 = d["range"]
        span = f"{A._day_label(s0)} – {A._day_label(s1)} {s1.year}"
        self._text(0, y + 6, "Pendaftar dari trial", "mid")
        self._text(W, y + 12, "survey calon murid setelah trial  ·  semua program  ·  "
                              f"{d['period_label']}", "sub", C.MUTED, anchor="ne")
        y += 44
        y = self._signup_tiles(su, 0, y, W, span) + GAP
        left = (W - GAP) * 0.62
        right = W - GAP - left
        h = 300
        cx, cy, cw = self._card(0, y, left, h,
                                f"Pendaftar & jadi murid per {su['series']['unit']}")
        lx = left - 18
        for name, color in (("Jadi murid", C.ACCENT), ("Pendaftar", BLUE)):
            t = self._text(lx, y + 18, name, "label", C.MUTED, anchor="ne")
            lx = self.bbox(t)[0] - 14
            self._img(I.dot(color, C.CARD), lx, y + 25, anchor="w")
            lx -= 14
        sr = su["series"]
        self._area_chart(cx, cy, cw, h - (cy - y) - 16, sr["labels"],
                         [("Pendaftar", sr["new"], BLUE), ("Jadi murid", sr["approved"],
                                                          C.ACCENT)], " orang")
        cx, cy, cw = self._card(left + GAP, y, right, h, "Tahu dari mana",
                                f"{su['total']} pendaftar")
        self._donut(cx, cy, cw, h - (cy - y) - 16, su["sources"], su["total"])
        y += h + GAP
        half = (W - GAP) / 2
        h = 48 + 16 + 22 + len(su["ages"]) * 30 + 8
        cx, cy, cw = self._card(0, y, half, h, "Kelompok umur",
                                "konversi = jadi murid / pendaftar")
        rows = []
        for r in su["ages"]:
            dl = r["delta"]
            dtext, dcol = ("–", C.MUTED) if dl is None else ("0%", C.MUTED)                 if abs(dl) < 0.5 else (
                (f"▲ {_num(abs(dl), 0)}%", GREEN) if dl >= 0 else (f"▼ {_num(abs(dl), 0)}%", RED))
            rows.append([(r["label"], C.TEXT, "name"), (str(r["n"]), C.TEXT, "name"),
                         (str(r["approved"]), C.TEXT, "name"),
                         ("–" if r["conv"] is None else f"{_num(r['conv'], 0)}%", C.TEXT, "val"),
                         (dtext, dcol, "dbold")])
        self._table(cx, cy, cw, [("Umur", 0, "nw"), ("Pendaftar", 0.30, "nw"),
                                 ("Jadi murid", 0.52, "nw"), ("Konversi", 0.74, "nw"),
                                 ("Dinamika", 1.0, "ne")], rows, "Belum ada pendaftar.")
        cx, cy, cw = self._card(half + GAP, y, half, h, "Minat kelas", d["period_label"])
        palette = (C.ACCENT, BLUE, GREEN, PURPLE, GOLD, C.MUTED)
        tot = sum(v for _l, v in su["interests"]) or 1
        top = max([v for _l, v in su["interests"]] + [1])
        bars = [{"title": lbl, "count": v, "frac": v / top, "color": palette[i % 6],
                 "text": f"{round(v / tot * 100)}%"} for i, (lbl, v) in enumerate(su["interests"])]
        self._hbars(cx, cy + 4, cw, bars, "Belum ada pendaftar.", lw=150, vw=44)
        y += h + GAP
        rec = su["recent"]
        h = 48 + 16 + 22 + max(1, len(rec)) * 30 + 30
        cx, cy, cw = self._card(0, y, W, h, "Menunggu persetujuan",
                                f"{su['pending']} pendaftar  ·  setujui di menu Pendaftar")
        rows = [[(r["name"], C.TEXT, "name"), (f"{r['age']} th" if r["age"] else "-", C.TEXT,
                                               "name"),
                 (r["interest"] or "-", C.TEXT, "name"), (r["phone"] or "-", C.MUTED, "name"),
                 (r["at"][:16], C.MUTED, "name")] for r in rec]
        end = self._table(cx, cy, cw, [("Nama", 0, "nw"), ("Umur", 0.34, "nw"),
                                       ("Minat", 0.44, "nw"), ("Telepon", 0.66, "nw"),
                                       ("Masuk", 1.0, "ne")], rows,
                          "Tidak ada pendaftar yang menunggu.")
        od = su.get("oldest_days")
        if su["pending"]:
            t = self._text(cx, end + 8, "Tertua menunggu: ", "label", C.MUTED)
            self._text(self.bbox(t)[2], end + 8, "hari ini" if not od else f"{od} hari",
                       "dbold", C.ACCENT)
        return y + h

    def _signup_compact(self, d, y, W):
        su = d.get("signups")
        if not su:
            return y
        g = 8
        third = (W - 2 * g) / 3
        h = 214
        cx, cy, cw = self._card(0, y, third, h, "Pendaftar trial", d["period_label"],
                                compact=True)
        conv = su.get("conv")
        self._text(cx, cy, "Konversi jadi murid", "label", C.MUTED)
        self._text(cx, cy + 16, "–" if conv is None else f"{_num(conv, 0)}%", "mid")
        self._progress(cx, cy + 46, cw, (conv or 0) / 100.0, C.ACCENT)
        self._text(cx, cy + 62, f"{su['approved']} dari {su['total']} pendaftar", "label",
                   C.MUTED, width=cw)
        self._text(cx, cy + 92, "Menunggu persetujuan", "label", C.MUTED)
        self._text(cx, cy + 108, str(su["pending"]), "mid",
                   C.ACCENT if su["pending"] else C.TEXT)
        cx, cy, cw = self._card(third + g, y, third, h,
                                f"Pendaftar per {su['series']['unit']}",
                                compact=True)
        sr = su["series"]
        self._area_chart(cx, cy, cw, h - (cy - y) - 12, sr["labels"],
                         [("Pendaftar", sr["new"], BLUE), ("Jadi murid", sr["approved"],
                                                          C.ACCENT)], " orang")
        cx, cy, cw = self._card(2 * (third + g), y, third, h, "Tahu dari mana", compact=True)
        self._donut(cx, cy, cw, h - (cy - y) - 12, su["sources"][:4], su["total"])
        return y + h

    # --- grafik --------------------------------------------------------------------------
    def _bars(self, x, y, w, h, labels, series, unit, integer=False):
        totals = [sum(s[1][i] for s in series) for i in range(len(labels))]
        if not totals or max(totals) <= 0:
            self._text(x + w / 2, y + h / 2, "Belum ada data pada periode ini.", "name",
                       C.MUTED, anchor="center")
            return
        # label 1 desimal: skala minimum 0,4 supaya label sumbu tidak semuanya "0,0"
        top = max(0.4, _nice_max(max(totals)))
        if integer:
            top = max(4, math.ceil(max(totals) / 4) * 4)
        L, B = 40, 22
        x0, x1, y0, y1 = x + L, x + w, y + 6, y + h - B
        fmt = (lambda v: str(int(round(v)))) if integer else _num
        for k in range(5):
            v = top * k / 4
            yy = y1 - (y1 - y0) * k / 4
            self.create_line(x0, yy, x1, yy, fill=GRID)
            self._text(x0 - 8, yy, fmt(v), "small", C.MUTED, anchor="e")
        n = len(totals)
        slot = (x1 - x0) / n
        bw = max(3, min(26, slot * 0.62))
        step = max(1, math.ceil((self.f["small"].measure(max(labels, key=len)) + 8) / slot))
        for i in range(n):
            cx = x0 + slot * (i + 0.5)
            base = y1
            for _name, values, color in series:
                v = values[i]
                if v <= 0:
                    continue
                bh = max(2, (y1 - y0) * v / top)
                self._img(I.pill(int(bw), int(bh), color, C.CARD, r=min(4, bw / 2, bh / 2)),
                          cx - bw / 2, base - bh)
                base -= bh + (2 if len(series) > 1 else 0)
            lines = [labels[i]] + [f"{nm}: {fmt(vals[i])}{unit}" for nm, vals, _c in series]
            self._tips.append((cx - slot / 2, y0, cx + slot / 2, y1, lines, base))
            if i % step == 0:
                self._text(cx, y1 + 6, labels[i], "small", C.MUTED, anchor="n")

    def _heat(self, x, y, w, grid, ch):
        cols = len(A.HEAT_HOURS)
        L = 32
        cw = min(34.0, (w - L) / cols)
        left = x + max(L, (w - cw * cols) / 2)
        top = max([max(r) for r in grid] + [0])
        for j, hour in enumerate(A.HEAT_HOURS):
            if j % 2 == 0:
                self._text(left + cw * (j + 0.5), y, f"{hour:02d}", "small", C.MUTED,
                           anchor="n")
        y0 = y + 16
        for d in range(7):
            yy = y0 + d * (ch + 2)
            self._text(left - 8, yy + ch / 2, A.DAY_SHORT[d], "small", C.MUTED, anchor="e")
            for j in range(cols):
                v = grid[d][j]
                t = math.sqrt(v / top) if top > 0 else 0.0
                level = round(t * 6) / 6          # dibulatkan: gambar kotak bisa dipakai ulang
                color = _mix(C.SIDEBAR_ACTIVE, C.ACCENT, level) if v > 0 else C.SIDEBAR_ACTIVE
                xx = left + j * cw
                self._img(I.pill(int(cw - 3), ch, color, C.CARD, r=min(5, ch / 3)), xx, yy)
                hour = A.HEAT_HOURS[j]
                self._tips.append((xx, yy, xx + cw, yy + ch,
                                   [f"{A.DAY_SHORT[d]}  {hour:02d}.00 - {hour + 1:02d}.00",
                                    f"rata-rata {_num(v)} murid login"], yy))
        return y0 + 7 * (ch + 2)

    def _hbars(self, x, y, w, rows, empty="Belum ada kursus.", lw=118, vw=64):
        top = max([r["count"] for r in rows] + [1])
        bx, bw = x + lw, w - lw - vw - 8
        for i, r in enumerate(rows):
            yy = y + i * 26
            self._text(x, yy + 6, r["title"], "label", width=lw - 8, anchor="w")
            self._img(I.pill(int(bw), 10, C.SIDEBAR_ACTIVE, C.CARD, r=5), bx, yy + 1)
            frac = r["frac"] if "frac" in r else r["count"] / top
            fw = int(bw * frac)
            if fw >= 6:
                self._img(I.pill(fw, 10, r["color"], C.SIDEBAR_ACTIVE, r=5), bx, yy + 1)
            self._text(x + w, yy + 6, r.get("text", f"{r['count']} murid"), "label", C.MUTED,
                       anchor="e")
        if not rows:
            self._text(x, y, empty, "name", C.MUTED)
        return y + max(1, len(rows)) * 26

    def _people(self, x, y, w, rows, empty, limit, compact, key):
        """rows: (id, nama, keterangan, nilai, warna). Nama bisa diklik (kalau on_open ada)."""
        line_h = 24 if compact else 42
        for i, (pid, name, note, right, color) in enumerate(rows[:limit]):
            yy = y + i * line_h
            tag = f"{key}{i}"
            self._text(x, yy + 1, str(i + 1), "label", C.LOCKED)
            vw = self.f["val"].measure(right) + 10 if right else 0
            if right:
                self._text(x + w, yy, right, "val", color or C.TEXT, anchor="ne")
            q = self.query.strip().lower()
            i = name.lower().find(q) if q else -1
            if i >= 0:   # sorot bagian nama yang cocok dengan pencarian
                f = self.f["name"]
                hx = x + 22 + f.measure(name[:i])
                hw = f.measure(name[i:i + len(q)])
                self._img(I.pill(int(hw + 4), int(f.metrics("linespace") + 2), HIGHLIGHT,
                                 C.CARD, r=4), hx - 2, yy - 1)
            nm = self._text(x + 22, yy, name, "name", width=w - 22 - vw, tags=(tag,))
            if not compact:
                self._text(x + 22, yy + 19, f"{pid}  ·  {note}" if note else pid,
                           "small", C.MUTED, width=w - 22 - vw, tags=(tag,))
            if self.on_open:
                self.tag_bind(tag, "<Button-1>", lambda e, p=pid: self.on_open(p))
                self.tag_bind(tag, "<Enter>", lambda e, n=nm: (
                    self.itemconfigure(n, fill=C.ACCENT_HOVER), self.config(cursor="hand2")))
                self.tag_bind(tag, "<Leave>", lambda e, n=nm: (
                    self.itemconfigure(n, fill=C.TEXT), self.config(cursor="")))
        end = y + min(len(rows), limit) * line_h
        if not rows:
            self._text(x, y, empty, "name", C.MUTED)
            end = y + 22
        elif len(rows) > limit:
            self._text(x, end + 2, f"+ {len(rows) - limit} lainnya", "label", C.MUTED)
            end += 22
        return end

    def _legend(self, x, y):
        for name, color in (("Gambar", C.ACCENT), ("Video", BLUE), ("Assignment", GREEN)):
            self._img(I.dot(color, C.CARD), x, y + 7, anchor="w")
            t = self._text(x + 12, y, name, "label", C.MUTED)
            x = self.bbox(t)[2] + 16

    @staticmethod
    def _rows(d):
        teachers = [(t["id"], t["name"], f"{t['reports']} laporan  ·  "
                                         f"{t['sessions']}x login",
                     A.fmt_hours(t["seconds"]), None) for t in d["teachers"]]
        attention = [(a["id"], a["name"], a["reason"], "", None) for a in d["attention"]]
        top = [(t["id"], t["name"], f"{t['uploads']} portfolio  ·  {t.get('badges', 0)} badge",
                A.fmt_hours(t["seconds"]),
                C.ACCENT_HOVER) for t in d["top"]]
        return teachers, attention, top

    @staticmethod
    def _need(rows, limit, line_h):
        return (min(len(rows), limit) or 1) * line_h + (22 if len(rows) > limit else 0)

    # --- susunan Lengkap ---------------------------------------------------------------------
    def _full(self, d, W):
        y, span = self._tiles(d, 0, 0, W, compact=False)
        k = d["kpi"]
        unit = d["unit"]
        y += GAP
        ch = 300   # Jam belajar (lebar penuh)
        cx, cy, cw = self._card(0, y, W, ch, f"Jam belajar murid per {unit}",
                                f"{k['learners']} murid belajar  ·  {span}")
        self._area_chart(cx, cy, cw, ch - (cy - y) - 16, d["hours"]["labels"],
                         [("Jam belajar", d["hours"]["values"], C.ACCENT)], " jam",
                         integer=False)
        y += ch + GAP + 8
        y = self._signup_full(d, y, W) + GAP + 8     # Pendaftar dari trial (survey)
        self._text(0, y + 6, "Aktivitas kelas", "mid")
        y += 44
        half = (W - GAP) / 2
        h = 292    # Jam ramai | Portfolio
        cx, cy, cw = self._card(0, y, half, h, "Jam ramai kelas",
                                "rata-rata murid login per jam")
        self._heat(cx, cy, cw, d["heat"], 24)
        cx, cy, cw = self._card(half + GAP, y, half, h,
                                f"Upload portfolio & assignment per {unit}")
        pf = d["portfolio"]
        self._bars(cx, cy, cw, h - (cy - y) - 44, pf["labels"], self._pf_series(pf),
                   " file", integer=True)
        self._legend(cx, y + h - 34)
        y += h + GAP
        # Kehadiran per jadwal | Badge terbanyak
        sched, badges = d.get("schedule", []), d.get("badges", [])
        h = 48 + 16 + max(max(1, len(sched)), max(1, len(badges))) * 26
        cx, cy, cw = self._card(0, y, half, h, "Kehadiran per jadwal",
                                f"login ≥ {A.PRESENT_MIN} menit di jam jadwal")
        self._hbars(cx, cy, cw, sched, "Belum ada jadwal yang sudah berjalan.", lw=150,
                    vw=110)
        cx, cy, cw = self._card(half + GAP, y, half, h, "Badge paling banyak didapat",
                                f"{k.get('badges', 0)} badge baru  ·  {span}")
        self._hbars(cx, cy, cw, badges, "Belum ada badge.", lw=170, vw=70)
        y += h + GAP
        teachers, attention, top = self._rows(d)
        # Murid per kursus | Aktivitas guru
        h = 48 + 16 + max(max(1, len(d["courses"])) * 26, self._need(teachers, 10, 42))
        cx, cy, cw = self._card(0, y, half, h, "Murid per kursus",
                                "kursus yang sudah dibuka guru")
        self._hbars(cx, cy, cw, d["courses"])
        cx, cy, cw = self._card(half + GAP, y, half, h, "Aktivitas guru",
                                f"jam online  ·  {k['reports']} laporan")
        self._people(cx, cy, cw, teachers, "Belum ada guru.", 10, False, "tg")
        y += h + GAP
        # Perlu diperhatikan | Paling rajin
        h = 48 + 16 + max(self._need(attention, 10, 42), self._need(top, 10, 42))
        cx, cy, cw = self._card(0, y, half, h, "Murid perlu diperhatikan",
                                f"tidak login ≥ {A.INACTIVE_DAYS} hari / belum upload / "
                                "absen jadwal")
        self._people(cx, cy, cw, attention, "Semua murid aktif.", 10, False, "at")
        cx, cy, cw = self._card(half + GAP, y, half, h, f"{A.TOP_N} murid paling rajin",
                                d["period_label"])
        self._people(cx, cy, cw, top, "Belum ada murid yang belajar.", 10, False, "tp")
        return y + h + 4

    # --- susunan Ringkas (3 kolom, muat satu layar) ------------------------------------------
    def _compact(self, d, W):
        y, _span = self._tiles(d, 0, 0, W, compact=True)
        unit = d["unit"]
        g = 8
        third = (W - 2 * g) / 3
        y += g
        h = 214
        cx, cy, cw = self._card(0, y, third, h, f"Jam belajar per {unit}", compact=True)
        self._area_chart(cx, cy, cw, h - (cy - y) - 12, d["hours"]["labels"],
                         [("Jam belajar", d["hours"]["values"], C.ACCENT)], " jam",
                         integer=False)
        cx, cy, cw = self._card(third + g, y, third, h, f"Upload per {unit}", compact=True)
        pf = d["portfolio"]
        self._bars(cx, cy, cw, h - (cy - y) - 12, pf["labels"], self._pf_series(pf),
                   " file", integer=True)
        cx, cy, cw = self._card(2 * (third + g), y, third, h, "Jam ramai kelas", compact=True)
        self._heat(cx, cy, cw, d["heat"], 16)
        y += h + g
        y = self._signup_compact(d, y, W) + g      # Pendaftar dari trial (survey)
        teachers, attention, top = self._rows(d)
        h = 40 + 12 + max(self._need(attention, 5, 24), self._need(top, 5, 24),
                          self._need(teachers, 5, 24))
        cx, cy, cw = self._card(0, y, third, h, "Perlu diperhatikan",
                                f"{len(attention)} murid", compact=True)
        self._people(cx, cy, cw, attention, "Semua murid aktif.", 5, True, "at")
        cx, cy, cw = self._card(third + g, y, third, h, "Paling rajin", d["period_label"],
                                compact=True)
        self._people(cx, cy, cw, top, "Belum ada data.", 5, True, "tp")
        cx, cy, cw = self._card(2 * (third + g), y, third, h, "Aktivitas guru", "jam online",
                                compact=True)
        self._people(cx, cy, cw, teachers, "Belum ada guru.", 5, True, "tg")
        y += h + g
        half = (W - g) / 2
        sched, badges = d.get("schedule", [])[:5], d.get("badges", [])[:5]
        h = 40 + 12 + max(1, len(sched), len(badges)) * 26
        cx, cy, cw = self._card(0, y, half, h, "Kehadiran per jadwal", compact=True)
        self._hbars(cx, cy, cw, sched, "Belum ada jadwal yang berjalan.", lw=150, vw=110)
        cx, cy, cw = self._card(half + g, y, half, h, "Badge terbanyak", compact=True)
        self._hbars(cx, cy, cw, badges, "Belum ada badge.", lw=170, vw=70)
        return y + h + 4

    @staticmethod
    def _pf_series(pf):
        return [("Gambar", pf["images"], C.ACCENT), ("Video", pf["videos"], BLUE),
                ("Assignment", pf.get("assignments", [0] * len(pf["images"])), GREEN)]

    # --- keterangan saat kursor di atas batang / kotak -------------------------------------
    def _motion(self, e):
        x, y = self.canvasx(e.x), self.canvasy(e.y)
        for x0, y0, x1, y1, lines, top in self._tips:
            if x0 <= x < x1 and y0 <= y < y1:
                self._show_tip((x0 + x1) / 2, top, lines)
                return
        self.delete("tip")

    def _show_tip(self, x, y, lines):
        self.delete("tip")
        f = self.f["label"]
        w = max(f.measure(t) for t in lines) + 20
        h = len(lines) * (f.metrics("linespace") + 2) + 12
        x = min(max(4, x - w / 2), self.winfo_width() - w - 4)
        y = max(2, y - h - 8)
        img = I.pill(int(w), int(h), "#141413", C.CARD, r=8, border=C.BORDER)
        if img is not None:
            self._tip_img = img
            self.create_image(x, y, image=img, anchor="nw", tags="tip")
        ty = y + 7
        for i, t in enumerate(lines):
            self.create_text(x + 10, ty, text=t, anchor="nw", tags="tip",
                             fill=C.TEXT if i == 0 else C.MUTED,
                             font=self.f["dbold"] if i == 0 else f)
            ty += f.metrics("linespace") + 2


class AnalyticsPanel(tk.Frame):
    """Bar filter (periode, program, tampilan) + AnalyticsBoard.

    state: dict yang diingat Panel Admin ({"period", "program", "view"}).
    on_open(id): buka murid / guru di tab-nya.
    """

    CACHE_SEC = 120   # hasil per filter disimpan sebentar: pindah bolak-balik instan

    def __init__(self, master, state, on_open=None):
        super().__init__(master, bg=C.BG)
        self.state = state
        self._cache = {}
        self._job = None

        bar = tk.Frame(self, bg=C.BG)
        bar.pack(fill="x", pady=(0, 14))
        tk.Label(bar, text="Periode", bg=C.BG, fg=C.MUTED, font=(C.FONT, 10)).pack(
            side="left", padx=(0, 10))
        self._pbtns = {}
        for key, label, _n in A.PERIODS:
            b = RoundButton(bar, text=label, command=lambda k=key: self._set("period", k),
                            font=(C.FONT, 10), padx=12, pady=5)
            b.pack(side="left", padx=(0, 6))
            self._pbtns[key] = b
        self._prog_labels = dict(A.PROGRAMS)
        self._prog_keys = {v: k for k, v in A.PROGRAMS}
        self.prog_var = tk.StringVar(value=self._prog_labels[state.get("program", "all")])
        RoundSelect(bar, self.prog_var, *self._prog_labels.values(),
                    command=lambda v: self._set("program", self._prog_keys[v])).pack(
            side="left", padx=(18, 0))
        self._vbtns = {}
        for key, label in (("compact", "Ringkas"), ("full", "Lengkap")):
            b = RoundButton(bar, text=label, command=lambda k=key: self._set_view(k),
                            font=(C.FONT, 10), padx=12, pady=5)
            b.pack(side="right", padx=(6, 0))
            self._vbtns[key] = b
        tk.Label(bar, text="Tampilan", bg=C.BG, fg=C.MUTED, font=(C.FONT, 10)).pack(
            side="right", padx=(0, 4))
        # lebar tetap: muncul / hilangnya teks tidak menggeser tombol lain
        self.status = tk.Label(bar, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 9),
                               width=14, anchor="w")
        self.status.pack(side="left", padx=(14, 0))
        self._paint()

        self.board = AnalyticsBoard(self, on_open=on_open)
        self.board.pack(fill="x")
        self.load()

    def _paint(self):
        groups = ((self._pbtns, self.state.get("period", "30d")),
                  (self._vbtns, self.state.get("view", "full")))
        for btns, current in groups:
            for k, b in btns.items():
                on = k == current
                b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
                         activebackground=C.SEG_ON if on else C.CARD_HOVER,
                         activeforeground=C.TEXT)

    def _set_view(self, view):
        if self.state.get("view", "full") == view:
            return
        self.state["view"] = view
        self._paint()
        if self.board.data is not None:
            self.board.set_data(self.board.data, view)

    def _set(self, key, value):
        if self.state.get(key) == value:
            return
        self.state[key] = value
        self._paint()
        self.load()

    def _key(self):
        return (self.state.get("period", "30d"), self.state.get("program", "all"))

    def load(self):
        key = self._key()
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < self.CACHE_SEC:
            self.board.set_data(hit[1], self.state.get("view", "full"))
            return
        self.status.config(text="Menghitung…")
        box = {}

        def work():
            try:
                box["data"] = A.compute(*key)
            except Exception as exc:
                C.log(f"Analytics gagal dihitung: {exc!r}")
                box["error"] = exc

        threading.Thread(target=work, daemon=True).start()
        self._poll(box, key)

    def _poll(self, box, key):
        if not self.winfo_exists():
            return
        if not box:
            self._job = self.after(60, lambda: self._poll(box, key))
            return
        self._job = None
        if "data" in box:
            self._cache[key] = (time.time(), box["data"])
        if key != self._key():
            return   # filter sudah berganti lagi; hasil ini disimpan saja
        if "error" in box:
            self.status.config(text="Gagal. Lihat app.log")
            return
        self.status.config(text="")
        self.board.set_data(box["data"], self.state.get("view", "full"))

    def destroy(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
        super().destroy()
