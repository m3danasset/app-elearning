"""Halaman utama murid: deretan kartu kursus (1:1) di tengah, gaya Dock macOS.

- Kartu tersusun mendatar di tengah halaman. Kalau tidak muat: geser kiri/kanan dengan
  roda mouse, tombol panah di tepi, atau tombol panah keyboard (animasi halus).
- Kursor di atas kartu: kartu terangkat sedikit + garis tepi oranye (langsung, tanpa animasi).
- Latar: video dengan opacity rendah dari  assets\\video\\home\\  (opsional). Tanpa video,
  latar polos warna aplikasi.

Seluruh halaman digambar di SATU canvas: video + kartu digabung jadi satu gambar (kartu
sedikit transparan di atas video), teks di atasnya. Tidak ada widget bertumpuk, jadi tidak
ada potongan / blok hitam saat jendela berubah ukuran.
Video dibaca & digelapkan di thread terpisah dan dibatasi 12 fps supaya ringan.
"""

import os
import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import photos
from elearning.ui import ui_icons as I

HOME_VIDEO_DIR = os.path.join(C.APP_DIR, "assets", "video", "home")
VIDEO_OPACITY = getattr(C, "HOME_VIDEO_OPACITY", 0.22)   # 0 = tak terlihat, 1 = penuh
VIDEO_FPS = 12
CARD_ALPHA = 0.90          # kartu sedikit tembus pandang di atas video
GAP = 22
RADIUS = 18
LIFT = 6                   # kartu di bawah kursor naik sedikit (tanpa animasi: langsung, ringan)
SCROLL_MS = 220            # lama animasi geser kiri/kanan
FADE = 150                 # lebar memudar di tepi kiri & kanan (px)
ARROW_ZONE = 46            # area klik panah < > di tepi


def _rgb(c):
    return I._rgb(c)


class _BgVideo:
    """Video latar yang sudah dicampur dengan warna latar (opacity rendah), di thread."""

    def __init__(self, path):
        from elearning.ui import video_background as VB
        self.ok = bool(path) and VB.HAS_VIDEO
        self.player = None
        if not self.ok:
            return
        Image = photos.Image
        bg = _rgb(C.BG)
        op = VIDEO_OPACITY

        class P(VB.VideoPlayer):
            def _prepare(self_, frame):
                img = VB.VideoPlayer._prepare(self_, frame)
                solid = Image.new("RGB", img.size, bg)
                return Image.blend(solid, img, op)

        self.player = P(path, dim=1.0, max_fps=VIDEO_FPS)
        self.player.start()

    def set_size(self, w, h):
        if self.player is not None:
            self.player.set_size(w, h)

    def latest(self):
        return self.player.get_latest() if self.player is not None else None

    def failed(self):
        return self.player is not None and self.player.failed

    def stop(self):
        if self.player is not None:
            self.player.stop()
            self.player = None


class CourseDock(tk.Canvas):
    """Satu canvas: [gambar latar penuh] + [gambar pita kartu] + teks.

    Agar geser kiri/kanan halus (maks. 30 fps), tiap langkah animasi hanya:
      - menyusun ulang PITA kartu (setinggi kartu, bukan seluruh halaman),
      - menggeser teks yang sudah ada (canvas.move), tanpa membuat ulang,
      - mengganti warna teks hanya untuk kartu yang tingkat pudarnya berubah.
    Panah < > ikut digambar halus (anti-alias) ke dalam pita.
    """

    FRAME_MS = C.UI_FRAME_MS   # maks. 30 fps

    def __init__(self, master, courses, allowed, on_open, title, hello):
        super().__init__(master, bg=C.BG, highlightthickness=0, bd=0)
        self.courses = list(courses)
        self.allowed = set(allowed)
        self.on_open = on_open
        self.title_text, self.hello_text = title, hello
        self.empty_text = ""
        self.offset = 0.0           # indeks kartu pertama di jendela tengah (beranimasi)
        self.target = 0
        self.hover = None
        self.rects = []
        self._base = None           # latar penuh (video tercampur / polos), PIL RGB
        self._base_photo = self._band_photo = None
        self._base_item = self.create_image(0, 0, anchor="nw")
        self._band_item = self.create_image(0, 0, anchor="nw")
        self._anim = None
        self._size = (0, 0)
        self._s = 200
        self._cy = 0
        self._band = (0, 10)        # (y atas pita, tinggi pita)
        self._text_x = 0.0          # posisi awal baris saat teks dibuat (untuk canvas.move)
        self._items = []            # per kartu: [(id item, warna asli)]
        self._fades = []            # per kartu: tingkat pudar terakhir (dibulatkan)
        self._arrow_hover = None
        self._closed = False
        self.f = {
            "h1": tkfont.Font(family=C.FONT, size=20, weight="bold"),
            "hello": tkfont.Font(family=C.FONT, size=11),
            "group": tkfont.Font(family=C.FONT, size=8, weight="bold"),
            "title": tkfont.Font(family=C.FONT, size=15, weight="bold"),
            "desc": tkfont.Font(family=C.FONT, size=9),
            "foot": tkfont.Font(family=C.FONT, size=9, weight="bold"),
        }
        path = None
        try:
            from elearning.ui import video_background as VB
            path = VB.find_video(HOME_VIDEO_DIR)
        except Exception as exc:
            C.log(f"Video latar beranda: {exc!r}")
        self.video = _BgVideo(path)
        if path:
            C.log(f"Video latar beranda: {path}")
        self.bind("<Configure>", self._on_resize)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: (self._set_hover(None), self._set_arrow_hover(None)))
        self.bind("<Button-1>", self._click)
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Shift-MouseWheel>", self._wheel)
        self.bind("<Button-4>", lambda e: self.scroll_by(-1))
        self.bind("<Button-5>", lambda e: self.scroll_by(1))
        top = self.winfo_toplevel()
        top._course_dock = self
        if not getattr(top, "_dock_keys", False):     # dipasang sekali per jendela

            def key(d):
                dock = getattr(top, "_course_dock", None)
                if dock is not None and not dock._closed:
                    dock._key(d)
            top.bind("<Left>", lambda e: key(-1), add="+")
            top.bind("<Right>", lambda e: key(1), add="+")
            top._dock_keys = True
        if self.video.ok:
            self.after(60, self._video_tick)

    # --- data -------------------------------------------------------------------------------
    def set_courses(self, courses, empty_text=""):
        self.courses = list(courses)
        self.empty_text = empty_text
        self.hover = None
        self.offset = self.target = 0
        self._rebuild()

    # --- ukuran ---------------------------------------------------------------------------------
    def _on_resize(self, e):
        if (e.width, e.height) == self._size or e.width < 50 or e.height < 50:
            return
        self._size = (e.width, e.height)
        self.video.set_size(e.width, e.height)
        if self._base is not None and self.video.ok:
            self._base = self._base.resize(self._size)     # frame lama sampai frame baru tiba
        else:
            self._base = photos.Image.new("RGB", self._size, _rgb(C.BG))
        self.target = self._clamp(self.target)
        self.offset = float(self.target)
        self._set_base_photo()
        self._rebuild()

    def _card_size(self):
        w, h = self._size
        return int(max(150, min(220, h * 0.36, (w - 120) / 3.2)))

    MARGIN = 64

    def _visible(self):
        avail = self._size[0] - 2 * self.MARGIN
        return max(1, int((avail + GAP) // (self._s + GAP)))

    def _max_first(self):
        return max(0, len(self.courses) - self._visible())

    def _overflow(self):
        return self._max_first() > 0

    def _clamp(self, x):
        return min(max(0, int(round(x))), self._max_first())

    def _start_x(self, offset=None):
        offset = self.offset if offset is None else offset
        vis = min(len(self.courses), self._visible())
        group = vis * self._s + (vis - 1) * GAP
        return (self._size[0] - group) / 2 - offset * (self._s + GAP)

    def _update_rects(self):
        s, x0 = self._s, self._start_x()
        self.rects = []
        for i in range(len(self.courses)):
            x = x0 + i * (s + GAP)
            lift = LIFT if i == self.hover else 0
            self.rects.append((x, self._cy - s / 2 - lift, x + s, self._cy + s / 2 - lift))

    def _shown(self, i):
        vis = min(len(self.courses), self._visible())
        return self.offset - 1 < i < self.offset + vis

    def _open(self, i):
        return i is not None and 0 <= i < len(self.courses) and \
            self.courses[i]["id"] in self.allowed

    # --- pudar di tepi ----------------------------------------------------------------------------
    def _fade_mask(self, W, H):
        key = ("dockfade", W, H)
        m = I._img_cache.get(key)
        if m is None:
            row = []
            for x in range(W):
                t = min(1.0, (x + 0.5) / FADE, (W - x - 0.5) / FADE)
                row.append(int(255 * t * t * (3 - 2 * t)))
            m = photos.Image.new("L", (W, 1))
            m.putdata(row)
            m = m.resize((W, H))
            I._img_cache[key] = m
        return m

    def _fade_at(self, x):
        if not self._overflow():
            return 1.0
        t = max(0.0, min(1.0, x / FADE, (self._size[0] - x) / FADE))
        return t * t * (3 - 2 * t)

    @staticmethod
    def _col(color, f):
        if f >= 0.999:
            return color
        a, b = _rgb(color), _rgb(C.BG)
        return "#%02x%02x%02x" % tuple(int(b[k] + (a[k] - b[k]) * f) for k in range(3))

    # --- gambar kartu & panah (disimpan) ----------------------------------------------------
    def _card_img(self, s, hover):
        key = ("dockcard", s, hover)
        img = I._img_cache.get(key)
        if img is None:
            Image = photos.Image
            img = Image.new("RGBA", (s, s), _rgb(C.CARD) + (0,))
            outer = I.round_mask(s, s, RADIUS).point(lambda v: int(v * CARD_ALPHA))
            inner = I.round_mask(s - 2, s - 2, RADIUS - 1).point(lambda v: int(v * CARD_ALPHA))
            border = _rgb(C.ACCENT if hover else C.BORDER)
            fill = _rgb(C.CARD_HOVER if hover else C.CARD)
            img.paste(border + (255,), (0, 0), outer)
            body = Image.new("RGBA", (s - 2, s - 2), fill + (255,))
            body.putalpha(inner)
            img.alpha_composite(body, (1, 1))
            I._img_cache[key] = img
        return img

    def _arrow_mask(self, side):
        key = ("dockarrow", side)
        m = I._img_cache.get(key)
        if m is None:
            m = I._render_icon("chev_right", "#ffffff", "#000000", 40).convert("L")
            if side < 0:
                m = m.transpose(0)       # 0 = cermin kiri-kanan
            I._img_cache[key] = m
        return m

    # --- susun ulang semuanya (ukuran / daftar berubah) ------------------------------------
    def _rebuild(self):
        if self._size[0] < 50:
            return
        w, h = self._size
        self._s = self._card_size()
        s = self._s
        self._cy = h * 0.54
        self._band = (int(self._cy - s / 2 - LIFT - 2), int(s + LIFT + 6))
        self.coords(self._band_item, 0, self._band[0])
        self.delete("fg")
        self._items, self._fades = [], []
        top = self._cy - s / 2 - LIFT
        self.create_text(w / 2, top - 58, text=self.title_text, font=self.f["h1"],
                         fill=C.TEXT, tags="fg")
        self.create_text(w / 2, top - 28, text=self.hello_text, font=self.f["hello"],
                         fill=C.MUTED, tags="fg")
        self._update_rects()
        if not self.courses:
            self.create_text(w / 2, self._cy, text=self.empty_text, font=self.f["hello"],
                             fill=C.MUTED, tags="fg")
        else:
            self._fit_title(s)
            for i, c in enumerate(self.courses):
                self._items.append(self._card_text(i, c))
                self._fades.append(1.0)
        self._text_x = self._start_x()
        self._apply_fades(force=True)
        self._compose_band()

    def _fit_title(self, s):
        longest = max((c["title"] for c in self.courses), key=len)
        for size in (16, 15, 14, 13, 12, 11, 10):
            self.f["title"].config(size=size)
            if self.f["title"].measure(longest) <= s - 36:
                break

    def _card_text(self, i, c):
        x0, y0, x1, y1 = self.rects[i]
        if i == self.hover:
            y0, y1 = y0 + LIFT, y1 + LIFT     # teks dibuat di posisi normal, diangkat lewat move
        pad = 18
        unlocked = c["id"] in self.allowed
        accent = c["color"] if unlocked else C.TRACK_OFF
        tags = ("fg", "cards", f"c{i}")
        out = []
        x, y = x0 + pad, y0 + pad
        out.append((self.create_rectangle(x, y, x + 30, y + 4, fill=accent, outline=accent,
                                          tags=tags), accent, "rect"))
        y += 16
        out.append((self.create_text(x, y, text=c["group"], anchor="nw", font=self.f["group"],
                                     fill=accent, tags=tags), accent, "text"))
        y += 16
        tcol = C.TEXT if unlocked else C.LOCKED
        out.append((self.create_text(x, y, text=c["title"], anchor="nw",
                                     font=self.f["title"], fill=tcol, tags=tags), tcol, "text"))
        y += self.f["title"].metrics("linespace") + 6
        dcol = C.MUTED if unlocked else C.LOCKED
        f = self.f["desc"]
        line_h = f.metrics("linespace")
        max_lines = max(1, int((y1 - pad - 26 - y) // line_h))
        for n, line in enumerate(self._wrap(f, c["desc"], (x1 - x0) - 2 * pad, max_lines)):
            out.append((self.create_text(x, y + n * line_h, text=line, anchor="nw", font=f,
                                         fill=dcol, tags=tags), dcol, "text"))
        foot = "Buka kursus  →" if unlocked else "Terkunci  ·  hubungi guru"
        fcol = C.ACCENT if unlocked else C.LOCKED
        out.append((self.create_text(x, y1 - pad, text=foot, anchor="sw", font=self.f["foot"],
                                     fill=fcol, tags=tags), fcol, "text"))
        if i == self.hover and self._open(i):
            self.move(f"c{i}", 0, -LIFT)
        return out

    @staticmethod
    def _wrap(f, text, width, max_lines):
        lines, cur = [], ""
        for word in text.split():
            trial = f"{cur} {word}".strip()
            if cur and f.measure(trial) > width:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        if cur:
            lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while last and f.measure(last + "...") > width:
                last = last[:-1]
            lines[-1] = last.rstrip() + "..."
        return lines

    # --- langkah ringan (animasi / hover) ---------------------------------------------------
    def _apply_fades(self, force=False):
        """Warna teks kartu ikut memudar di tepi; hanya kartu yang berubah yang diperbarui."""
        for i, items in enumerate(self._items):
            x0, _y0, x1, _y1 = self.rects[i]
            f = round(self._fade_at((x0 + x1) / 2) * 20) / 20
            if not force and f == self._fades[i]:
                continue
            self._fades[i] = f
            hidden = f <= 0.05
            for item, col, kind in items:
                if hidden:
                    self.itemconfigure(item, state="hidden")
                    continue
                c = self._col(col, f)
                if kind == "rect":
                    self.itemconfigure(item, state="normal", fill=c, outline=c)
                else:
                    self.itemconfigure(item, state="normal", fill=c)

    def _compose_band(self):
        """Pita kartu: potongan latar + kartu + pudar tepi + panah -> satu gambar kecil."""
        if self._base is None or self._size[0] < 50:
            return
        Image = photos.Image
        W = self._size[0]
        by, bh = self._band
        bg = self._base.crop((0, by, W, by + bh))
        out = bg.convert("RGBA")
        s = self._s
        for i, (x0, y0, x1, _y1) in enumerate(self.rects):
            if x1 < 0 or x0 > W:
                continue
            hov = i == self.hover and self._open(i) and self._shown(i)
            self._paste_clipped(out, self._card_img(s, hov), int(round(x0)),
                                int(round(y0)) - by)
        out = out.convert("RGB")
        if self._overflow():
            out = Image.composite(out, bg, self._fade_mask(W, bh))
            cy = int(self._cy) - by
            for side, show in ((-1, self.target > 0), (1, self.target < self._max_first())):
                if not show:
                    continue
                m = self._arrow_mask(side)
                x = 4 if side < 0 else W - 44
                col = C.TEXT if self._arrow_hover == side else C.MUTED
                out.paste(_rgb(col), (x, cy - 20), m)
        self._band_photo = photos.to_photoimage(out)
        self.itemconfigure(self._band_item, image=self._band_photo)

    @staticmethod
    def _paste_clipped(dst, src, x, y):
        """alpha_composite tidak boleh keluar batas: potong dulu bagian yang terlihat."""
        W, H = dst.size
        sx0, sy0 = max(0, -x), max(0, -y)
        sx1, sy1 = min(src.size[0], W - x), min(src.size[1], H - y)
        if sx1 > sx0 and sy1 > sy0:
            dst.alpha_composite(src.crop((sx0, sy0, sx1, sy1)), (x + sx0, y + sy0))

    def _set_base_photo(self):
        if self._base is not None:
            self._base_photo = photos.to_photoimage(self._base)
            self.itemconfigure(self._base_item, image=self._base_photo)

    def _frame(self):
        """Satu langkah: posisi baru -> geser teks, perbarui pudar, susun pita."""
        old_x = self._text_x
        self._update_rects()
        nx = self._start_x()
        if abs(nx - old_x) >= 0.01:
            self.move("cards", nx - old_x, 0)
            self._text_x = nx
        self._apply_fades()
        self._compose_band()

    # --- interaksi ---------------------------------------------------------------------------
    def _arrow_at(self, x, y):
        if not self._overflow() or abs(y - self._cy) > 40:
            return None
        if x < ARROW_ZONE and self.target > 0:
            return -1
        if x > self._size[0] - ARROW_ZONE and self.target < self._max_first():
            return 1
        return None

    def _index_at(self, x, y):
        for i, (x0, y0, x1, y1) in enumerate(self.rects):
            if x0 <= x <= x1 and y0 <= y <= y1 and self._fade_at((x0 + x1) / 2) > 0.05:
                return i
        return None

    def _set_arrow_hover(self, side):
        if side != self._arrow_hover:
            self._arrow_hover = side
            if self._anim is None:
                self._compose_band()

    def _motion(self, e):
        side = self._arrow_at(e.x, e.y)
        self._set_arrow_hover(side)
        if side is not None:
            self._set_hover(None)
            self.config(cursor="hand2")
            return
        self._set_hover(self._index_at(e.x, e.y))

    def _set_hover(self, i):
        if i is not None and not self._shown(i):     # kartu di tepi: klik = geser ke sana
            self.config(cursor="hand2")
            i = None
        else:
            self.config(cursor="hand2" if self._open(i) else "")
        if not self._open(i):
            i = None
        if i == self.hover:
            return
        old, self.hover = self.hover, i
        for j, dy in ((old, LIFT), (i, -LIFT)):
            if j is not None:
                self.move(f"c{j}", 0, dy)
        self._update_rects()
        if self._anim is None:
            self._compose_band()

    def _click(self, e):
        side = self._arrow_at(e.x, e.y)
        if side is not None:
            self.scroll_by(side)
            return
        i = self._index_at(e.x, e.y)
        if i is None:
            return
        if not self._shown(i):
            vis = self._visible()
            self._go(self._clamp(i if i < self.target else i - vis + 1))
            return
        if self._open(i):
            self.on_open(self.courses[i])

    def _wheel(self, e):
        self.scroll_by(-1 if e.delta > 0 else 1)

    def _key(self, d):
        try:
            if isinstance(self.focus_get(), tk.Entry):
                return      # sedang mengetik di kolom cari
        except (KeyError, tk.TclError):
            pass
        if self.winfo_ismapped():
            self.scroll_by(d)

    def scroll_by(self, d):
        self._go(self._clamp(self.target + d))

    def _go(self, new):
        if new == self.target:
            return
        self.target = new
        self._set_hover(None)
        import time
        self._from, self._t0 = self.offset, time.perf_counter()
        if self._anim is None and not self._closed:
            self._anim = self.after(0, self._step)

    def _step(self):
        """Animasi geser berbasis waktu (easing), maks. 30 fps; frame yang telat dilompati."""
        import time
        self._anim = None
        if self._closed or not self.winfo_exists():
            return
        t0 = time.perf_counter()
        t = min(1.0, (t0 - self._t0) * 1000 / SCROLL_MS)
        ease = 1 - (1 - t) ** 3
        self.offset = self.target if t >= 1.0 else self._from + (self.target - self._from) * ease
        self._frame()
        if t < 1.0:
            spent = (time.perf_counter() - t0) * 1000
            self._anim = self.after(max(1, int(self.FRAME_MS - spent)), self._step)

    # --- video ------------------------------------------------------------------------------
    def _video_tick(self):
        if self._closed:
            return
        try:
            iconic = self.winfo_toplevel().state() == "iconic"
        except tk.TclError:
            return
        img = None if iconic else self.video.latest()
        if img is not None and img.size == self._size:
            self._base = img
            self._set_base_photo()
            if self._anim is None:
                self._compose_band()
        if self.video.failed():
            C.log(f"Video latar beranda gagal: {self.video.player.error}")
            self.video.stop()
            return
        self.after(1000 // VIDEO_FPS, self._video_tick)

    def destroy(self):
        self._closed = True
        self.video.stop()
        super().destroy()
