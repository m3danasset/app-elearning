"""Halaman Analytics di Panel Admin.

Seluruh isi (kartu angka, grafik, daftar) digambar di SATU canvas (AnalyticsBoard).
Canvas Tk menggambar isinya di memori dulu lalu menampilkannya sekaligus, jadi:
  - ganti periode / program (hanya tampilan Ringkas; Lengkap sudah dihapus),
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
        self.view = "compact"
        self._imgs = []
        self._tips = []          # (x0, y0, x1, y1, [baris teks], y_atas) area berketerangan
        self._width = 0
        self._tip_img = None
        self._art = {}           # gambar grafik halus (area / donut) per ukuran & data
        self.query = ""          # kata dari kolom cari admin: nama yang cocok disorot
        self.fit_h = 0           # tinggi layar yang tersedia (kisi kartu dibuat pas)
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
        h = self._compact(self.data, w)
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
            ("Survey murid", str((d.get("student_survey") or {}).get("count", 0)),
             "jawaban  ·  " + d["period_label"], None, "%", None),
            ("Tugas guru", f"{sum(t['done'] for t in d.get('tasks') or [])}"
                           f"/{sum(t['total'] for t in d.get('tasks') or [])}",
             "selesai bulan ini", None, "%", None),
        )
        gap = 8 if compact else GAP
        per_row = len(items)
        if (w - (per_row - 1) * gap) / per_row < 118:     # sempit: 2 baris kartu angka
            per_row = math.ceil(len(items) / 2)
        tw = (w - (per_row - 1) * gap) / per_row
        th = 84 if compact else 132
        for i, (label, value, note, delta, unit, viz) in enumerate(items):
            tx = x + (i % per_row) * (tw + gap)
            ty = y + (i // per_row) * (th + gap)
            cx, cy, cw = self._card(tx, ty, tw, th, compact=compact)
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
        n_rows = math.ceil(len(items) / per_row)
        return y + n_rows * th + (n_rows - 1) * gap, span

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
        size = int(max(44, min(h - 6, w * 0.48, 176)))   # kartu pendek: donut mengecil
        thick = max(12, int(size * 0.15))
        cols = [(v, palette[i % len(palette)]) for i, (_l, v) in enumerate(parts)]
        key = ("donut", size, thick, C.ACCENT, tuple(cols))
        img = self._art_img(key, lambda: CA.donut(size, cols, C.CARD, thick,
                                                  C.SIDEBAR_ACTIVE))
        dy = y + (h - size) / 2
        self._img(img, x, dy)
        small = size < 100                        # donut kecil: angka ikut kecil
        self._text(x + size / 2, dy + size / 2 - (6 if small else 8), str(total),
                   "mid" if small else "big", anchor="center")
        self._text(x + size / 2, dy + size / 2 + (11 if small else 16), noun, "small", C.MUTED,
                   anchor="center")
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

    # --- bagian Pendaftar dari trial ----------------------------------------------------------
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
            if ch >= 10 or d % 2 == 0:            # baris sempit: label hari selang-seling
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

    # --- susunan Dashboard: kartu angka + kisi grafik, PAS satu layar saat layar penuh -------
    # 4 kolom x 4 baris (>= 1000 px), 3 kolom (>= 760), 2 kolom. Tinggi kartu = sisa tinggi
    # layar dibagi rata (fit_h dari AnalyticsPanel); kalau terlalu pendek (< MIN_CARD_H) baru
    # boleh digulir.
    MIN_CARD_H = 128

    def _compact(self, d, W):
        g = 8
        y, _span = self._tiles(d, 0, 0, W, compact=True)
        y += g
        cards = self._cards(d)
        cols = 4 if W >= 1000 else 3 if W >= 760 else 2
        rows = math.ceil(len(cards) / cols)
        avail = (self.fit_h or 0) - y - 2
        ch = max(self.MIN_CARD_H, (avail - g * (rows - 1)) / rows) if avail > 0 else 214
        cw = (W - g * (cols - 1)) / cols
        for n, (title, sub, draw) in enumerate(cards):
            r, c = divmod(n, cols)
            x, yy = c * (cw + g), y + r * (ch + g)
            cx, cy, iw = self._card(x, yy, cw, ch, title, sub, compact=True)
            try:
                draw(cx, cy, iw, yy + ch - 12 - cy)
            except Exception as exc:             # satu kartu gagal: kartu lain tetap tampil
                C.log(f"Analytics: kartu {title!r} gagal: {exc!r}")
                self._text(cx, cy, "Gagal digambar (lihat app.log).", "name", C.MUTED)
        return y + rows * ch + (rows - 1) * g

    def _cards(self, d):
        """[(judul, sub, gambar(x, y, lebar, tinggi))] urut tampil (16 kartu)."""
        unit = d["unit"]
        su = d.get("signups") or {}
        ss = d.get("student_survey") or {}
        tally = ss.get("tally") or []
        teachers, attention, top = self._rows(d)
        pf = d["portfolio"]
        cats = d.get("categories") or []
        n_cat = sum(v for _l, v in cats)

        def hours(x, y, w, h):
            self._area_chart(x, y, w, h, d["hours"]["labels"],
                             [("Jam belajar", d["hours"]["values"], C.ACCENT)], " jam",
                             integer=False)

        def uploads(x, y, w, h):
            self._bars(x, y, w, h, pf["labels"], self._pf_series(pf), " file", integer=True)

        def heat(x, y, w, h):
            self._heat(x, y, w, d["heat"], max(8, min(18, (h - 16) / 7 - 2)))

        def categories(x, y, w, h):
            self._donut(x, y, w, h, cats, n_cat, "murid")

        def weekday(x, y, w, h):
            vals = d.get("weekday") or [0] * 7
            self._bars(x, y, w, h, list(A.WEEKDAYS), [("Rata-rata", vals, BLUE)], " jam murid")

        def conv(x, y, w, h):
            c = su.get("conv")
            self._text(x, y, "Konversi jadi murid", "label", C.MUTED)
            self._text(x, y + 16, "–" if c is None else f"{_num(c, 0)}%", "mid")
            self._progress(x, y + 46, w, (c or 0) / 100.0, C.ACCENT)
            self._text(x, y + 62, f"{su.get('approved', 0)} dari {su.get('total', 0)} pendaftar",
                       "label", C.MUTED, width=w)
            if h >= 120:
                self._text(x, y + 92, "Menunggu persetujuan", "label", C.MUTED)
                self._text(x, y + 108, str(su.get("pending", 0)), "mid",
                           C.ACCENT if su.get("pending") else C.TEXT)

        def signups(x, y, w, h):
            sr = su.get("series") or {"labels": [], "new": [], "approved": []}
            self._area_chart(x, y, w, h, sr["labels"],
                             [("Pendaftar", sr["new"], BLUE), ("Jadi murid", sr["approved"],
                                                              C.ACCENT)], " orang")

        def sources(x, y, w, h):
            self._donut(x, y, w, h, (su.get("sources") or [])[:4], su.get("total", 0))

        def survey_donut(x, y, w, h):
            if not tally:
                self._text(x, y, "Belum ada pertanyaan pilihan.", "name", C.MUTED)
                return
            q, counts, answered = tally[0]
            self._text(x, y, q["text"], "label", C.MUTED, width=w)
            self._donut(x, y + 16, w, h - 16, counts[:5], answered, "murid")

        def survey_bars(x, y, w, h):
            if len(tally) < 2:
                self._text(x, y, "Belum ada pertanyaan pilihan kedua.", "name", C.MUTED)
                return
            q, counts, answered = tally[1]
            self._text(x, y, q["text"], "label", C.MUTED, width=w)
            topc = max([c for _o, c in counts] + [1])
            rows = [{"title": o, "count": c, "frac": c / topc, "color": PURPLE,
                     "text": f"{c} murid"} for o, c in counts][:max(1, int((h - 20) // 26))]
            self._hbars(x, y + 22, w, rows, "Belum ada jawaban.", lw=96, vw=60)

        def tasks(x, y, w, h):
            rows = []
            for t in (d.get("tasks") or [])[:max(1, int(h // 26))]:
                frac = t["done"] / t["total"] if t["total"] else 0
                rows.append({"title": t["title"], "count": t["done"], "frac": frac,
                             "color": GREEN, "text": f"{t['done']}/{t['total']} selesai"})
            self._hbars(x, y, w, rows, "Belum ada tugas bulan ini.", lw=96, vw=84)

        def courses(x, y, w, h):
            self._hbars(x, y, w, d["courses"][:max(1, int(h // 26))], lw=110, vw=64)

        def people(rows, empty, key):
            def draw(x, y, w, h):
                self._people(x, y, w, rows, empty, max(1, int((h - 22) // 24)), True, key)
            return draw

        def hbars(rows, empty, lw, vw):
            def draw(x, y, w, h):
                self._hbars(x, y, w, rows[:max(1, int(h // 26))], empty, lw=lw, vw=vw)
            return draw

        n_tasks = sum(t["total"] for t in d.get("tasks") or [])
        return [
            (f"Jam belajar per {unit}", "", hours),
            (f"Upload per {unit}", "", uploads),
            ("Jam ramai kelas", "", heat),
            ("Murid aktif per kategori", f"{n_cat} murid", categories),
            ("Pendaftar trial", d["period_label"], conv),
            (f"Pendaftar per {(su.get('series') or {}).get('unit', unit)}", "", signups),
            ("Tahu dari mana", "", sources),
            ("Rata-rata per hari", "jam belajar murid", weekday),
            ("Survey murid", f"{ss.get('count', 0)} jawaban", survey_donut),
            ("Survey murid", "pilihan terbanyak", survey_bars),
            ("Laporan guru", f"{n_tasks} tugas bulan ini", tasks),
            ("Murid per kursus", "", courses),
            ("Perlu diperhatikan", f"{len(attention)} murid",
             people(attention, "Semua murid aktif.", "at")),
            ("Paling rajin", d["period_label"], people(top, "Belum ada data.", "tp")),
            ("Kehadiran per jadwal", "",
             hbars(d.get("schedule", []), "Belum ada jadwal yang berjalan.", 140, 100)),
            ("Badge terbanyak", "", hbars(d.get("badges", []), "Belum ada badge.", 150, 64)),
        ]

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
        # lebar tetap: muncul / hilangnya teks tidak menggeser tombol lain
        self.status = tk.Label(bar, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 9),
                               width=14, anchor="w")
        self.status.pack(side="left", padx=(14, 0))
        self._paint()

        self.board = AnalyticsBoard(self, on_open=on_open)
        self.board.pack(fill="x")
        self._bar = bar
        self._sf = self._scroll_frame()
        self._fit_job = None
        if self._sf is not None:
            self._sf.canvas.bind("<Configure>", self._on_view, add="+")
        self.load()

    def _scroll_frame(self):
        from elearning.ui.widgets import ScrollFrame
        w = self.master
        while w is not None and not isinstance(w, ScrollFrame):
            w = getattr(w, "master", None)
        return w

    def _fit_height(self):
        """Tinggi area gulir dikurangi bar filter: kisi kartu pas satu layar (tanpa gulir)."""
        if self._sf is None:
            return 0
        self.update_idletasks()
        return max(0, self._sf.canvas.winfo_height() - self._bar.winfo_reqheight() - 14 - 6)

    def _on_view(self, _e=None):
        if self._fit_job is not None:
            self.after_cancel(self._fit_job)
        self._fit_job = self.after(80, self._apply_fit)

    def _apply_fit(self):
        self._fit_job = None
        h = self._fit_height()
        if h != self.board.fit_h:
            self.board.fit_h = h
            self.board.redraw()

    def _paint(self):
        groups = ((self._pbtns, self.state.get("period", "30d")),)
        for btns, current in groups:
            for k, b in btns.items():
                on = k == current
                b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
                         activebackground=C.SEG_ON if on else C.CARD_HOVER,
                         activeforeground=C.TEXT)

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
            self.board.fit_h = self._fit_height()
            self.board.set_data(hit[1], "compact")
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
        self.board.fit_h = self._fit_height()
        self.board.set_data(box["data"], "compact")

    def destroy(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
        super().destroy()
