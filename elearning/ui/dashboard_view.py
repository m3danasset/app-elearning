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
import threading
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
ADD_D = 34                  # tombol + (tambah widget)
DEL_D = 22                  # tombol x (hapus widget)
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
        self.widgets = D.load_widgets((user or {}).get("id", ""), role)
        self._wrects = []              # kotak widget (urut sama dengan self.widgets)
        self._edit = False             # tombol tambah / hapus widget sedang tampil
        self._edit_imgs = {}
        self._ate_click = False
        self._clock_job = None
        self.rects = []                # (x0, y0, x1, y1) kartu (koordinat konten)
        self.hover = None
        self.scroll = 0
        self.shift = 0                 # ruang tambahan di atas (layar tinggi)
        self.card_scroll = 0           # gulir area kartu (px); widget & sapaan tidak ikut
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
            "hero": tkfont.Font(family=C.FONT, size=30, weight="bold"),
            "clock": tkfont.Font(family=C.FONT, size=28, weight="bold"),
        }
        path = None
        try:
            from elearning.ui import video_background as VB
            path = VB.find_video(HOME_VIDEO_DIR)
        except Exception as exc:
            C.log(f"Dashboard: video latar: {exc!r}")
        self.video = _Video(path)
        self.bind("<Configure>", self._on_resize)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: (self._set_hover(None), self._set_edit(False)))
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
        """Pembagian widget per baris: [jumlah baris 1, baris 2] dan lebar tiap widget."""
        W = self._size[0]
        n = len(self.widgets)
        room = W - 2 * PAD - ADD_D - 16                     # sisakan ruang tombol +
        fit = max(1, int((room + WIDGET_GAP) // (WIDGET_MIN_W + WIDGET_GAP)))
        per = max(1, min(PER_ROW, max(fit, -(-n // 2))))   # semua widget muat di 2 baris
        rows = [min(per, n - i) for i in range(0, n, per)][:2] if n else []
        widest = max(rows) if rows else 1
        ww = min(WIDGET_W, (room - (widest - 1) * WIDGET_GAP) / widest)
        return rows, ww

    def _hero_h(self):
        rows, _ww = self._widget_rows()
        area = len(rows) * WIDGET_H + max(0, len(rows) - 1) * WIDGET_GAP if rows else 36
        return WIDGET_Y + area + 40 + 56 + 54

    def _layout(self):
        W, H = self._size
        if W < 100 or H < 100:
            return
        # layar tinggi & kartu muat: bagian atas (widget + sapaan) diberi ruang lega seperti
        # mockup (sapaan sekitar tengah, kartu di bawah); tidak muat -> rapat + bisa digulir
        free = H - self._content_h()
        self.shift = max(0, min(free * 0.6, H * 0.22))
        self.scroll = 0                     # widget + sapaan TERKUNCI; hanya kartu yang digulir
        cols = self._cols(W)
        cw = (W - 2 * PAD - (cols - 1) * GAP) / cols
        n = len(self.items or [])
        rows = -(-n // cols) if n else 0
        rowh = CARD_H + GAP
        top = self.cards_top = self._hero_h() + self.shift - 12
        # bisa digulir sampai baris terakhir keluar dari area pudar bawah
        self.card_scroll = max(0, min(self.card_scroll,
                                      rows * rowh + FADE_BOTTOM - (H - top)))
        self.rects = []
        for i in range(n):
            r, c = divmod(i, cols)
            x0 = PAD + c * (cw + GAP)
            y0 = top + 12 + r * rowh - self.card_scroll       # koordinat layar
            self.rects.append((x0, y0, x0 + cw, y0 + CARD_H))
        self.hover = None
        self.itemconfigure(self._hover_item, state="hidden")
        self._build_layer()
        self._draw_text()

    def _widget_rects(self):
        """Kotak widget: maks. 6 per baris, 2 baris, tiap baris di tengah."""
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

    def _add_pos(self):
        """Tombol + : di kanan widget terakhir (atau tengah kalau belum ada widget)."""
        if len(self.widgets) >= D.MAX_WIDGETS:
            return None
        if not self._wrects:
            return (self._size[0] / 2, WIDGET_Y + self.shift * 0.35 + 18)
        x0, y0, x1, y1 = self._wrects[-1]
        return (x1 + 16 + ADD_D / 2, (y0 + y1) / 2)

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
            if y1 + 40 < self.cards_top or y0 > H + 40:
                continue
            it = self.items[i]
            lv = _level_color(it["level"])
            hov = False                  # sorotan kursor: gambar bingkai terpisah (_set_hover)
            w, h = int(x1 - x0), int(y1 - y0)
            sh, pad = _shadow(w, h, 16, 14, 95)
            place(sh, x0 - pad, y0 + dy - pad + 6)
            border = _mix(C.BORDER, lv, 0.35) if it["level"] == "urgent" else C.BORDER
            place(body(w, h, border), x0, y0 + dy)
            place(self._tint(w, h, lv, it["level"]), x0, y0 + dy)
            # ikon bulat (redup untuk info / selesai)
            disc = lv if it["level"] in ("urgent", "todo") else _mix(C.CARD, lv, 0.55)
            try:
                def make_icon(name=it["icon"], disc=disc):
                    icon = I._render_icon(name, "#ffffff", C.CARD, ICON, disc=disc)
                    icon = icon.convert("RGBA")
                    icon.putalpha(I.round_mask(ICON, ICON, ICON / 2))
                    return icon
                place(_cached(("icon", it["icon"], disc), make_icon), x0 + 20, y0 + dy + 20)
            except Exception:
                pass
            # tombol aksi (kanan bawah)
            bw, bh = self._btn_size(it)
            bx, by = x1 - 18 - bw, y1 - 16 - bh
            if it["level"] in ("urgent", "todo"):
                fill = _mix(lv, "#ffffff", 0.12) if hov else lv
            else:
                fill = _mix(C.CARD, "#ffffff", 0.14 if hov else 0.08)
            btn = Image.new("RGBA", (bw, bh), I._rgb(fill) + (0,))
            btn.putalpha(I.round_mask(bw, bh, bh / 2))
            place(btn, bx, by + dy)
            if it["level"] == "urgent":          # titik "belum dibaca"
                dot = Image.new("RGBA", (10, 10), I._rgb(lv) + (0,))
                dot.putalpha(I.round_mask(10, 10, 5))
                place(dot, x1 - 22, y0 + dy + 16)
        a = cards.getchannel("A")
        cards.putalpha(Image.composite(a, Image.new("L", (W, H), 0), self._fade_mask(W, H)))
        layer.alpha_composite(cards)
        self._layer = layer
        self.video.layer = layer if self.video.ok() else None
        self._show_static()

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

    # --- tombol tambah / hapus widget (muncul saat kursor di area widget) --------------------
    def _edit_img(self, key, d, fill, alpha):
        ph = self._edit_imgs.get(key)
        if ph is None:
            Image = photos.Image
            img = Image.new("RGBA", (d, d), I._rgb(fill) + (0,))
            img.putalpha(I.round_mask(d, d, d / 2).point(lambda v: v * alpha // 255))
            ph = self._edit_imgs[key] = photos.to_photoimage(img)
        return ph

    def _draw_edit(self):
        self.delete("wedit")
        show = "normal" if (self._edit or not self.widgets) else "hidden"
        for k, (x0, y0, x1, y1) in enumerate(self._wrects):
            cx, cy = x1 - 6, y0 + 6
            tag = ("txt", "wedit", f"wdel{k}")
            self.create_image(cx, cy, image=self._edit_img("del", DEL_D, "#3a3936", 245),
                              tags=tag, state=show)
            self.create_text(cx, cy - 1, text="×", font=self.f["btn"], fill=C.TEXT, tags=tag,
                             state=show)
            self.tag_bind(f"wdel{k}", "<Button-1>", lambda e, k=k: self._remove_widget(k))
        pos = self._add_pos()
        if pos is not None:
            cx, cy = pos
            tag = ("txt", "wedit", "wadd")
            self.create_image(cx, cy, image=self._edit_img("add", ADD_D, C.ACCENT, 255),
                              tags=tag, state=show)
            self.create_text(cx, cy - 1, text="+", font=self.f["big"], fill="white", tags=tag,
                             state=show)
            self.tag_bind("wadd", "<Button-1>", self._add_menu)
        self.tag_bind("wedit", "<Enter>", lambda e: self.config(cursor="hand2"))

    def _set_edit(self, on):
        if on == self._edit:
            return
        self._edit = on
        if self.widgets:
            self.itemconfigure("wedit", state="normal" if on else "hidden")

    def _in_widget_area(self, x, y):
        pos = self._add_pos()
        boxes = list(self._wrects)
        if pos is not None:
            boxes.append((pos[0] - ADD_D, pos[1] - ADD_D, pos[0] + ADD_D, pos[1] + ADD_D))
        if not boxes:
            return False
        x0 = min(b[0] for b in boxes) - 24
        x1 = max(b[2] for b in boxes) + 24
        y0 = min(b[1] for b in boxes) - 24
        y1 = max(b[3] for b in boxes) + 16
        return x0 <= x <= x1 and y0 <= y <= y1

    def _remove_widget(self, k):
        self._ate_click = True
        if 0 <= k < len(self.widgets):
            del self.widgets[k]
            self._save_widgets()

    def _add_menu(self, e):
        self._ate_click = True
        have = set(self.widgets)
        m = tk.Menu(self, tearoff=0, font=(C.FONT, 10), bg=C.CARD, fg=C.TEXT,
                    activebackground=C.ACCENT, activeforeground="white", bd=0)
        free = [w for w in D.widget_choices(self.role) if w[0] not in have]
        for wid, label, _roles, _t in free:
            m.add_command(label=f"  {label}", command=lambda i=wid: self._add_widget(i))
        if not free:
            m.add_command(label="  Semua widget sudah dipasang", state="disabled")
        m.add_separator()
        m.add_command(label="  Kembalikan ke bawaan", command=self._reset_widgets)
        m.tk_popup(e.x_root, e.y_root)

    def _add_widget(self, wid):
        if wid not in self.widgets and len(self.widgets) < D.MAX_WIDGETS:
            self.widgets.append(wid)
            self._save_widgets(reload=True)

    def _reset_widgets(self):
        self.widgets = [i for i in D.DEFAULT_WIDGETS
                        if i in {w[0] for w in D.widget_choices(self.role)}]
        self._save_widgets(reload=True)

    def _save_widgets(self, reload=False):
        try:
            D.save_widgets((self.user or {}).get("id", ""), self.widgets)
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
        if y < t0:
            return 0.0
        return max(0.0, min(1.0, (y - t0) / FADE_TOP, (H - y) / FADE_BOTTOM))

    def _fade_mask(self, W, H):
        t0 = int(self.cards_top)

        def make():
            Image = photos.Image
            col = Image.new("L", (1, H))
            col.putdata([int(255 * self._fade(y + 0.5)) for y in range(H)])
            return col.resize((W, H))
        return _cached(("fade", W, H, t0), make)

    def _btn_size(self, it):
        text = it["action"] + "  →"
        return int(self.f["btn"].measure(text) + 30), 30

    def _show_static(self):
        """Frame video terakhir (atau latar polos) + lapisan, langsung di thread utama:
        tidak menunggu frame video berikutnya dan latar tidak berkedip."""
        Image = photos.Image
        W, H = self._size
        raw = self.video.raw if self.video.ok() else None
        if raw is not None and raw.size == (W, H):
            base = raw.convert("RGBA")
        else:
            base = Image.new("RGBA", (W, H), I._rgb(C.BG) + (255,))
        if self._layer is not None:
            base.alpha_composite(self._layer)
        self._photo = photos.to_photoimage(base.convert("RGB"))
        self.itemconfigure(self._img_item, image=self._photo)

    def _draw_text(self):
        self.delete("txt")
        W, H = self._size
        dy = 0                              # widget & sapaan terkunci (tidak ikut gulir)
        name = (self.user or {}).get("name", "")
        rects = self._widget_rects()
        gy = (max(r[3] for r in rects) + 40) if rects else WIDGET_Y + self.shift * 0.35 + 76
        self.create_text(W / 2, gy + dy, anchor="n", tags="txt", font=self.f["hero"],
                         fill=C.TEXT, text=f"{D.greeting()}, {name}")
        if self.items is None:
            sub = f"{D.today_text()}  ·  memuat…"
        else:
            todo = sum(1 for it in self.items if it["level"] in ("urgent", "todo"))
            sub = (f"{D.today_text()}  ·  " +
                   (f"{todo} hal perlu dikerjakan" if todo else "semua beres, kerja bagus!"))
        self.create_text(W / 2, gy + 56 + dy, anchor="n", tags="txt", font=self.f["sub"],
                         fill=C.MUTED, text=sub)
        self._draw_widgets(rects, dy)
        if self.items is None:
            return
        self._draw_cards_text(W, H)
        self._fade_text()

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
            if y1 + dy < -40 or y0 + dy > H + 40:
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
    def _index_at(self, x, y):
        if self._fade(y) < 0.5:          # di atas batas / di area pudar bawah: tidak aktif
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
        self._set_hover(self._index_at(e.x, e.y))
        self._set_edit(self._in_widget_area(e.x, e.y))
        if any(x0 <= e.x < x1 and y0 <= e.y < y1 for x0, y0, x1, y1 in self._wrects):
            self.config(cursor="hand2")

    def _click(self, e):
        if self._ate_click:              # klik di tombol tambah / hapus widget
            self._ate_click = False
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
        for j in (self._job, self._refresh_job, self._resize_job, self._clock_job):
            if j is not None:
                try:
                    self.after_cancel(j)
                except tk.TclError:
                    pass
        self.video.stop()
        super().destroy()
