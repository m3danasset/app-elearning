"""Dashboard admin & guru: halaman pertama setelah login.

Gaya halaman utama murid (video latar redup, satu canvas), tapi isinya kartu NOTIFIKASI:
hal yang perlu dikerjakan (pendaftar, sertifikat, kelas berikutnya, laporan, murid tidak
aktif, ...). Tiap kartu: ikon bulat berwarna sesuai tingkat, label kategori, waktu, judul,
isi singkat, tombol aksi (klik kartu / tombol = buka menu terkait). Kanan atas: cincin
"sudah beres" + jumlah yang perlu ditindak.

Ringan: kartu digambar SEKALI ke satu lapisan RGBA; lapisan itu dicampur ke frame video di
thread video (bukan thread utama). Tanpa video: latar polos + lapisan, dicampur sekali.
Data dihitung di thread (dashboard.items), diperbarui tiap 60 detik.
"""

import os
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import dashboard as D
from elearning import photos
from elearning.ui import ui_icons as I

HOME_VIDEO_DIR = os.path.join(C.APP_DIR, "assets", "video", "home")
BLUE = "#7cc8ff"
VIDEO_FPS = 12
REFRESH_MS = 60_000
CARD_ALPHA = 0.93
CARD_H = 152
GAP = 18
PAD = 40
TOP_H = 300                 # widget 1 baris + sapaan (dihitung ulang: _hero_h)
WIDGET_Y, WIDGET_H, WIDGET_W, WIDGET_GAP = 28, 96, 270, 18
WIDGET_MIN_W = 150          # lebih sempit dari ini: widget per baris dikurangi
PER_ROW = 6                 # maks. 6 per baris, 2 baris (dashboard.MAX_WIDGETS)
PEN_D = 36                  # tombol pena (mode atur widget)
DEL_D = 22                  # tombol x (sembunyikan widget, mode atur)
CHIP_H = 34                 # widget tersembunyi di baki (mode atur)
HANDLE_D = 30               # tombol panah laci kartu (kecilkan / tampilkan semua)
DRAWER_MS = 520             # laci kartu naik / turun (ease-in-out, maks. 30 fps, berbasis waktu)
HERO_PT, HERO_OPEN_PT = 40, 24   # sapaan: besar (laci kecil) / mengecil ke atas (laci penuh)
SCROLL_MS = 200             # gulir kartu di laci penuh (halus, bukan loncat 80 px)
PEEK = 64                   # laci kecil: kartu baris ke-2 mengintip sekian px di bawah layar
PEEK_ALPHA = 0.5            # ... samar (paling terang), memudar ke 0 di tepi bawah layar
WIDGET_ACCENT = {"clock": BLUE, "done": "#3fb68b", "online": "#ea7600", "date": "#b39af0",
                 "signups": "#ea7600", "certs": "#3fb68b", "classes": BLUE,
                 "students": BLUE, "idle": "#e3c26f", "unscheduled": "#e3c26f",
                 "reports": "#b39af0", "work": BLUE}
FADE_TOP, FADE_BOTTOM = 26, 120     # kartu memudar di batas atas area gulir & di bawah layar
ICON = 38
INFO = "#8f8b82"


def _level_color(level):
    return {"urgent": C.ACCENT, "todo": BLUE, "info": INFO, "done": C.ON}.get(level, INFO)


def _mix(a, b, t):
    ca, cb = I._rgb(a), I._rgb(b)
    return "#%02x%02x%02x" % tuple(int(round(ca[i] + (cb[i] - ca[i]) * t)) for i in range(3))


_parts = {}                 # potongan kartu siap pakai (bayangan, badan, ikon) per ukuran


def _cached(key, make):
    img = _parts.get(key)
    if img is None:
        if len(_parts) > 120:
            _parts.clear()
        img = _parts[key] = make()
    return img


def _shadow(w, h, r, blur=14, alpha=110):
    """Bayangan lembut (perkecil-perbesar, tanpa ImageFilter). Kembalikan (RGBA, pad)."""
    return _cached(("shadow", w, h, r, blur, alpha), lambda: _make_shadow(w, h, r, blur, alpha))


def _make_shadow(w, h, r, blur, alpha):
    Image = photos.Image
    pad = blur * 2
    m = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    m.paste(I.round_mask(w, h, r).point(lambda v: v * alpha // 255), (pad, pad))
    small = m.resize((max(1, m.width // blur), max(1, m.height // blur)), Image.BILINEAR)
    a = small.resize(m.size, Image.BICUBIC)
    return Image.merge("RGBA", (Image.new("L", a.size, 0),) * 3 + (a,)), pad


class _Video:
    """Video latar redup + lapisan kartu dicampur di thread video."""

    def __init__(self, path):
        from elearning.ui import video_background as VB
        self.layer = None              # RGBA ukuran jendela (diganti utuh dari thread utama)
        self.raw = None                # frame terakhir tanpa kartu (untuk ganti lapisan cepat)
        self.player = None
        if not path or not VB.HAS_VIDEO:
            return
        Image = photos.Image
        bg = I._rgb(C.BG)
        op = getattr(C, "HOME_VIDEO_OPACITY", 0.22)
        holder = self

        class P(VB.VideoPlayer):
            def _prepare(self_, frame):
                img = VB.VideoPlayer._prepare(self_, frame)
                img = Image.blend(Image.new("RGB", img.size, bg), img, op)
                holder.raw = img
                layer = holder.layer
                if layer is not None and layer.size == img.size:
                    img = img.convert("RGBA")
                    img.alpha_composite(layer)
                    img = img.convert("RGB")
                img.info["layer"] = id(layer)       # frame lama (lapisan lama) tidak dipakai
                return img

        self.player = P(path, dim=1.0, max_fps=VIDEO_FPS)
        self.player.start()

    def ok(self):
        return self.player is not None and not self.player.failed

    def stop(self):
        if self.player is not None:
            self.player.stop()
            self.player = None


class DashboardView(tk.Canvas):
    def __init__(self, master, role, user, on_action):
        super().__init__(master, bg=C.BG, highlightthickness=0, bd=0)
        self.role, self.user, self.on_action = role, user, on_action
        self.items = None              # None = masih memuat
        self.info = {}                 # isi widget atas (online, kelas berikutnya)
        self.slots = D.load_slots((user or {}).get("id", ""), role)   # 12 slot (6 x 2)
        self.widgets = [w for w in self.slots if w]     # urut slot
        self._wrects = []              # kotak widget (urut sama dengan self.widgets)
        self.editing = False           # mode atur widget (tombol pena)
        self._edit_imgs = {}
        self._ate_click = False
        self._drag = None              # seret-lepas widget (mode atur)
        self._geo = None               # tata letak mode atur (slot, baki)
        self._clock_job = None
        self.rects = []                # (x0, y0, x1, y1) kartu (koordinat konten)
        self.hover = None
        self.scroll = 0
        self.shift = 0                 # ruang tambahan di atas (layar tinggi)
        self.card_scroll = 0           # gulir area kartu (px); widget & sapaan tidak ikut
        self.drawer_open = False       # laci kartu: kecil (1 baris di bawah) / penuh
        self._handle = None            # (cx, cy) tombol panah laci
        self._anim = None              # animasi laci / gulir yang sedang berjalan
        self._anim_job = None
        self._no_cards = False         # _build_layer tanpa kartu (kartu di pita animasi)
        self._all_rows = False         # _draw_cards_text: semua baris (juga di bawah layar)
        self._base_rgb = None          # latar + widget tanpa kartu (penutup tepi saat gulir)
        self._greet_fill = {}
        self._strip = None             # mode pita (laci penuh / animasi): posisi pita kartu
        self._peek_top = None          # laci kecil: y atas kartu baris ke-2 (mengintip)
        self._greet_items = ()         # (sapaan, baris tanggal)
        self._timer_on = False         # timer Windows 1 ms selama animasi
        self.cards_top = TOP_H
        self._size = (0, 0)
        self._layer = None
        self._photo = None
        self._img_item = self.create_image(0, 0, anchor="nw")
        self._hover_item = self.create_image(0, 0, anchor="nw", state="hidden")
        self._hover_photo = None
        self._closed = False
        self._job = self._refresh_job = self._resize_job = None
        self._loading = False
        self.f = {
            "h1": tkfont.Font(family=C.FONT, size=22, weight="bold"),
            "sub": tkfont.Font(family=C.FONT, size=11),
            "tag": tkfont.Font(family=C.FONT, size=8, weight="bold"),
            "when": tkfont.Font(family=C.FONT, size=8),
            "title": tkfont.Font(family=C.FONT, size=12, weight="bold"),
            "body": tkfont.Font(family=C.FONT, size=9),
            "btn": tkfont.Font(family=C.FONT, size=9, weight="bold"),
            "big": tkfont.Font(family=C.FONT, size=16, weight="bold"),
            "small": tkfont.Font(family=C.FONT, size=9),
            "hero": tkfont.Font(family=C.FONT, size=HERO_PT, weight="bold"),
            "hero_s": tkfont.Font(family=C.FONT, size=HERO_OPEN_PT, weight="bold"),
            "clock": tkfont.Font(family=C.FONT, size=28, weight="bold"),
        }
        # sapaan saat laci bergerak: SEMUA ukuran huruf dibuat sekali (mengubah ukuran satu
        # huruf tiap frame ~20 ms = patah-patah; berpindah ke huruf yang sudah ada ~0 ms)
        self._hero_fonts = {pt: tkfont.Font(family=C.FONT, size=pt, weight="bold")
                            for pt in range(HERO_OPEN_PT, HERO_PT + 1)}
        path = None
        try:
            from elearning.ui import video_background as VB
            path = VB.find_video(HOME_VIDEO_DIR)
        except Exception as exc:
            C.log(f"Dashboard: video latar: {exc!r}")
        self.video = _Video(path)
        self.bind("<Configure>", self._on_resize)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<B1-Motion>", self._drag_motion)
        self.bind("<ButtonRelease-1>", self._drag_end)
        self.bind("<Button-1>", self._click)
        self.bind("<MouseWheel>", self._wheel)
        if self.video.ok():
            self.after(60, self._video_tick)
        self.load()

    # --- data ----------------------------------------------------------------------------
    def load(self):
        if self._closed:
            return
        if self._loading:                # sedang menghitung: ulangi sekali setelah selesai
            self._again = True
            return
        self._loading = True
        box = {}

        def work():
            box["info"] = D.info(self.role, self.user, list(self.widgets))
            box["items"] = D.items(self.role, self.user)

        threading.Thread(target=work, daemon=True).start()
        self._poll(box)

    def _poll(self, box):
        if self._closed:
            return
        if "items" not in box:
            self._job = self.after(60, lambda: self._poll(box))
            return
        self._job = None
        self._loading = False
        if getattr(self, "_again", False):      # widget berubah saat menghitung: hitung lagi
            self._again = False
            self.after_idle(self.load)
        self.items = box["items"]
        self.info = box.get("info") or {}
        self._layout()
        self._refresh_job = self.after(REFRESH_MS, self.load)

    # --- tata letak -------------------------------------------------------------------------
    def _on_resize(self, e):
        if (e.width, e.height) == self._size:
            return
        self._size = (e.width, e.height)
        if self.video.player is not None:
            self.video.player.set_size(e.width, e.height)
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._layout()          # langsung (latar polos dulu): tidak ada area kosong / hitam

    def _cols(self, W):
        return 3 if W >= 1180 else 2 if W >= 720 else 1

    def _content_h(self):
        W = self._size[0]
        n = len(self.items or [])
        rows = -(-n // self._cols(W)) if n else 1
        return self._hero_h() + rows * (CARD_H + GAP) + PAD   # tanpa ruang tambahan (shift)

    def _widget_rows(self):
        """Mode biasa: widget per baris slot (baris 1 = slot 1-6, baris 2 = slot 7-12), slot
        kosong dilewati, tiap baris di tengah. Kembalikan ([jumlah per baris], lebar)."""
        W = self._size[0]
        rows = [n for n in (sum(1 for w in self.slots[:PER_ROW] if w),
                            sum(1 for w in self.slots[PER_ROW:] if w)) if n]
        room = W - 2 * PAD - 2 * (PEN_D + 16)            # sisakan ruang tombol pena
        widest = max(rows) if rows else 1
        ww = min(WIDGET_W, (room - (widest - 1) * WIDGET_GAP) / widest)
        return rows, ww

    def _edit_geo(self):
        """Mode atur: 12 kotak slot (6 x 2) + baki widget tersembunyi di bawahnya."""
        W = self._size[0]
        room = W - 2 * PAD - 2 * (PEN_D + 16)
        gw = min(WIDGET_W, (room - (PER_ROW - 1) * WIDGET_GAP) / PER_ROW)
        x = (W - (PER_ROW * gw + (PER_ROW - 1) * WIDGET_GAP)) / 2
        y = WIDGET_Y + self.shift * 0.35
        slots = []
        for k in range(D.MAX_WIDGETS):
            r, c = divmod(k, PER_ROW)
            x0 = x + c * (gw + WIDGET_GAP)
            y0 = y + r * (WIDGET_H + WIDGET_GAP)
            slots.append((x0, y0, x0 + gw, y0 + WIDGET_H))
        grid_bottom = slots[-1][3]
        free = [w for w in D.widget_choices(self.role) if w[0] not in self.slots]
        chips, line, cy = [], [], grid_bottom + 58
        maxw = W - 2 * PAD
        f = self.f["btn"]

        def flush(line, cy):
            tot = sum(w for _i, w in line) + 10 * max(0, len(line) - 1)
            cx = (W - tot) / 2
            for wid, w in line:
                chips.append((wid, (cx, cy, cx + w, cy + CHIP_H)))
                cx += w + 10
        for wid, label, _r, _t in free:
            w = f.measure(label) + 44
            if line and sum(x for _i, x in line) + 10 * len(line) + w > maxw:
                flush(line, cy)
                line, cy = [], cy + CHIP_H + 10
            line.append((wid, w))
        if line:
            flush(line, cy)
            cy += CHIP_H
        tray = (PAD, grid_bottom + 18, W - PAD, max(cy, grid_bottom + 58 + CHIP_H) + 16)
        return {"slots": slots, "chips": chips, "tray": tray, "w": gw}

    def _hero_h(self):
        if self.editing:
            g = self._geo or self._edit_geo()
            return g["tray"][3] + 30 - self.shift * 0.35
        rows, _ww = self._widget_rows()
        area = len(rows) * WIDGET_H + max(0, len(rows) - 1) * WIDGET_GAP if rows else 36
        return WIDGET_Y + area + 40 + 56 + 54

    def _layout(self):
        self._stop_anim()
        W, H = self._size
        if W < 100 or H < 100:
            return
        # layar tinggi & kartu muat: bagian atas (widget + sapaan) diberi ruang lega seperti
        # mockup (sapaan sekitar tengah, kartu di bawah); tidak muat -> rapat + bisa digulir
        self._geo = None
        free = H - self._content_h()
        self.shift = 0 if self.editing else max(0, min(free * 0.6, H * 0.22))
        if self.editing:
            self._geo = self._edit_geo()
        self.scroll = 0                     # widget + sapaan TERKUNCI; hanya kartu yang digulir
        cols = self._cols(W)
        cw = (W - 2 * PAD - (cols - 1) * GAP) / cols
        n = len(self.items or [])
        rows = -(-n // cols) if n else 0
        rowh = CARD_H + GAP
        self._handle = None
        self._peek_top = None
        if self.editing:
            top = self.cards_top = self._hero_h() + self.shift - 12
            first_y = top + 12
        else:
            self.shift = 0                   # widget di atas, sapaan di tengah layar
            hy = self._drawer_y(self.drawer_open)
            self._handle = (W / 2, hy) if rows > 1 or self.drawer_open else None
            top = self.cards_top = hy + 22
            first_y = top + 6
            if not self.drawer_open:
                self.card_scroll = 0
                if rows > 1:
                    self._peek_top = first_y + rowh
        # laci penuh / mode atur: bisa digulir sampai baris terakhir keluar dari area pudar
        self.card_scroll = max(0, min(self.card_scroll,
                                      rows * rowh + FADE_BOTTOM - (H - top)))
        self.rects = []
        for i in range(n):
            r, c = divmod(i, cols)
            x0 = PAD + c * (cw + GAP)
            if not self.editing and not self.drawer_open and r > 1:
                y0 = -10_000                 # laci kecil: baris 1 + baris 2 yang mengintip
            else:
                y0 = first_y + r * rowh - self.card_scroll       # koordinat layar
            self.rects.append((x0, y0, x0 + cw, y0 + CARD_H))
        self.hover = None
        self.itemconfigure(self._hover_item, state="hidden")
        if self._strip_ok():                 # laci penuh: kartu = pita yang digeser saat gulir
            self._prep_strip(first_y - self.card_scroll, top_cover=self.cards_top)
            return
        self._build_layer()
        self._draw_text()

    def _drawer_y(self, open_):
        """y tombol panah laci: penuh = tepat di bawah widget, kecil = 1 baris di bawah layar.
        Kartu pertama mulai di y + 28."""
        if open_:                            # di bawah sapaan yang mengecil ke atas
            gy, sub_y = self._greet_pos(True)
            return sub_y + self.f["sub"].metrics("linespace") + 30
        n = len(self.items or [])
        peek = PEEK if n > self._cols(self._size[0]) else 0     # ada baris ke-2
        return self._size[1] - PAD - CARD_H - 30 - peek

    def _greet_pos(self, open_):
        """(y sapaan, y baris tanggal). Laci penuh: tepat di bawah widget, huruf kecil;
        laci kecil: besar di tengah antara widget dan laci."""
        rects = self._widget_rects()
        wb = max(r[3] for r in rects) if rects else WIDGET_Y + 36
        if open_:
            gy = wb + 26
            return gy, gy + self.f["hero_s"].metrics("linespace") + 2
        bottom = self._drawer_y(False) - HANDLE_D
        gy = max(wb + 30, (wb + bottom) / 2 - 46)
        return gy, gy + 70

    def _max_scroll(self, top):
        cols = self._cols(self._size[0])
        n = len(self.items or [])
        rows = -(-n // cols) if n else 0
        return max(0, rows * (CARD_H + GAP) + FADE_BOTTOM - (self._size[1] - top))

    def _widget_rects(self):
        """Kotak widget terpasang (urut slot). Biasa: rapat & di tengah; atur: posisi slot."""
        if self.editing:
            g = self._geo or self._edit_geo()
            out = [g["slots"][k] for k, w in enumerate(self.slots) if w]
            self._wrects = out
            return out
        W = self._size[0]
        rows, ww = self._widget_rows()
        out = []
        y = WIDGET_Y + self.shift * 0.35
        for cnt in rows:
            x = (W - (cnt * ww + (cnt - 1) * WIDGET_GAP)) / 2
            for k in range(cnt):
                x0 = x + k * (ww + WIDGET_GAP)
                out.append((x0, y, x0 + ww, y + WIDGET_H))
            y += WIDGET_H + WIDGET_GAP
        self._wrects = out
        return out

    def _pen_pos(self):
        W = self._size[0]
        y = WIDGET_Y + self.shift * 0.35 + PEN_D / 2 + 2
        return (W - PAD - PEN_D / 2, y)

    def _build_layer(self):
        """Semua kartu (bayangan + badan + ikon + tombol) ke SATU gambar RGBA."""
        Image = photos.Image
        W, H = self._size
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dy = 0
        card = I._rgb(C.CARD)

        def body(w, h, border, alpha=CARD_ALPHA):
            return _cached(("body", w, h, border, C.CARD), lambda: make_body(w, h, border, alpha))

        def make_body(w, h, border, alpha):
            img = Image.new("RGBA", (w, h), I._rgb(border) + (0,))
            img.putalpha(I.round_mask(w, h, 16).point(lambda v: int(v * alpha)))
            inner = Image.new("RGBA", (w - 2, h - 2), card + (0,))
            inner.putalpha(I.round_mask(w - 2, h - 2, 15).point(lambda v: int(v * alpha)))
            img.alpha_composite(inner, (1, 1))
            return img

        tgt = [layer]

        def place(img, x, y):
            x, y = int(round(x)), int(round(y))
            sx0, sy0 = max(0, -x), max(0, -y)
            sx1, sy1 = min(img.width, W - x), min(img.height, H - y)
            if sx1 > sx0 and sy1 > sy0:
                tgt[0].alpha_composite(img.crop((sx0, sy0, sx1, sy1)), (x + sx0, y + sy0))

        if self.editing:                 # slot kosong: kotak samar bergaris tepi
            g = self._geo or self._edit_geo()
            for k, (x0, y0, x1, y1) in enumerate(g["slots"]):
                if self.slots[k]:
                    continue
                w, h = int(x1 - x0), int(y1 - y0)
                place(self._ghost(w, h), x0, y0)
            tx0, ty0, tx1, ty1 = g["tray"]
            place(self._ghost(int(tx1 - tx0), int(ty1 - ty0), 0.10), tx0, ty0)
        # widget atas (gaya widget: kartu kecil membulat, isi besar)
        for k, (x0, y0, x1, y1) in enumerate(self._widget_rects()):
            kind = self.widgets[k]
            w, h = int(x1 - x0), int(y1 - y0)
            sh, pad = _shadow(w, h, 18, 12, 90)
            place(sh, x0 - pad, y0 + dy - pad + 6)
            place(body(w, h, C.BORDER), x0, y0 + dy)
            place(self._tint(w, h, WIDGET_ACCENT.get(kind, BLUE), "todo"), x0, y0 + dy)
            if kind == "done" and self.items is not None:   # cincin "beres"
                done = sum(1 for it in self.items if it["level"] == "done")
                rs = 60 if w >= 220 else 44
                from elearning.ui import chart_art as CA
                ring = _cached(("ring", rs, done, len(self.items)), lambda: CA.donut(
                    rs, [(done, C.ON), (len(self.items) - done, C.BORDER)]
                    if self.items else [], None, 8 if rs > 50 else 6, C.BORDER, gap_px=0))
                if ring is not None:
                    place(ring.convert("RGBA"), x0 + 16, y0 + dy + (h - rs) / 2)
        cards = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        tgt[0] = cards                   # kartu: lapisan sendiri, lalu dipudarkan di tepi
        for i, (x0, y0, x1, y1) in enumerate(self.rects):
            if self._no_cards:           # animasi laci: kartu ada di pita sendiri (_card_strip)
                break
            if y1 + 40 < self.cards_top or y0 > H + 40:
                continue
            self._paint_card(place, i, x0, y0, x1, y1)
        a = cards.getchannel("A")
        cards.putalpha(Image.composite(a, Image.new("L", (W, H), 0), self._fade_mask(W, H)))
        layer.alpha_composite(cards)
        self._layer = layer
        self.video.layer = layer if self.video.ok() else None
        self._show_static()

    def _paint_card(self, place, i, x0, y0, x1, y1):
        """Satu kartu (bayangan + badan + cahaya + ikon + tombol) lewat place(img, x, y)."""
        Image = photos.Image
        card = I._rgb(C.CARD)

        def make_body(w, h, border, alpha=CARD_ALPHA):
            img = Image.new("RGBA", (w, h), I._rgb(border) + (0,))
            img.putalpha(I.round_mask(w, h, 16).point(lambda v: int(v * alpha)))
            inner = Image.new("RGBA", (w - 2, h - 2), card + (0,))
            inner.putalpha(I.round_mask(w - 2, h - 2, 15).point(lambda v: int(v * alpha)))
            img.alpha_composite(inner, (1, 1))
            return img

        it = self.items[i]
        lv = _level_color(it["level"])
        w, h = int(x1 - x0), int(y1 - y0)
        sh, pad = _shadow(w, h, 16, 14, 95)
        place(sh, x0 - pad, y0 - pad + 6)
        border = _mix(C.BORDER, lv, 0.35) if it["level"] == "urgent" else C.BORDER
        place(_cached(("body", w, h, border, C.CARD), lambda: make_body(w, h, border)), x0, y0)
        place(self._tint(w, h, lv, it["level"]), x0, y0)
        # ikon bulat (redup untuk info / selesai)
        disc = lv if it["level"] in ("urgent", "todo") else _mix(C.CARD, lv, 0.55)
        try:
            def make_icon(name=it["icon"], disc=disc):
                icon = I._render_icon(name, "#ffffff", C.CARD, ICON, disc=disc)
                icon = icon.convert("RGBA")
                icon.putalpha(I.round_mask(ICON, ICON, ICON / 2))
                return icon
            place(_cached(("icon", it["icon"], disc), make_icon), x0 + 20, y0 + 20)
        except Exception:
            pass
        # tombol aksi (kanan bawah); sorotan kursor = bingkai terpisah (_set_hover)
        bw, bh = self._btn_size(it)
        bx, by = x1 - 18 - bw, y1 - 16 - bh
        fill = lv if it["level"] in ("urgent", "todo") else _mix(C.CARD, "#ffffff", 0.08)
        btn = Image.new("RGBA", (bw, bh), I._rgb(fill) + (0,))
        btn.putalpha(I.round_mask(bw, bh, bh / 2))
        place(btn, bx, by)
        if it["level"] == "urgent":          # titik "belum dibaca"
            dot = Image.new("RGBA", (10, 10), I._rgb(lv) + (0,))
            dot.putalpha(I.round_mask(10, 10, 5))
            place(dot, x1 - 22, y0 + 16)

    def _draw_widgets(self, rects, dy):
        """Isi tiap widget (teks) sesuai jenisnya + tombol tambah / hapus (tersembunyi)."""
        from datetime import datetime
        inf = self.info or {}
        for k, (x0, y0, x1, y1) in enumerate(rects):
            kind = self.widgets[k]
            w = x1 - x0
            getattr(self, f"_w_{kind}", self._w_stat)(kind, x0, y0, x1, y1, w, inf)
        self._draw_edit()
        if self._clock_job is None:
            self._clock_job = self.after(15_000, self._tick_clock)

    def _t(self, x, y, text, font, fill=C.TEXT, anchor="nw", tags=("txt",)):
        return self.create_text(x, y, anchor=anchor, tags=tags, font=self.f[font], fill=fill,
                                text=text)

    def _w_clock(self, kind, x0, y0, x1, y1, w, inf):
        from datetime import datetime
        if w < 200:
            self._t(x0 + 16, y0 + 8, datetime.now().strftime("%H:%M"), "clock",
                    tags=("txt", "clock"))
            nxt = inf.get("next")
            self._t(x0 + 16, y0 + 52, "kelas berikutnya" if nxt else "tidak ada kelas",
                    "small", BLUE if nxt else C.MUTED)
            if nxt:
                self._t(x0 + 16, y0 + 70, f"{nxt['start']}  ·  {nxt['students']} murid",
                        "small", C.MUTED)
            return
        self._t(x0 + 18, y0 + 12, datetime.now().strftime("%H:%M"), "clock",
                tags=("txt", "clock"))
        nxt = inf.get("next")
        if nxt is None:
            line = "Tidak ada kelas lagi hari ini" if inf.get("classes") \
                else "Tidak ada kelas hari ini"
        elif nxt["now"]:
            line = f"Kelas berjalan  {nxt['start']}–{nxt['end']}"
        else:
            line = f"Kelas berikutnya  {nxt['start']}  ·  {nxt['students']} murid"
        self._t(x0 + 18, y0 + 64, self._fit(line, w - 34), "small", BLUE if nxt else C.MUTED)

    def _w_done(self, kind, x0, y0, x1, y1, w, inf):
        if self.items is None:
            return
        done = sum(1 for it in self.items if it["level"] == "done")
        urgent = sum(1 for it in self.items if it["level"] == "urgent")
        rs = 60 if w >= 220 else 44
        tx = x0 + 16 + rs + 14
        big = f"{done}/{len(self.items)}" + (" beres" if w >= 220 else "")
        self._t(tx, y0 + 26, self._fit(big, x1 - tx - 10, "big"), "big")
        if w < 220:
            self._t(tx, y0 + 56, "beres", "small", C.MUTED)
            return
        self._t(tx, y0 + 56, self._fit(f"{urgent} perlu ditindak" if urgent
                                       else "tidak ada yang mendesak", x1 - tx - 10),
                "small", C.ACCENT if urgent else C.MUTED)

    def _w_online(self, kind, x0, y0, x1, y1, w, inf):
        s, t = inf.get("online_s", 0), inf.get("online_t", 0)
        self._stat(x0, y0, x1, str(s + t), "sedang online",
                   f"{s} murid  ·  {t} guru" if self.role == "admin" else f"{s} murid",
                   C.ACCENT if s + t else C.MUTED, dot=bool(s + t))

    def _w_date(self, kind, x0, y0, x1, y1, w, inf):
        from datetime import date
        d = date.today()
        self._t(x0 + 18, y0 + 10, str(d.day), "clock")
        nw = self.f["clock"].measure(str(d.day))
        self._t(x0 + 18 + nw + 10, y0 + 18, D.DAYS[d.weekday()], "small", WIDGET_ACCENT["date"])
        self._t(x0 + 18, y0 + 64, f"{D.MONTHS[d.month - 1]} {d.year}", "small", C.MUTED)

    def _w_stat(self, kind, x0, y0, x1, y1, w, inf):
        spec = {
            "signups": ("signups", "pendaftar menunggu", "tinjau di menu Pendaftar"),
            "certs": ("certs", "sertifikat menunggu", "proses di menu Sertifikat"),
            "classes": ("classes", "kelas hari ini",
                        f"{inf.get('classes_students', 0)} murid terjadwal"),
            "students": ("active", "murid aktif", f"{inf.get('expired', 0)} expired"),
            "idle": ("idle", "murid tidak aktif", f"tidak login ≥ {D.INACTIVE_DAYS} hari"),
            "unscheduled": ("unscheduled", "tanpa jadwal", "murid aktif belum dijadwalkan"),
            "reports": ("reports", "laporan hari ini",
                        "laporan semua guru" if self.role == "admin" else
                        ("sudah ditulis" if inf.get("reports") else "belum ditulis")),
            "work": ("work", "karya baru", f"{D.NEW_WORK_DAYS} hari terakhir"),
        }.get(kind)
        if spec is None:
            return
        val = inf.get(spec[0])
        warn = kind in ("signups", "certs", "idle", "unscheduled") and val
        self._stat(x0, y0, x1, "–" if val is None else str(val), spec[1], spec[2],
                   WIDGET_ACCENT.get(kind) if warn else C.MUTED)

    def _stat(self, x0, y0, x1, value, label, sub, color, dot=False):
        if x1 - x0 < 200:                  # widget sempit: label di bawah angka, tanpa sub
            self._t(x0 + 16, y0 + 8, value, "clock")
            self._t(x0 + 16, y0 + 52, self._fit(("● " if dot else "") + label, x1 - x0 - 28),
                    "small", color)
            self._t(x0 + 16, y0 + 70, self._fit(sub, x1 - x0 - 28), "small", C.MUTED)
            return
        self._t(x0 + 18, y0 + 10, value, "clock")
        nw = self.f["clock"].measure(value)
        lx = x0 + 18 + nw + 10
        self._t(lx, y0 + 22, self._fit(("● " if dot else "") + label, x1 - lx - 12), "small",
                color)
        self._t(x0 + 18, y0 + 64, self._fit(sub, x1 - x0 - 34), "small", C.MUTED)

    # --- mode atur widget (tombol pena): slot, baki widget tersembunyi, seret-lepas ---------
    @staticmethod
    def _ghost(w, h, fill_alpha=0.18):
        """Kotak samar bergaris tepi (slot kosong / baki)."""
        def make():
            Image = photos.Image
            ring = I.round_mask(w, h, 16).copy()
            ring.paste(0, (1, 1), I.round_mask(w - 2, h - 2, 15))
            fill = I.round_mask(w - 2, h - 2, 15).point(lambda v: int(v * fill_alpha))
            a = Image.new("L", (w, h), 0)
            a.paste(fill, (1, 1))
            a = Image.composite(ring.point(lambda v: v * 150 // 255), a, ring)
            img = Image.new("RGBA", (w, h), I._rgb("#8f8b82") + (0,))
            img.putalpha(a)
            return img
        return _cached(("ghost", w, h, fill_alpha), make)

    def _edit_img(self, key, make):
        ph = self._edit_imgs.get(key)
        if ph is None:
            ph = self._edit_imgs[key] = photos.to_photoimage(make())
        return ph

    def _disc(self, d, fill, alpha=255, icon=None, icon_color="#ffffff"):
        def make():
            Image = photos.Image
            if icon:
                img = I._render_icon(icon, icon_color, fill, d, disc=fill).convert("RGBA")
            else:
                img = Image.new("RGBA", (d, d), I._rgb(fill) + (0,))
            img.putalpha(I.round_mask(d, d, d / 2).point(lambda v: v * alpha // 255))
            return img
        return self._edit_img(("disc", d, fill, alpha, icon, icon_color), make)

    def _chip_img(self, w, h, hov=False):
        def make():
            Image = photos.Image
            img = Image.new("RGBA", (w, h), I._rgb(C.BORDER if hov else C.CARD) + (0,))
            img.putalpha(I.round_mask(w, h, h / 2).point(lambda v: v * 240 // 255))
            return img
        return self._edit_img(("chip", w, h, hov), make)

    def _draw_edit(self):
        """Tombol pena (selalu) + isi mode atur: x di widget, + di slot kosong, baki."""
        self.delete("wedit")
        px, py = self._pen_pos()
        if self.editing:
            img = self._disc(PEN_D, C.ACCENT, 255, "check", "#ffffff")
        else:
            img = self._disc(PEN_D, "#2c2b28", 235, "pen", "#d8d5cc")
        self.create_image(px, py, image=img, tags=("txt", "wedit", "pen"))
        self.tag_bind("pen", "<Button-1>", self._toggle_edit)
        self.tag_bind("pen", "<Enter>", lambda e: self.config(cursor="hand2"))
        if not self.editing:
            return
        self.create_text(px, py + PEN_D / 2 + 6, anchor="n", tags=("txt", "wedit"),
                         font=self.f["small"], fill=C.ACCENT, text="Selesai")
        g = self._geo or self._edit_geo()
        for k, (x0, y0, x1, y1) in enumerate(g["slots"]):
            if self.slots[k]:
                tag = ("txt", "wedit", f"wdel{k}")
                cx, cy = x1 - 6, y0 + 6
                self.create_image(cx, cy, image=self._disc(DEL_D, "#3a3936", 245), tags=tag)
                self.create_text(cx, cy - 1, text="×", font=self.f["btn"], fill=C.TEXT,
                                 tags=tag)
                self.tag_bind(f"wdel{k}", "<Button-1>", lambda e, k=k: self._hide_slot(k))
            else:
                self.create_text((x0 + x1) / 2, (y0 + y1) / 2, tags=("txt", "wedit"),
                                 font=self.f["big"], fill="#6f6c64", text="+")
        tx0, ty0, tx1, ty1 = g["tray"]
        title = ("Widget tersembunyi  ·  seret ke slot kosong" if g["chips"]
                 else "Semua widget sudah terpasang")
        self.create_text((tx0 + tx1) / 2, ty0 + 14, tags=("txt", "wedit", "traytitle"),
                         font=self.f["small"], fill=C.MUTED, text=title)
        names = {w[0]: w[1] for w in D.WIDGETS}
        for wid, (x0, y0, x1, y1) in g["chips"]:
            tag = ("txt", "wedit", f"chip_{wid}")
            self.create_image(x0, y0, anchor="nw", tags=tag,
                              image=self._chip_img(int(x1 - x0), int(y1 - y0)))
            self.create_image(x0 + 18, (y0 + y1) / 2, tags=tag,
                              image=self._disc(9, WIDGET_ACCENT.get(wid, BLUE)))
            self.create_text(x0 + 30, (y0 + y1) / 2, anchor="w", tags=tag,
                             font=self.f["btn"], fill=C.TEXT, text=names.get(wid, wid))

    def _toggle_edit(self, _e=None):
        self._ate_click = True
        self.editing = not self.editing
        self._drag_cancel()
        self.card_scroll = 0
        self._layout()

    def _hit_slot(self, x, y):
        g = self._geo or self._edit_geo()
        for k, (x0, y0, x1, y1) in enumerate(g["slots"]):
            if x0 - WIDGET_GAP / 2 <= x < x1 + WIDGET_GAP / 2 and \
                    y0 - WIDGET_GAP / 2 <= y < y1 + WIDGET_GAP / 2:
                return k
        return None

    def _hit_chip(self, x, y):
        g = self._geo or self._edit_geo()
        for wid, (x0, y0, x1, y1) in g["chips"]:
            if x0 <= x < x1 and y0 <= y < y1:
                return wid
        return None

    def _in_tray(self, x, y):
        tx0, ty0, tx1, ty1 = (self._geo or self._edit_geo())["tray"]
        return tx0 <= x < tx1 and ty0 <= y < ty1

    def _press_edit(self, e):
        """Mode atur: tekan di widget / widget tersembunyi = mulai seret; di slot kosong =
        menu pilihan widget untuk slot itu."""
        k = self._hit_slot(e.x, e.y)
        if k is not None and self.slots[k]:
            self._drag = {"id": self.slots[k], "from": k, "x": e.x, "y": e.y, "moved": False}
            return
        wid = self._hit_chip(e.x, e.y)
        if wid is not None:
            self._drag = {"id": wid, "from": None, "x": e.x, "y": e.y, "moved": False}
            return
        if k is not None:
            self._slot_menu(k, e)

    def _drag_motion(self, e):
        d = self._drag
        if d is None:
            return
        if not d["moved"]:
            if abs(e.x - d["x"]) + abs(e.y - d["y"]) < 5:
                return
            d["moved"] = True
            self._drag_ghost(d, e)
        self.move("drag", e.x - d["x"], e.y - d["y"])
        d["x"], d["y"] = e.x, e.y
        # sorot tujuan: slot di bawah kursor / baki (lepas = sembunyikan)
        k = self._hit_slot(e.x, e.y)
        g = self._geo or self._edit_geo()
        if k is not None:
            x0, y0, x1, y1 = g["slots"][k]
            self.coords("dropring", x0, y0)
            self.itemconfigure("dropring", state="normal")
        else:
            self.itemconfigure("dropring", state="hidden")
        over = d["from"] is not None and self._in_tray(e.x, e.y)
        self.itemconfigure("traytitle", fill=C.ACCENT if over else C.MUTED,
                           text="Lepas untuk menyembunyikan widget" if over else
                           ("Widget tersembunyi  ·  seret ke slot kosong"
                            if g["chips"] else "Semua widget sudah terpasang"))

    def _drag_ghost(self, d, e):
        """Salinan widget yang mengikuti kursor (tembus pandang) + bingkai slot tujuan."""
        g = self._geo or self._edit_geo()
        w, h = int(g["w"]), WIDGET_H
        accent = WIDGET_ACCENT.get(d["id"], BLUE)

        def body():
            Image = photos.Image
            img = Image.new("RGBA", (w, h), I._rgb(accent) + (0,))
            img.putalpha(I.round_mask(w, h, 16).point(lambda v: v * 230 // 255))
            inner = Image.new("RGBA", (w - 4, h - 4), I._rgb(C.CARD) + (0,))
            inner.putalpha(I.round_mask(w - 4, h - 4, 14).point(lambda v: v * 225 // 255))
            img.alpha_composite(inner, (2, 2))
            return img

        def ring():
            Image = photos.Image
            a = I.round_mask(w, h, 16).copy()
            a.paste(0, (2, 2), I.round_mask(w - 4, h - 4, 14))
            img = Image.new("RGBA", (w, h), I._rgb(C.ACCENT) + (0,))
            img.putalpha(a)
            return img
        self.create_image(0, 0, anchor="nw", tags=("drag", "dropring"), state="hidden",
                          image=self._edit_img(("dropring", w, h), ring))
        self.dtag("dropring", "drag")
        x0, y0 = e.x - w / 2, e.y - h / 2
        self.create_image(x0, y0, anchor="nw", tags="drag",
                          image=self._edit_img(("dragbody", w, h, accent), body))
        name = D.WIDGET_BY_ID.get(d["id"], (d["id"], d["id"]))[1]
        self.create_text(e.x, e.y, tags="drag", font=self.f["btn"], fill=C.TEXT,
                         text=self._fit(name, w - 24, "btn"))
        if d["from"] is not None:           # widget asal diredupkan selama diseret
            self._drag_dim = True
        self.config(cursor="fleur")

    def _drag_end(self, e):
        d, self._drag = self._drag, None
        self.delete("drag")
        self.delete("dropring")
        self.config(cursor="")
        if d is None or not d["moved"]:
            return
        k = self._hit_slot(e.x, e.y)
        changed = False
        if k is not None:
            if d["from"] is None:                     # dari baki ke slot (yang lama tersembunyi)
                self.slots[k] = d["id"]
            elif k != d["from"]:                      # pindah / tukar posisi
                self.slots[d["from"]], self.slots[k] = self.slots[k], self.slots[d["from"]]
            changed = True
        elif d["from"] is not None and self._in_tray(e.x, e.y):
            self.slots[d["from"]] = None              # disembunyikan
            changed = True
        if changed:
            self._slots_changed(reload=d["from"] is None)
        else:
            self._layout()

    def _drag_cancel(self):
        self._drag = None
        self.delete("drag")
        self.delete("dropring")

    def _hide_slot(self, k):
        self._ate_click = True
        if self.slots[k]:
            self.slots[k] = None
            self._slots_changed()

    def _slot_menu(self, k, e):
        free = [w for w in D.widget_choices(self.role) if w[0] not in self.slots]
        m = tk.Menu(self, tearoff=0, font=(C.FONT, 10), bg=C.CARD, fg=C.TEXT,
                    activebackground=C.ACCENT, activeforeground="white", bd=0)
        for wid, label, _roles, _t in free:
            m.add_command(label=f"  {label}", command=lambda i=wid: self._put(k, i))
        if not free:
            m.add_command(label="  Semua widget sudah terpasang", state="disabled")
        m.add_separator()
        m.add_command(label="  Kembalikan ke bawaan", command=self._reset_widgets)
        m.tk_popup(e.x_root, e.y_root)

    def _put(self, k, wid):
        self.slots[k] = wid
        self._slots_changed(reload=True)

    def _reset_widgets(self):
        ok = {w[0] for w in D.widget_choices(self.role)}
        self.slots = [None] * D.MAX_WIDGETS
        for n, wid in enumerate(w for w in D.DEFAULT_WIDGETS if w in ok):
            self.slots[n] = wid
        self._slots_changed(reload=True)

    def _slots_changed(self, reload=False):
        self.widgets = [w for w in self.slots if w]
        try:
            D.save_slots((self.user or {}).get("id", ""), self.slots)
        except OSError as exc:
            C.log(f"Dashboard: widget tidak tersimpan: {exc!r}")
        self._layout()
        if reload:                 # widget baru butuh angka baru (dihitung di thread)
            self.load()

    def _tick_clock(self):
        """Jam widget diperbarui tiap 15 detik (hanya teks, sangat ringan)."""
        from datetime import datetime
        self._clock_job = None
        if self._closed:
            return
        self.itemconfigure("clock", text=datetime.now().strftime("%H:%M"))
        self._clock_job = self.after(15_000, self._tick_clock)

    def _fit(self, text, width, font="small"):
        f = self.f[font]
        if f.measure(text) <= width:
            return text
        while text and f.measure(text + "…") > width:
            text = text[:-1]
        return text.rstrip() + "…"

    @staticmethod
    def _tint(w, h, color, level):
        """Cahaya lembut warna tingkat dari kiri-atas kartu (gaya notifikasi), memudar ke
        kanan. Urgent / todo lebih terang; info / selesai samar."""
        strength = {"urgent": 0.20, "todo": 0.14}.get(level, 0.06)

        def make():
            Image = photos.Image
            g = Image.linear_gradient("L").rotate(-90).resize((w, h))     # kiri 255 -> kanan 0
            v = Image.linear_gradient("L").resize((w, h))                  # atas 0 -> bawah 255
            a = Image.composite(g, Image.new("L", (w, h), 0),
                                v.point(lambda x: 255 - x // 2))           # atas lebih terang
            a = a.point(lambda x: int((x / 255.0) ** 1.6 * 255 * strength))
            m = I.round_mask(w - 2, h - 2, 15)
            mask = Image.new("L", (w, h), 0)
            mask.paste(m, (1, 1))
            a = Image.composite(a, Image.new("L", (w, h), 0), mask)   # = a x mask
            img = Image.new("RGBA", (w, h), I._rgb(color) + (0,))
            img.putalpha(a)
            return img
        return _cached(("tint", w, h, color, strength), make)

    def _fade(self, y):
        """0..1: kartu di y terlihat sepenuhnya (1) / memudar / hilang (0)."""
        H = self._size[1]
        t0 = self.cards_top
        if y < t0 or y > H:
            return 0.0
        if self.editing:
            return max(0.0, min(1.0, (y - t0) / FADE_TOP, (H - y) / FADE_BOTTOM))
        if self.drawer_open:                 # laci penuh: potong tegas di atas, pudar di bawah
            return max(0.0, min(1.0, (H - y) / FADE_BOTTOM))
        pk = self._peek_top                  # laci kecil: baris ke-2 samar, memudar ke bawah
        if pk is None or y < pk:
            return 1.0
        return PEEK_ALPHA * max(0.0, (H - y) / max(1.0, H - pk))

    def _fade_mask(self, W, H):
        t0 = int(self.cards_top)

        def make():
            Image = photos.Image
            col = Image.new("L", (1, H))
            col.putdata([int(255 * self._fade(y + 0.5)) for y in range(H)])
            return col.resize((W, H))
        return _cached(("fade", W, H, t0, self.drawer_open, self.editing, self._peek_top),
                       make)

    def _btn_size(self, it):
        text = it["action"] + "  →"
        return int(self.f["btn"].measure(text) + 30), 30

    def _show_static(self):
        """Frame video terakhir (atau latar polos) + lapisan, langsung di thread utama:
        tidak menunggu frame video berikutnya dan latar tidak berkedip."""
        Image = photos.Image
        W, H = self._size
        raw = self.video.raw if self.video.ok() else None
        if raw is not None:      # ukuran baru (sidebar dilipat / dibuka): frame lama proporsional
            if raw.size != (W, H):
                from elearning.ui.course_dock import cover_resize
                raw = cover_resize(raw, (W, H))
            base = raw.convert("RGBA")
        else:
            base = Image.new("RGBA", (W, H), I._rgb(C.BG) + (255,))
        if self._layer is not None:
            base.alpha_composite(self._layer)
        rgb = base.convert("RGB")
        if self._no_cards:
            self._base_rgb = rgb
        self._photo = photos.to_photoimage(rgb)
        self.itemconfigure(self._img_item, image=self._photo)

    def _draw_text(self):
        self.delete("txt")
        W, H = self._size
        dy = 0                              # widget & sapaan terkunci (tidak ikut gulir)
        name = (self.user or {}).get("name", "")
        rects = self._widget_rects()
        gy = (max(r[3] for r in rects) + 40) if rects else WIDGET_Y + self.shift * 0.35 + 76
        if self.editing:
            self._draw_widgets(rects, dy)
            if self.items is not None:
                self._draw_cards_text(W, H)
                self._fade_text()
            return
        self._draw_handle()
        if self.drawer_open:                 # laci penuh: sapaan kecil di bawah widget
            self._draw_greeting(True)
            self._draw_widgets(rects, dy)
            if self.items is not None:
                self._draw_cards_text(W, H)
                self._fade_text()
            return
        self._draw_greeting(False)
        self._draw_widgets(rects, dy)
        if self.items is None:
            return
        self._draw_cards_text(W, H)
        self._fade_text()

    def _draw_greeting(self, open_=False):
        """Sapaan + baris tanggal. Laci kecil: besar di tengah; laci penuh: kecil di atas."""
        W = self._size[0]
        name = (self.user or {}).get("name", "")
        gy, sub_y = self._greet_pos(open_)
        if self.items is None:
            sub = f"{D.today_text()}  ·  memuat…"
        else:
            todo = sum(1 for it in self.items if it["level"] in ("urgent", "todo"))
            sub = (f"{D.today_text()}  ·  " +
                   (f"{todo} hal perlu dikerjakan" if todo else "semua beres, kerja bagus!"))
        hero = self.create_text(W / 2, gy, anchor="n", tags=("txt", "greet"),
                                font=self.f["hero_s" if open_ else "hero"], fill=C.TEXT,
                                text=f"{D.greeting()}, {name}")
        line = self.create_text(W / 2, sub_y, anchor="n", tags=("txt", "greet"),
                                font=self.f["sub"], fill=C.MUTED, text=sub)
        self._greet_items = (hero, line)

    def _draw_handle(self):
        """Tombol panah minimalis di atas laci kartu + keterangan kecil."""
        self.delete("handle")
        if self._handle is None or self.items is None:
            return
        cx, cy = self._handle
        up = not self.drawer_open
        img = self._disc(HANDLE_D, "#2c2b28", 230, "chev_up" if up else "chev_down", "#d8d5cc")
        tag = ("txt", "handle")
        self.create_image(cx, cy, image=img, tags=tag)
        n = len(self.items)
        shown = min(n, self._cols(self._size[0]))
        label = f"Tampilkan semua ({n})" if up else "Kecilkan"
        self.create_text(cx + HANDLE_D / 2 + 10, cy, anchor="w", tags=tag,
                         font=self.f["small"], fill=C.MUTED, text=label)
        if up and n > shown:
            self.create_text(cx - HANDLE_D / 2 - 10, cy, anchor="e", tags=tag,
                             font=self.f["small"], fill=C.MUTED, text=f"{shown} dari {n}")
        self.tag_bind("handle", "<Button-1>", self._toggle_drawer)
        self.tag_bind("handle", "<Enter>", lambda e: self.config(cursor="hand2"))

    def _toggle_drawer(self, _e=None):
        self._ate_click = True
        if self._anim is not None and self._anim["kind"] == "drawer":
            return                           # sedang bergerak: tunggu sampai berhenti
        self._start_anim("drawer", not self.drawer_open, 0)

    # --- animasi laci & gulir ---------------------------------------------------------------
    # MODE PITA: kartu digambar SEKALI ke satu pita RGBA (item canvas "strip") + teksnya ("ct");
    # latar di belakangnya = lapisan TANPA kartu. Laci penuh SELALU mode pita, jadi gulir hanya
    # canvas.move (tanpa persiapan / gambar ulang). Laci naik / turun memakai pita yang sama.
    # Penutup tepi = potongan latar: potong tegas di bawah tombol laci, pudar di bawah layar.
    # Mode ringan: tanpa pita, tanpa animasi (langsung).
    def _strip_ok(self):
        W, H = self._size
        return (self.drawer_open and not self.editing and bool(self.items) and not C.lite()
                and W >= 100 and H >= 100)

    def _prep_strip(self, first, top_cover=None):
        """Masuk mode pita dengan baris kartu pertama di y = first."""
        W, H = self._size
        cols = self._cols(W)
        cw = (W - 2 * PAD - (cols - 1) * GAP) / cols
        n = len(self.items)
        first = int(round(first))
        self._no_cards = True                # 1) latar + widget TANPA kartu
        try:
            self._build_layer()
        finally:
            self._no_cards = False
        strip, pad = self._card_strip(cols, cw, n)      # 2) pita semua kartu
        self._strip_photo = photos.to_photoimage(strip)
        self.create_image(0, first - pad, anchor="nw", image=self._strip_photo,
                          tags=("anim", "strip"))
        rowh = CARD_H + GAP                  # 3) teks semua kartu, warna utuh
        self.rects = []
        for i in range(n):
            r, c = divmod(i, cols)
            x0 = PAD + c * (cw + GAP)
            y0 = first + r * rowh
            self.rects.append((x0, y0, x0 + cw, y0 + CARD_H))
        self._all_rows = True
        try:
            self._draw_text()
        finally:
            self._all_rows = False
        for item in self.find_withtag("ct"):        # juga yang tadi disembunyikan _fade_text
            base = self._ct_color.get(item)
            if base is not None:
                self.itemconfigure(item, state="normal", fill=base)
            else:
                self.itemconfigure(item, state="normal")
        self.addtag_withtag("anim", "ct")
        # 4) urutan: latar < sapaan < pita < bingkai sorot < teks kartu < penutup < widget
        self.tag_raise("strip")
        self.tag_raise(self._hover_item)
        self.tag_raise("ct")
        self._strip = {"cur": first, "first0": first, "rects0": list(self.rects)}
        self._edge_covers(top_cover)

    def _raise_top(self):
        """Widget, tombol laci & pena selalu di atas pita dan penutup."""
        for item in self.find_withtag("txt"):
            tags = self.gettags(item)
            if "ct" not in tags:
                self.addtag_withtag("wtop", item)
        self.tag_raise("wtop")

    def _card_strip(self, cols, cw, n):
        """Semua kartu (koordinat lokal, baris pertama di y = pad) ke satu gambar RGBA."""
        Image = photos.Image
        W = self._size[0]
        rows = -(-n // cols)
        pad = 40                            # ruang bayangan di atas / bawah
        strip = Image.new("RGBA", (W, rows * (CARD_H + GAP) + 2 * pad), (0, 0, 0, 0))

        def place(img, x, y):
            x, y = int(round(x)), int(round(y))
            sx0, sy0 = max(0, -x), max(0, -y)
            sx1, sy1 = min(img.width, strip.width - x), min(img.height, strip.height - y)
            if sx1 > sx0 and sy1 > sy0:
                strip.alpha_composite(img.crop((sx0, sy0, sx1, sy1)), (x + sx0, y + sy0))
        for i in range(n):
            r, c = divmod(i, cols)
            x0 = PAD + c * (cw + GAP)
            y0 = pad + r * (CARD_H + GAP)
            self._paint_card(place, i, x0, y0, x0 + cw, y0 + CARD_H)
        return strip, pad

    def _edge_covers(self, top_y=None):
        """Potongan latar (tanpa kartu) di atas pita: bagian atas padat sampai top_y (kartu
        terpotong tegas di bawah tombol laci; gambar RGB, ringan) + pudar di bawah layar."""
        self.delete("cover")
        self._cover_imgs = []
        base = self._base_rgb
        if base is not None:
            Image = photos.Image
            W, H = self._size
            parts = []
            if top_y:
                top_y = int(top_y)
                parts.append((photos.to_photoimage(base.crop((0, 0, W, top_y))), 0))
            y0 = H - FADE_BOTTOM
            band = base.crop((0, y0, W, H)).convert("RGBA")
            col = Image.new("L", (1, FADE_BOTTOM))
            col.putdata([int(255 * (1 - min(1.0, (H - y - 0.5) / FADE_BOTTOM)))
                         for y in range(y0, H)])
            band.putalpha(col.resize((W, FADE_BOTTOM)))
            parts.append((photos.to_photoimage(band), y0))
            for ph, y in parts:
                self._cover_imgs.append(ph)
                self.create_image(0, y, anchor="nw", image=ph, tags=("cover",))
            self.tag_raise("cover")
        self._raise_top()

    def _sync_rects(self):
        """Kotak kartu (untuk klik / sorot) ikut posisi pita sekarang."""
        st = self._strip
        if st is None:
            return
        d = st["cur"] - st["first0"]
        self.rects = [(x0, y0 + d, x1, y1 + d) for x0, y0, x1, y1 in st["rects0"]]

    def _start_anim(self, kind, to_open, to_scroll):
        """kind "drawer": laci naik (to_open) / turun; "scroll": gulir laci penuh ke to_scroll."""
        W, H = self._size
        if C.lite() or self.editing or not self.items or W < 100 or H < 100:
            self._stop_anim()
            self.drawer_open, self.card_scroll = to_open, to_scroll
            self._layout()
            return
        now = time.perf_counter()
        a = self._anim
        to_first = self._drawer_y(to_open) + 28 - to_scroll
        if kind == "scroll":
            if self._strip is None:          # (seharusnya tidak terjadi) susun ulang saja
                self.card_scroll = to_scroll
                self._layout()
                return
            if a is not None and a["kind"] == "scroll":     # gulir lagi: ganti tujuan
                a.update(y0=self._strip["cur"], y1=to_first, to_scroll=to_scroll, t0=now, k=0)
                return
            self._set_hover(None)
            self._set_timer(True)
            self._anim = {"kind": "scroll", "to_open": True, "to_scroll": to_scroll,
                          "y0": self._strip["cur"], "y1": to_first, "ms": SCROLL_MS,
                          "t0": now, "k": 0}
            self._anim_step()
            return
        if a is not None:
            return
        self._set_hover(None)
        from_hy = self._drawer_y(self.drawer_open)
        closing = self.drawer_open
        if closing and self._strip is not None:
            # laci turun: pita yang sama; kartu yang tergulir keluar dari bawah potongan atas
            from_first = self._strip["cur"]
        else:                                # laci naik dari susunan biasa (laci kecil)
            from_first = from_hy + 28 - self.card_scroll
            self._prep_strip(from_first)
        self._anim = {"kind": "drawer", "to_open": to_open, "to_scroll": to_scroll,
                      "y0": from_first, "y1": to_first, "h0": from_hy,
                      "h1": self._drawer_y(to_open), "hcur": int(round(from_hy)),
                      "g0": self._greet_pos(closing), "g1": self._greet_pos(to_open),
                      "pt0": HERO_OPEN_PT if closing else HERO_PT,
                      "pt1": HERO_PT if closing else HERO_OPEN_PT, "pt": None,
                      "ms": DRAWER_MS, "t0": time.perf_counter(), "k": 0}
        self._set_timer(True)
        self._anim_step()

    def _set_timer(self, on):
        """Timer Windows 1 ms selama animasi: tanpa ini after() dibulatkan ke ~15,6 ms dan jarak
        frame melompat 31 / 47 ms (terasa patah-patah). Dikembalikan saat animasi selesai."""
        if on == self._timer_on or sys.platform != "win32":
            return
        self._timer_on = on
        try:
            import ctypes
            winmm = ctypes.windll.winmm
            (winmm.timeBeginPeriod if on else winmm.timeEndPeriod)(1)
        except Exception as exc:
            C.log(f"Dashboard: timer 1 ms tidak bisa diatur: {exc!r}")

    def _anim_step(self):
        self._anim_job = None
        a, st = self._anim, self._strip
        if a is None or st is None or self._closed:
            return
        t_start = time.perf_counter()
        t = min(1.0, (t_start - a["t0"]) * 1000.0 / a["ms"])
        if a["kind"] == "drawer":             # ease-in-out: tidak ada lompatan besar di awal
            e = 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
        else:                                 # gulir: ease-out (langsung bereaksi)
            e = 1 - (1 - t) ** 3
        y = int(round(a["y0"] + (a["y1"] - a["y0"]) * e))
        if y != st["cur"]:
            self.move("anim", 0, y - st["cur"])
            st["cur"] = y
        if a["kind"] == "drawer":
            hy = int(round(a["h0"] + (a["h1"] - a["h0"]) * e))
            if hy != a["hcur"]:
                self.move("handle", 0, hy - a["hcur"])
                a["hcur"] = hy
            if self._greet_items:             # sapaan naik + mengecil (turun + membesar)
                pt = int(round(a["pt0"] + (a["pt1"] - a["pt0"]) * e))
                if pt != a["pt"]:
                    self.itemconfigure(self._greet_items[0], font=self._hero_fonts[pt])
                    a["pt"] = pt
                hero, line = self._greet_items
                (gy0, sy0), (gy1, sy1) = a["g0"], a["g1"]
                W2 = self._size[0] / 2
                self.coords(hero, W2, int(round(gy0 + (gy1 - gy0) * e)))
                self.coords(line, W2, int(round(sy0 + (sy1 - sy0) * e)))
        if t < 1.0:     # jadwal frame tetap dari jam mulai (gambar ulang Tk ikut terhitung)
            a["k"] = max(a["k"] + 1, int((t_start - a["t0"]) * 1000 / C.UI_FRAME_MS) + 1)
            due = a["t0"] + a["k"] * C.UI_FRAME_MS / 1000.0
            self._anim_job = self.after(max(1, int((due - time.perf_counter()) * 1000)),
                                        self._anim_step)
            return
        self._anim = None
        self._set_timer(False)
        self.drawer_open, self.card_scroll = a["to_open"], a["to_scroll"]
        if a["kind"] == "scroll":             # tetap mode pita: tidak ada gambar ulang
            self._sync_rects()
        else:                                 # laci: susunan akhir (penuh = pita baru)
            self._layout()
        try:
            x = self.winfo_pointerx() - self.winfo_rootx()
            y = self.winfo_pointery() - self.winfo_rooty()
            self._set_hover(self._index_at(x, y))
        except tk.TclError:
            pass

    def _stop_anim(self):
        """Keluar dari animasi & mode pita (ukuran berubah, data dimuat ulang, laci selesai):
        keadaan tujuan diterapkan, pita & penutup dihapus."""
        a, self._anim = self._anim, None
        if self._anim_job is not None:
            try:
                self.after_cancel(self._anim_job)
            except tk.TclError:
                pass
            self._anim_job = None
        if a is not None:
            self._set_timer(False)
            self.drawer_open, self.card_scroll = a["to_open"], a["to_scroll"]
        if self._strip is not None:
            self._strip = None
            self.delete("strip")
            self.delete("cover")
            self.dtag("anim", "anim")
            self.dtag("wtop", "wtop")
            self._strip_photo = None
            self._cover_imgs = []

    def _fade_text(self):
        """Teks kartu di tepi area gulir: warnanya dicampur ke latar (ikut memudar)."""
        for item in self.find_withtag("ct"):
            box = self.bbox(item)
            if not box:
                continue
            f = self._fade((box[1] + box[3]) / 2)
            if f < 0.06:
                self.itemconfigure(item, state="hidden")
                continue
            base = self._ct_color.get(item)
            if base is None:
                base = self.itemcget(item, "fill")
                if not base.startswith("#"):          # nama warna ("white") -> #rrggbb
                    r, g, b = self.winfo_rgb(base)
                    base = "#%02x%02x%02x" % (r >> 8, g >> 8, b >> 8)
                self._ct_color[item] = base
            self.itemconfigure(item, state="normal",
                               fill=base if f >= 0.99 else _mix(C.BG, base, f))

    def _draw_cards_text(self, W, H):
        self._ct_color = {}
        dy = 0
        if not self.items:
            self.create_text(PAD, TOP_H + dy, anchor="nw", tags="txt", font=self.f["sub"],
                             fill=C.MUTED, text="Belum ada yang bisa ditampilkan.")
            return
        for i, (x0, y0, x1, y1) in enumerate(self.rects):
            if not self._all_rows and (y1 + dy < -40 or y0 + dy > H + 40):
                continue
            it = self.items[i]
            lv = _level_color(it["level"])
            tx = x0 + 20 + ICON + 14
            right = x1 - 20 - (16 if it["level"] == "urgent" else 0)
            done = it["level"] == "done"
            self.create_text(tx, y0 + 22 + dy, anchor="nw", tags=("txt", "ct"), font=self.f["tag"],
                             fill=lv, text=it["tag"])
            if it.get("when"):
                tw = self.f["tag"].measure(it["tag"])
                self.create_text(tx + tw + 8, y0 + 22 + dy, anchor="nw", tags=("txt", "ct"),
                                 font=self.f["when"], fill=C.MUTED, text=f"·  {it['when']}")
            title = self._wrap(self.f["title"], it["title"], right - tx, 2)
            self.create_text(tx, y0 + 40 + dy, anchor="nw", tags=("txt", "ct"), font=self.f["title"],
                             fill=C.MUTED if done else C.TEXT, text="\n".join(title))
            by = y0 + 40 + len(title) * (self.f["title"].metrics("linespace")) + 6
            bw, bh = self._btn_size(it)
            body = self._wrap(self.f["body"], it["body"], x1 - 20 - tx,
                              2 if by + 2 * 16 < y1 - 16 - bh - 4 else 1)
            self.create_text(tx, by + dy, anchor="nw", tags=("txt", "ct"), font=self.f["body"],
                             fill=C.MUTED, text="\n".join(body))
            # label tombol
            bx = x1 - 18 - bw
            byy = y1 - 16 - bh
            fg = "white" if it["level"] in ("urgent", "todo") else C.TEXT
            self.create_text(bx + bw / 2, byy + bh / 2 + dy, tags=("txt", "ct"), font=self.f["btn"],
                             fill=fg, text=it["action"] + "  →")
            if done:
                self.create_text(tx, byy + bh / 2 + dy, anchor="w", tags=("txt", "ct"),
                                 font=self.f["btn"], fill=C.ON, text="✓  Beres")

    @staticmethod
    def _wrap(f, text, width, max_lines):
        from elearning.ui.course_dock import CourseDock
        return CourseDock._wrap(f, text, width, max_lines)

    # --- interaksi ---------------------------------------------------------------------------
    def _in_peek(self, y):
        return (not self.drawer_open and not self.editing and self._peek_top is not None
                and y >= self._peek_top)

    def _index_at(self, x, y):
        if self._in_peek(y) or self._fade(y) < 0.5:          # di atas batas / di area pudar bawah: tidak aktif
            return None
        for i, (x0, y0, x1, y1) in enumerate(self.rects):
            if x0 <= x < x1 and y0 <= y < y1:
                return i
        return None

    def _set_hover(self, i):
        """Kursor di atas kartu: bingkai warna tingkat (gambar kecil siap pakai) di atas kartu.
        Lapisan kartu TIDAK digambar ulang, jadi ringan (< 2 ms)."""
        if i == self.hover:
            return
        self.hover = i
        self.config(cursor="hand2" if i is not None else "")
        if i is None or i >= len(self.rects):
            self.itemconfigure(self._hover_item, state="hidden")
            return
        x0, y0, x1, y1 = self.rects[i]
        w, h = int(x1 - x0), int(y1 - y0)
        color = _level_color(self.items[i]["level"])

        def ring():
            Image = photos.Image
            a = I.round_mask(w, h, 16).copy()
            a.paste(0, (2, 2), I.round_mask(w - 4, h - 4, 14))
            img = Image.new("RGBA", (w, h), I._rgb(color) + (0,))
            img.putalpha(a)
            return photos.to_photoimage(img)
        self._hover_photo = _cached(("ring", w, h, color), ring)
        self.itemconfigure(self._hover_item, image=self._hover_photo, state="normal")
        if self._fade(y0) < 0.99 or self._fade(y1) < 0.99:   # bingkai tidak ikut memudar:
            self.itemconfigure(self._hover_item, state="hidden")   # hanya kartu yang utuh
        self.coords(self._hover_item, int(round(x0)), int(round(y0)))

    def _motion(self, e):
        if self._drag is not None or self._anim is not None:
            return
        self._set_hover(self._index_at(e.x, e.y))
        if self._in_peek(e.y):
            self.config(cursor="hand2")
        if any(x0 <= e.x < x1 and y0 <= e.y < y1 for x0, y0, x1, y1 in self._wrects):
            self.config(cursor="fleur" if self.editing else "hand2")
        elif self.editing and self._hit_chip(e.x, e.y) is not None:
            self.config(cursor="fleur")

    def _click(self, e):
        if self._ate_click:              # klik di tombol pena / x
            self._ate_click = False
            return
        if self._anim is not None:       # laci / kartu sedang bergerak
            return
        if self._in_peek(e.y):           # kartu baris ke-2 yang mengintip: buka laci
            self._toggle_drawer()
            self._ate_click = False
            return
        if self.editing:
            self._press_edit(e)
            return
        for k, (x0, y0, x1, y1) in enumerate(self._wrects):
            if x0 <= e.x < x1 and y0 <= e.y < y1:
                target = D.WIDGET_BY_ID.get(self.widgets[k], (None,) * 4)[3]
                if target and self.on_action is not None:
                    self.on_action(target)
                return
        i = self._index_at(e.x, e.y)
        if i is not None and self.on_action is not None:
            self.on_action(self.items[i]["target"])

    def _wheel(self, e):
        """Roda mouse: area kartu digulir atas-bawah (tanpa scrollbar); widget & sapaan diam.
        Kartu memudar di batas atas area dan di bawah layar."""
        a = self._anim
        if a is not None and a["kind"] == "drawer":
            return                           # laci sedang naik / turun
        scroll = a["to_scroll"] if a is not None else self.card_scroll
        if not self.editing and self._handle is not None:
            if not self.drawer_open and e.delta < 0:
                self._toggle_drawer()
                self._ate_click = False
                return
            if self.drawer_open and e.delta > 0 and scroll == 0:
                self._toggle_drawer()
                self._ate_click = False
                return
        if not self.editing and not self.drawer_open:
            return
        if not self.editing:                 # laci penuh: gulir halus
            new = max(0, min(scroll - int(e.delta / 120 * 80), self._max_scroll(self.cards_top)))
            if new != scroll:
                self._start_anim("scroll", True, new)
            return
        old = self.card_scroll
        self.card_scroll = max(0, old - int(e.delta / 120 * 80))
        self._layout()                  # dibatasi otomatis
        if self.card_scroll != old:
            self._motion(e)

    # --- video ------------------------------------------------------------------------------
    def _video_tick(self):
        if self._closed:
            return
        p = self.video.player
        if p is None:
            return
        if p.failed:
            C.log(f"Dashboard: video latar gagal: {p.error}")
            self.video.stop()
            self._show_static()
            return
        try:
            iconic = self.winfo_toplevel().state() == "iconic"
        except tk.TclError:
            return
        img = None if iconic else p.get_latest()
        if img is not None and img.size == self._size                 and img.info.get("layer") == id(self._layer):
            self._photo = photos.to_photoimage(img)
            self.itemconfigure(self._img_item, image=self._photo)
        self.after(1000 // VIDEO_FPS, self._video_tick)

    def destroy(self):
        self._closed = True
        self._set_timer(False)
        for j in (self._job, self._refresh_job, self._resize_job, self._clock_job,
                  self._anim_job):
            if j is not None:
                try:
                    self.after_cancel(j)
                except tk.TclError:
                    pass
        self.video.stop()
        super().destroy()
