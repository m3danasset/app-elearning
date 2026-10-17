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
VIDEO_FPS = 12
REFRESH_MS = 60_000
CARD_ALPHA = 0.93
CARD_H = 152
GAP = 18
PAD = 40
TOP_H = 132                 # sapaan + ringkasan
ICON = 38
BLUE = "#7cc8ff"
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
        self.rects = []                # (x0, y0, x1, y1) kartu (koordinat konten)
        self.hover = None
        self.scroll = 0
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
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._click)
        self.bind("<MouseWheel>", self._wheel)
        if self.video.ok():
            self.after(60, self._video_tick)
        self.load()

    # --- data ----------------------------------------------------------------------------
    def load(self):
        if self._loading or self._closed:
            return
        self._loading = True
        box = {}

        def work():
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
        self.items = box["items"]
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
        return TOP_H + rows * (CARD_H + GAP) + PAD

    def _layout(self):
        W, H = self._size
        if W < 100 or H < 100:
            return
        self.scroll = max(0, min(self.scroll, self._content_h() - H))
        cols = self._cols(W)
        cw = (W - 2 * PAD - (cols - 1) * GAP) / cols
        self.rects = []
        for i in range(len(self.items or [])):
            r, c = divmod(i, cols)
            x0 = PAD + c * (cw + GAP)
            y0 = TOP_H + r * (CARD_H + GAP)
            self.rects.append((x0, y0, x0 + cw, y0 + CARD_H))
        self.hover = None
        self.itemconfigure(self._hover_item, state="hidden")
        self._build_layer()
        self._draw_text()

    def _summary_rect(self):
        W = self._size[0]
        return (W - PAD - 300, 34, W - PAD, 34 + 76)

    def _build_layer(self):
        """Semua kartu (bayangan + badan + ikon + tombol) ke SATU gambar RGBA."""
        Image = photos.Image
        W, H = self._size
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dy = -self.scroll
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

        def place(img, x, y):
            x, y = int(round(x)), int(round(y))
            sx0, sy0 = max(0, -x), max(0, -y)
            sx1, sy1 = min(img.width, W - x), min(img.height, H - y)
            if sx1 > sx0 and sy1 > sy0:
                layer.alpha_composite(img.crop((sx0, sy0, sx1, sy1)), (x + sx0, y + sy0))

        # ringkasan kanan atas: cincin "beres"
        if self.items is not None and W >= 760:
            x0, y0, x1, y1 = self._summary_rect()
            w, h = int(x1 - x0), int(y1 - y0)
            sh, pad = _shadow(w, h, 16, 12, 80)
            place(sh, x0 - pad, y0 + dy - pad + 5)
            place(body(w, h, C.BORDER), x0, y0 + dy)
            done = sum(1 for it in self.items if it["level"] == "done")
            from elearning.ui import chart_art as CA
            ring = CA.donut(56, [(done, C.ON), (len(self.items) - done, C.SIDEBAR_ACTIVE)]
                            if self.items else [], C.CARD, 7, C.SIDEBAR_ACTIVE, gap_px=0)
            if ring is not None:
                place(ring.convert("RGBA"), x0 + 12, y0 + dy + 10)
        for i, (x0, y0, x1, y1) in enumerate(self.rects):
            if y1 + dy < -40 or y0 + dy > H + 40:
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
        self._layer = layer
        self.video.layer = layer if self.video.ok() else None
        self._show_static()

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
        dy = -self.scroll
        name = (self.user or {}).get("name", "")
        self.create_text(PAD, 40 + dy, anchor="nw", tags="txt", font=self.f["h1"], fill=C.TEXT,
                         text=f"{D.greeting()}, {name}")
        if self.items is None:
            sub = f"{D.today_text()}  ·  memuat…"
        else:
            todo = sum(1 for it in self.items if it["level"] in ("urgent", "todo"))
            sub = (f"{D.today_text()}  ·  " +
                   (f"{todo} hal perlu dikerjakan" if todo else "semua beres, kerja bagus!"))
        self.create_text(PAD, 84 + dy, anchor="nw", tags="txt", font=self.f["sub"],
                         fill=C.MUTED, text=sub)
        if self.items is None:
            return
        if W >= 760:
            x0, y0, x1, _y1 = self._summary_rect()
            done = sum(1 for it in self.items if it["level"] == "done")
            urgent = sum(1 for it in self.items if it["level"] == "urgent")
            self.create_text(x0 + 84, y0 + 16 + dy, anchor="nw", tags="txt",
                             font=self.f["big"], fill=C.TEXT,
                             text=f"{done}/{len(self.items)} beres")
            self.create_text(x0 + 84, y0 + 46 + dy, anchor="nw", tags="txt",
                             font=self.f["small"],
                             fill=C.ACCENT if urgent else C.MUTED,
                             text=f"{urgent} perlu segera ditindak" if urgent
                             else "tidak ada yang mendesak")
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
            self.create_text(tx, y0 + 22 + dy, anchor="nw", tags="txt", font=self.f["tag"],
                             fill=lv, text=it["tag"])
            if it.get("when"):
                tw = self.f["tag"].measure(it["tag"])
                self.create_text(tx + tw + 8, y0 + 22 + dy, anchor="nw", tags="txt",
                                 font=self.f["when"], fill=C.MUTED, text=f"·  {it['when']}")
            title = self._wrap(self.f["title"], it["title"], right - tx, 2)
            self.create_text(tx, y0 + 40 + dy, anchor="nw", tags="txt", font=self.f["title"],
                             fill=C.MUTED if done else C.TEXT, text="\n".join(title))
            by = y0 + 40 + len(title) * (self.f["title"].metrics("linespace")) + 6
            bw, bh = self._btn_size(it)
            body = self._wrap(self.f["body"], it["body"], x1 - 20 - tx,
                              2 if by + 2 * 16 < y1 - 16 - bh - 4 else 1)
            self.create_text(tx, by + dy, anchor="nw", tags="txt", font=self.f["body"],
                             fill=C.MUTED, text="\n".join(body))
            # label tombol
            bx = x1 - 18 - bw
            byy = y1 - 16 - bh
            fg = "white" if it["level"] in ("urgent", "todo") else C.TEXT
            self.create_text(bx + bw / 2, byy + bh / 2 + dy, tags="txt", font=self.f["btn"],
                             fill=fg, text=it["action"] + "  →")
            if done:
                self.create_text(tx, byy + bh / 2 + dy, anchor="w", tags="txt",
                                 font=self.f["btn"], fill=C.ON, text="✓  Beres")

    @staticmethod
    def _wrap(f, text, width, max_lines):
        from elearning.ui.course_dock import CourseDock
        return CourseDock._wrap(f, text, width, max_lines)

    # --- interaksi ---------------------------------------------------------------------------
    def _index_at(self, x, y):
        y += self.scroll
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
        self.coords(self._hover_item, int(round(x0)), int(round(y0 - self.scroll)))

    def _motion(self, e):
        self._set_hover(self._index_at(e.x, e.y))

    def _click(self, e):
        i = self._index_at(e.x, e.y)
        if i is not None and self.on_action is not None:
            self.on_action(self.items[i]["target"])

    def _wheel(self, e):
        H = self._size[1]
        top = max(0, self._content_h() - H)
        new = max(0, min(top, self.scroll - int(e.delta / 120) * 60))
        if new != self.scroll:
            self.scroll = new
            self.hover = None
            self.itemconfigure(self._hover_item, state="hidden")
            self._build_layer()
            self._draw_text()

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
        for j in (self._job, self._refresh_job, self._resize_job):
            if j is not None:
                try:
                    self.after_cancel(j)
                except tk.TclError:
                    pass
        self.video.stop()
        super().destroy()
