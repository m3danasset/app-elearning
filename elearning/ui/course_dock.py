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

Dashboard murid (hero, teaser=True): kursor diam di atas kartu kursus (TEASER_SHOW_MS) ->
kartu video TEASER (ui/teaser.py) muncul memudar di atas sapaan, ukuran sedang (maks.
TEASER_W). Kursor pindah ke kartu lain = videonya berganti; keluar dari kartu = memudar hilang.
Widget USB (kalau ada) bergeser ke kanan kartu teaser selama teaser tampil.
"""

import os
import threading
import time
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
USB_W, USB_H = 340, 96     # widget USB (gaya widget Dashboard admin / guru, 1 saja, tetap)
USB_ON = "#3fb68b"
USB_PAD = 28               # ruang bayangan di sekitar widget
USB_BTN = 34               # tombol eject bulat di kanan widget
# Bayangan lembut: SATU spesifikasi untuk semua dashboard (dashboard_view.SH_*)
from elearning.ui.dashboard_view import SH_ALPHA, SH_BLUR, SH_DY, TEXT_SH_ALPHA  # noqa: E402
TEASER_W = 840             # lebar kartu video teaser (16:9; mengecil kalau ruang kurang)
TEASER_SHOW_MS = 220       # kursor diam sekian di atas kartu kursus -> teaser muncul
TEASER_HIDE_MS = 260       # kursor keluar dari kartu -> teaser hilang (kecuali pindah kartu)
TEASER_FADE_MS = 280       # pudar masuk / keluar (dihitung tiap frame UI, 30 fps)
TEASER_RISE = 14           # kartu naik sekian px saat muncul (ikut pudar)
TEASER_GAP = 30            # jarak kartu teaser -> widget USB (> ruang bayangan teaser)
TEASER_BLUR, TEASER_SH_DY, TEASER_SH_A = SH_BLUR, SH_DY, SH_ALPHA   # bayangan yang sama
SLIDE_MS = 340             # widget USB bergeser ke kanan / kembali (ease-in-out)
STATS_W, STATS_H = 880, 92  # widget progres belajar di bawah kartu kursus (murid)
STATS_PAD = 28             # ruang bayangan di sekitar widget progres


def _rgb(c):
    return I._rgb(c)


def _ease(t):
    """Ease-in-out (kubik): mulai & berhenti pelan, tidak melompat di frame pertama."""
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _tint(s, color, strength):
    """Cahaya lembut warna dari kiri-atas, memudar ke kanan-bawah (dalam sudut membulat)."""
    Image = photos.Image
    g = Image.linear_gradient("L").rotate(-90).resize((s, s))       # kiri 255 -> kanan 0
    v = Image.linear_gradient("L").resize((s, s))                    # atas 0 -> bawah 255
    a = Image.composite(g, Image.new("L", (s, s), 0), v.point(lambda x: 255 - x * 3 // 4))
    a = a.point(lambda x: int((x / 255.0) ** 1.5 * 255 * strength))
    mask = Image.new("L", (s, s), 0)
    mask.paste(I.round_mask(s - 2, s - 2, RADIUS - 1), (1, 1))
    a = Image.composite(a, Image.new("L", (s, s), 0), mask)
    img = Image.new("RGBA", (s, s), _rgb(color) + (0,))
    img.putalpha(a)
    return img


def cover_resize(img, size):
    """Frame lama -> ukuran baru TANPA melar: diperbesar proporsional lalu dipotong di tengah
    (cara "cover" yang sama dengan video latar), jadi saat sidebar dilipat / dibuka latar
    tidak meloncat ketika frame video ukuran baru datang."""
    W, H = size
    w, h = img.size
    if (w, h) == (W, H) or w < 2 or h < 2:
        return img
    k = max(W / w, H / h)
    nw, nh = max(W, int(round(w * k))), max(H, int(round(h * k)))
    big = img.resize((nw, nh), photos.Image.BILINEAR)
    x0, y0 = (nw - W) // 2, (nh - H) // 2
    return big.crop((x0, y0, x0 + W, y0 + H))


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

    def __init__(self, master, courses, allowed, on_open, title, hello, foot=None, usb=False,
                 hero=False, teaser=False, stats=None):
        super().__init__(master, bg=C.BG, highlightthickness=0, bd=0)
        # teks bawah kartu (terbuka, terkunci); resource trial memakai "Open in Blender" dst.
        self.foot = foot or ("Open course  →", "Locked  ·  ask your teacher")
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
        self._resize_job = None        # jendela diseret: susun ulang sekali setelah berhenti
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
            "hero": tkfont.Font(family=C.FONT, size=40, weight="bold"),
            "wbig": tkfont.Font(family=C.FONT, size=14, weight="bold"),
            "wsmall": tkfont.Font(family=C.FONT, size=9),
        }
        # widget USB di atas judul (murid SK / PB / IC): tidak bisa diatur / dipindah
        self.usb = usb
        self.hero = hero             # halaman utama murid = Dashboard: sapaan besar (40 pt)
        self._title_y = 0
        self._usb_drives = None      # None = sedang dicek; [(root, label, free, total)]
        self._usb_rect = None
        self._usb_stop = None        # berhenti mendengar usb_save.monitor
        self._usb_photo = None
        self._usb_hover = False      # kursor di atas tombol eject
        self._usb_ejecting = False
        self._usb_msg = None         # (teks, warna, sampai kapan) pesan eject gagal
        self._usb_item = self.create_image(0, 0, anchor="nw")
        self._usb_cx = 0             # x widget USB di tengah (tanpa geser)
        self._usb_off = 0.0          # geser ke kanan saat teaser tampil (beranimasi)
        self._usb_slide = None       # (dari, ke, waktu mulai)
        # video teaser (Dashboard murid): SATU gambar RGB (latar + bayangan + video)
        self.teaser = teaser and hero
        self._tz = None              # {"cid", "player", "rect", "photo", "a", "from", "to", "t0"}
        self._tz_want = None         # id kursus di bawah kursor (setelah jeda)
        self._tz_timer = None
        self._tz_job = None
        self._tz_item = self.create_image(0, 0, anchor="nw")
        # widget progres belajar (murid, bukan trial): angka dihitung di thread
        self.stats_student = stats
        self._stats = None
        self._stats_photo = None
        self._stats_bars = []
        self._stats_item = self.create_image(0, 0, anchor="nw")
        if stats is not None:
            self._load_stats()
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
        self.bind("<Leave>", lambda e: (self._set_hover(None), self._set_arrow_hover(None),
                                        self._usb_set_hover(False), self._tease(None)))
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
        if self.usb:
            from elearning.ui import usb_save
            self._usb_stop = usb_save.monitor(self).subscribe(self._usb_changed)

    # --- data -------------------------------------------------------------------------------
    def set_courses(self, courses, empty_text=""):
        self.courses = list(courses)
        self.empty_text = empty_text
        self.hover = None
        self.offset = self.target = 0
        self._rebuild()

    # --- ukuran ---------------------------------------------------------------------------------
    def _on_resize(self, e):
        """Ukuran berubah. Jendela diseret (windowed): tidak disusun ulang tiap event (lambat);
        tirai gelap App menutupi, susun ulang sekali setelah ukuran berhenti berubah."""
        size = (e.width, e.height)
        if size == getattr(self, "_pending", self._size) or e.width < 50 or e.height < 50:
            return
        first = self._size == (0, 0)
        self._pending = size                 # diterapkan di _resized (gambar tetap ukuran lama)
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
            self._resize_job = None
        if first:
            self._resized()
        else:
            self._resize_job = self.after(100, self._resized)

    def _resized(self):
        self._resize_job = None
        if not self.winfo_exists():
            return
        self._size = self._pending
        self.video.set_size(*self._size)
        if self._base is not None and self.video.ok:
            self._base = cover_resize(self._base, self._size)   # frame lama, proporsional
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
    def _card_img(self, s, hover, color=None, unlocked=True):
        """Kartu 1:1 sedikit tembus + cahaya gradasi warna kursus dari kiri-atas (gaya kartu
        Dashboard admin / guru). Terkunci: gradasi samar."""
        key = ("dockcard", s, hover, color, unlocked)
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
            if color:
                img.alpha_composite(_tint(s, color, (0.30 if hover else 0.24) if unlocked
                                          else 0.07))
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
        if self.hero and self.stats_student is None:
            # trial / Resources trial: tanpa widget progres di bawah -> sapaan + kartu (tinggi
            # blok ~ sapaan 92 px + kartu) tepat di TENGAH halaman
            self._cy = h / 2 + 46 + LIFT / 2
        else:
            self._cy = h * (0.60 if self.hero else 0.54)
        self._band = (int(self._cy - s / 2 - LIFT - 2),
                      int(s + LIFT + 6 + 2 * SH_BLUR + SH_DY))   # + ruang bayangan
        self.coords(self._band_item, 0, self._band[0])
        self.delete("fg")
        self._items, self._fades = [], []
        top = self._cy - s / 2 - LIFT
        if self.hero:      # gaya Dashboard admin / guru: sapaan besar, baris kecil di bawahnya
            f = self.f["hero"]
            for size in (40, 34, 28, 24):
                f.config(size=size)
                if f.measure(self.title_text) <= w - 80:
                    break
            title_y = top - 42 - f.metrics("linespace")
            t1 = self.create_text(w / 2, title_y, text=self.title_text, font=f, anchor="n",
                                  fill=C.TEXT, tags="fg")
            t2 = self.create_text(w / 2, top - 28, text=self.hello_text, font=self.f["hello"],
                                  fill=C.MUTED, tags="fg")
            self._text_shadows(((t1, TEXT_SH_ALPHA[0]), (t2, TEXT_SH_ALPHA[1])))
            title_y -= 2
        else:
            title_y = top - 58
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
        self._title_y = title_y
        self._usb_layout(title_y if self.hero else title_y - 14)
        self._stats_layout()
        self._tz_relayout()

    def _text_shadows(self, items):
        """Bayangan lembut (kapsul ter-blur seukuran teks, seperti widget) di bawah teks."""
        from elearning.ui.dashboard_view import text_shadow
        self._tsh = []
        for item, alpha in items:
            text_shadow(self, item, alpha, self._tsh, "fg")

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
        foot = c.get("foot") or (self.foot[0] if unlocked else self.foot[1])
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
            c = self.courses[i]
            from elearning.ui.dashboard_view import _shadow
            sh, sp = _shadow(s, s, RADIUS, SH_BLUR, SH_ALPHA)      # bayangan lembut (widget)
            self._paste_clipped(out, sh, int(round(x0)) - sp,
                                int(round(y0)) - by - sp + SH_DY)
            self._paste_clipped(out, self._card_img(s, hov, c.get("color"),
                                                    c["id"] in self.allowed), int(round(x0)),
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
        if self.teaser:
            i = self._index_at(e.x, e.y)
            self._tease(i if i is not None and self._shown(i) else None)
        on = self._usb_on_btn(e.x, e.y)
        self._usb_set_hover(on)
        if on:
            self._set_hover(None)
            self.config(cursor="hand2")
            return
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
        if self._usb_on_btn(e.x, e.y):
            self._usb_eject()
            return
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
        if C.lite():                       # mode ringan: langsung pindah, tanpa animasi
            self.offset = float(new)
            self._frame()
            return
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
        # Teaser tampil / widget USB sedang bergeser: latar (redup) DIAM sebentar. Mengganti
        # gambar latar layar penuh ~20 ms di thread utama -> animasi teaser patah-patah.
        if self._tz is not None or self._usb_slide is not None:
            img = None
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

    # --- widget USB ------------------------------------------------------------------------
    # --- widget progres belajar (di bawah kartu kursus) ------------------------------------
    def _load_stats(self):
        box = {}

        def work():
            try:
                from elearning import student_stats
                box["s"] = student_stats.compute(self.stats_student)
            except Exception as exc:
                C.log(f"Progres murid: gagal dihitung: {exc!r}")
                box["s"] = None
            box["done"] = True
        threading.Thread(target=work, daemon=True).start()

        def poll():
            if self._closed:
                return
            if not box.get("done"):
                self.after(80, poll)
                return
            self._stats = box["s"]
            self._stats_layout()
        self.after(80, poll)

    def _stats_layout(self):
        """Satu kartu (bayangan & sudut bulat seperti widget USB) berisi 4 angka; hanya tampil
        kalau ada ruang di bawah kartu kursus."""
        self.delete("statw")
        self._stats_bars = []
        st = self._stats
        w, h = self._size
        if st is None or w < 300:
            self.itemconfigure(self._stats_item, image="")
            return
        band_bottom = self._band[0] + self._band[1]
        ww = int(min(STATS_W, w - 48))
        y = band_bottom + 4
        if ww < 420 or y + STATS_H + 14 > h:
            self.itemconfigure(self._stats_item, image="")
            return
        x = int((w - ww) / 2)
        self._compose_stats(x, int(y), ww)
        self._stats_text(x, int(y), ww)

    def _compose_stats(self, x0, y0, w):
        from elearning.ui.dashboard_view import _shadow
        Image = photos.Image
        h, pad = STATS_H, STATS_PAD
        key = ("statsbody", w, h)
        img = I._img_cache.get(key)
        if img is None:
            img = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
            sh, sp = _shadow(w, h, 18)
            self._paste_clipped(img, sh, pad - sp, pad - sp + SH_DY)
            body = Image.new("RGBA", (w, h), _rgb(C.BORDER) + (0,))
            body.putalpha(I.round_mask(w, h, 16).point(lambda v: int(v * 0.93)))
            inner = Image.new("RGBA", (w - 2, h - 2), _rgb(C.CARD) + (0,))
            inner.putalpha(I.round_mask(w - 2, h - 2, 15).point(lambda v: int(v * 0.93)))
            body.alpha_composite(inner, (1, 1))
            for k in range(1, 4):                       # garis pemisah antar angka
                lx = int(w * k / 4)
                line = Image.new("RGBA", (1, h - 32), _rgb(C.BORDER) + (255,))
                body.alpha_composite(line, (lx, 16))
            img.alpha_composite(body, (pad, pad))
            I._img_cache[key] = img
        self._stats_photo = photos.to_photoimage(img)
        self.coords(self._stats_item, x0 - pad, y0 - pad)
        self.itemconfigure(self._stats_item, image=self._stats_photo)

    def _stats_text(self, x0, y0, w):
        from elearning import student_stats as SS
        st = self._stats
        cw = w / 4
        done, total = st["videos_done"], st["videos_total"]
        cells = (
            ("Videos watched", f"{done}/{total}" if total else "–",
             f"{round(done / total * 100)}% complete" if total else "no videos yet", "bar"),
            ("Badges earned", str(st["badges"]), "across your courses", None),
            ("Your work", f"{st['portfolio']} · {st['assignment']}", "portfolio · assignment",
             None),
            ("Study time this week", SS.fmt_time(st["week_seconds"]),
             f"{st['streak']}-day streak" if st["streak"] >= 2 else "keep it going!", None),
        )
        for i, (label, value, sub, viz) in enumerate(cells):
            cx = x0 + i * cw + 20
            tw = cw - 40
            self.create_text(cx, y0 + 16, text=self._fit(label, "wsmall", tw), anchor="nw",
                             font=self.f["wsmall"], fill=C.MUTED, tags=("fg", "statw"))
            self.create_text(cx, y0 + 32, text=self._fit(value, "wbig", tw), anchor="nw",
                             font=self.f["wbig"], fill=C.TEXT, tags=("fg", "statw"))
            if viz == "bar" and total:
                bw = int(tw)
                bg = I.pill(bw, 6, C.SIDEBAR_ACTIVE, C.CARD, r=3)
                self._stats_bars.append(bg)
                self.create_image(cx, y0 + 64, image=bg, anchor="nw", tags=("fg", "statw"))
                fw = int(bw * done / total)
                if fw >= 6:
                    fg = I.pill(fw, 6, USB_ON, C.SIDEBAR_ACTIVE, r=3)
                    self._stats_bars.append(fg)
                    self.create_image(cx, y0 + 64, image=fg, anchor="nw", tags=("fg", "statw"))
                self.create_text(cx + bw, y0 + 36, text=sub, anchor="ne", font=self.f["wsmall"],
                                 fill=USB_ON, tags=("fg", "statw"))
            else:
                self.create_text(cx, y0 + 60, text=self._fit(sub, "wsmall", tw), anchor="nw",
                                 font=self.f["wsmall"], fill=C.MUTED, tags=("fg", "statw"))

    def _usb_layout(self, title_y):
        """Widget di tengah ruang kosong di atas judul. Tidak tampil kalau tidak ada USB yang
        tercolok atau ruangnya kurang."""
        self.delete("usbw")
        self._usb_rect = None
        if not self.usb or not self._usb_drives:
            self.itemconfigure(self._usb_item, image="")
            return
        w = self._size[0]
        ww = int(min(USB_W, w - 48))
        bottom = title_y - 16
        y = max(16, (bottom - USB_H) / 2)
        if ww < 200 or bottom - y < USB_H:
            self.itemconfigure(self._usb_item, image="")
            return
        x = (w - ww) / 2
        self._usb_cx = int(x)
        self._usb_off = min(self._usb_off, max(0.0, w - 16 - ww - x))
        x += self._usb_off
        self._usb_rect = (int(x), int(y), int(x) + ww, int(y) + USB_H)
        self._compose_usb()
        self._usb_text()

    def _compose_usb(self):
        """Potongan latar + bayangan + badan + cahaya warna + ikon -> satu gambar kecil."""
        if self._usb_rect is None or self._base is None:
            return
        from elearning.ui.dashboard_view import DashboardView, _shadow
        Image = photos.Image
        x0, y0, x1, y1 = self._usb_rect
        w, h = x1 - x0, y1 - y0
        pad = USB_PAD
        on = bool(self._usb_drives)
        # RGBA TRANSPARAN (tidak menyalin latar): Tk mencampurnya di atas video latar, jadi
        # menggeser widget cukup memindah koordinat (mulus) & tidak disusun ulang tiap frame video
        bx0, by0 = x0 - pad, y0 - pad
        state = (w, h, on, self._usb_hover, self._usb_ejecting)
        if self._usb_photo is not None and getattr(self, "_usb_state", None) == state:
            self.coords(self._usb_item, bx0, by0)
            return
        out = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        color = USB_ON if on else C.MUTED
        sh, sp = _shadow(w, h, 18)
        self._paste_clipped(out, sh, x0 - sp - bx0, y0 - sp - by0 + SH_DY)
        key = ("usbbody", w, h)
        body = I._img_cache.get(key)
        if body is None:
            body = Image.new("RGBA", (w, h), _rgb(C.BORDER) + (0,))
            body.putalpha(I.round_mask(w, h, 16).point(lambda v: int(v * 0.93)))
            inner = Image.new("RGBA", (w - 2, h - 2), _rgb(C.CARD) + (0,))
            inner.putalpha(I.round_mask(w - 2, h - 2, 15).point(lambda v: int(v * 0.93)))
            body.alpha_composite(inner, (1, 1))
            I._img_cache[key] = body
        self._paste_clipped(out, body, x0 - bx0, y0 - by0)
        self._paste_clipped(out, DashboardView._tint(w, h, color, "todo" if on else "info"),
                            x0 - bx0, y0 - by0)
        key = ("usbicon", color)
        icon = I._img_cache.get(key)
        if icon is None:
            disc = color if on else "#4a4842"
            icon = I._render_icon("usb", "#ffffff", C.CARD, 38, disc=disc).convert("RGBA")
            icon.putalpha(I.round_mask(38, 38, 19))
            I._img_cache[key] = icon
        self._paste_clipped(out, icon, x0 + 18 - bx0, y0 + (h - 38) // 2 - by0)
        if not self._usb_ejecting:          # tombol eject: lingkaran samar, terang saat disorot
            key = ("usbeject", self._usb_hover)
            btn = I._img_cache.get(key)
            if btn is None:
                fill = C.CARD_HOVER if self._usb_hover else C.CARD
                disc = "#4f4c46" if self._usb_hover else "#3a3833"
                btn = I._render_icon("eject", C.TEXT if self._usb_hover else C.MUTED, fill,
                                     USB_BTN, disc=disc).convert("RGBA")
                btn.putalpha(I.round_mask(USB_BTN, USB_BTN, USB_BTN / 2))
                I._img_cache[key] = btn
            bx, by = self._usb_btn_xy()
            self._paste_clipped(out, btn, int(bx) - bx0, int(by) - by0)
        self._usb_photo = photos.to_photoimage(out)
        self._usb_state = state
        self.coords(self._usb_item, bx0, by0)
        self.itemconfigure(self._usb_item, image=self._usb_photo)

    def _usb_btn_xy(self):
        x0, y0, x1, y1 = self._usb_rect
        return x1 - 16 - USB_BTN, (y0 + y1 - USB_BTN) / 2

    def _usb_on_btn(self, x, y):
        if self._usb_rect is None or self._usb_ejecting:
            return False
        bx, by = self._usb_btn_xy()
        r = USB_BTN / 2
        return (x - bx - r) ** 2 + (y - by - r) ** 2 <= (r + 3) ** 2

    def _usb_set_hover(self, on):
        if on != self._usb_hover:
            self._usb_hover = on
            self._compose_usb()

    def _usb_eject(self):
        """Keluarkan semua flashdisk di widget (di thread); berhasil -> widget hilang."""
        from elearning.ui import usb_save
        roots = [d[0] for d in self._usb_drives or ()]
        if not roots or self._usb_ejecting:
            return
        self._usb_ejecting, self._usb_hover, self._usb_msg = True, False, None
        self._compose_usb()
        self._usb_text()

        def done(errs):
            if self._closed:
                return
            self._usb_ejecting = False
            if errs:
                self._usb_msg = (errs[0], C.ACCENT, time.monotonic() + 6)
                self.after(6100, self._usb_text)
            self._compose_usb()
            self._usb_text()

        usb_save.eject_async(self, roots, done)

    def _fit(self, text, font, width):
        f = self.f[font]
        if f.measure(text) <= width:
            return text
        while text and f.measure(text + "...") > width:
            text = text[:-1]
        return text.rstrip() + "..."

    @staticmethod
    def _size_text(n):
        if n is None:
            return ""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024 or unit == "TB":
                return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
            n /= 1024.0

    def _usb_text(self):
        self.delete("usbw")
        if self._usb_rect is None:
            return
        x0, y0, x1, y1 = self._usb_rect
        tx = x0 + 18 + 38 + 14
        tw = x1 - tx - 16 - USB_BTN - 8
        d = self._usb_drives
        if not d:
            return
        if len(d) == 1:
            root, label, free, _total = d[0]
            name = f"{label} ({root[:2]})" if label else f"USB ({root[:2]})"
            big = "USB plugged in"
            small = name + (f"  ·  {self._size_text(free)} free" if free is not None else "")
            col = USB_ON
        else:
            big = f"{len(d)} USB plugged in"
            small = "  ·  ".join(r[:2] for r, *_ in d)
            col = USB_ON
        if self._usb_ejecting:
            small, smcol = "Ejecting... don't unplug yet", C.MUTED
        elif self._usb_msg and time.monotonic() < self._usb_msg[2]:
            small, smcol = self._usb_msg[0], self._usb_msg[1]
        else:
            smcol = C.MUTED
        cy = (y0 + y1) / 2
        if d:
            big = "● " + big
        self.create_text(tx, cy - 11, text=self._fit(big, "wbig", tw), anchor="w",
                         font=self.f["wbig"], fill=col if d else C.TEXT, tags=("fg", "usbw"))
        self.create_text(tx, cy + 14, text=self._fit(small, "wsmall", tw), anchor="w",
                         font=self.f["wsmall"], fill=smcol, tags=("fg", "usbw"))

    def _usb_changed(self, drives):
        """Pemantau USB (usb_save.monitor): daftar flashdisk berubah."""
        if self._closed:
            return
        shown = bool(drives) != bool(self._usb_drives)
        self._usb_drives = drives
        if shown:                     # dicolok / dicabut semua: widget muncul / hilang
            self._usb_layout(self._title_y if self.hero else self._title_y - 14)
            self._tz_relayout()       # teaser ikut menyesuaikan ruang (widget di kanannya)
        else:
            self._usb_text()

    # --- video teaser (Dashboard murid) ---------------------------------------------------------
    # Supaya muncul mulus: video SUDAH dibuka (thread) begitu kursor menyentuh kartu, kartu baru
    # memudar setelah frame pertamanya siap; pudar + naik sedikit dihitung tiap frame UI (30 fps,
    # jadwal tetap) di thread utama, tidak menunggu frame video (24 fps).
    def _tease(self, i):
        """Kursor di atas kartu i (None = tidak ada): teaser muncul / ganti / hilang setelah jeda."""
        if not self.teaser or self._closed:
            return
        cid = self.courses[i]["id"] if i is not None and i < len(self.courses) else None
        if cid == self._tz_want:
            return
        self._tz_want = cid
        if self._tz_timer is not None:
            self.after_cancel(self._tz_timer)
        if cid is not None and self._tz is None:
            self._tz_open(cid)                      # siapkan video selama jeda (tersembunyi)
        self._tz_timer = self.after(TEASER_SHOW_MS if cid else TEASER_HIDE_MS, self._tease_apply)

    def _tz_player(self, cid, rect):
        from elearning.ui import teaser as TZ
        course = next((c for c in self.courses if c["id"] == cid), None)
        path = TZ.teaser_path(course) if course else None
        if not path or rect is None:
            return None
        p = TZ.make_player(path, 12 if C.lite() else 24, rect[2], rect[3])
        if p is not None:
            p.start()
        return p

    def _tz_open(self, cid):
        rect = self._tz_layout()
        player = self._tz_player(cid, rect)
        if player is None:
            return
        self._tz = {"cid": cid, "player": player, "next": None, "next_cid": None,
                    "rect": rect, "frame": None, "photo": None, "a": 0.0, "from": 0.0,
                    "to": 0.0, "t0": None, "drawn": None}
        if self._tz_job is None:
            self._tz_job = self.after(1, self._tz_tick)

    def _tease_apply(self):
        self._tz_timer = None
        if self._closed:
            return
        cid = self._tz_want
        if cid is None:
            self._tz_fade(0.0)
            return
        if self._tz is None:
            self._tz_open(cid)
        tz = self._tz
        if tz is None:
            return
        if cid not in (tz["cid"], tz["next_cid"]):  # kartu lain: video baru disiapkan, ditukar
            if tz["next"] is not None:              # saat frame pertamanya siap (tanpa kedip)
                tz["next"].stop()
            tz["next"], tz["next_cid"] = self._tz_player(cid, tz["rect"]), cid
        self._tz_fade(1.0)

    def _tz_layout(self):
        """(x, y, w, h) kartu teaser: di tengah ruang di atas sapaan (maks. TEASER_W, 16:9,
        <= 720p); widget USB butuh ruang di kanannya. None kalau ruang tidak cukup."""
        from elearning.ui import teaser as TZ
        W = self._size[0]
        bottom = self._title_y - 16
        tw = min(TEASER_W, TZ.MAX_W, (bottom - 12) * 16 / 9, W - 48)
        if self.usb and self._usb_drives:
            tw = min(tw, W - 2 * (min(USB_W, W - 48) + TEASER_GAP + 16))
        tw = int(tw)
        if tw < 220:
            return None
        th = int(tw * 9 / 16)
        return (int((W - tw) / 2), int(max(12, (bottom - th) / 2)), tw, th)

    def _tz_relayout(self):
        tz = self._tz
        if tz is None:
            return
        rect = self._tz_layout()
        if rect is None:
            self._tz_clear()
            return
        if rect[2:] != tz["rect"][2:]:              # ukuran berubah: frame lama tidak dipakai
            for pl in (tz["player"], tz["next"]):
                if pl is not None:
                    pl.set_target(rect[2], rect[3])
            tz.update(frame=None, photo=None, drawn=None)
            self.itemconfigure(self._tz_item, image="")
        tz["rect"] = rect
        tz["drawn"] = None
        self._usb_target()

    def _tz_fade(self, to):
        tz = self._tz
        if tz is None:
            return
        if tz["to"] != to:
            tz["from"], tz["to"] = tz["a"], to
            tz["t0"] = time.perf_counter() if tz["frame"] is not None else None
        self._usb_target()
        if self._tz_job is None:
            self._tz_job = self.after(1, self._tz_tick)

    def _usb_target(self):
        """Widget USB: geser ke kanan kartu teaser selama teaser tampil, kembali ke tengah."""
        if self._usb_rect is None:
            self._usb_off, self._usb_slide = 0.0, None
            return
        tz = self._tz
        to = 0.0
        if tz is not None and tz["to"] > 0:
            x, _y, w, _h = tz["rect"]
            ww = self._usb_rect[2] - self._usb_rect[0]
            to = max(0.0, min(x + w + TEASER_GAP - self._usb_cx,
                              self._size[0] - 16 - ww - self._usb_cx))
        cur = self._usb_slide[1] if self._usb_slide is not None else self._usb_off
        if cur == to:
            return
        if C.lite():
            self._usb_slide = None
            self._usb_set_off(to)
        else:
            self._usb_slide = (self._usb_off, to, time.perf_counter())
            if self._tz_job is None:
                self._tz_job = self.after(1, self._tz_tick)

    def _usb_set_off(self, off):
        """Geser widget USB: hanya memindah gambar (RGBA) & teksnya, tidak disusun ulang."""
        if self._usb_rect is None:
            return
        self._usb_off = off
        x0, y0, x1, y1 = self._usb_rect
        x = int(round(self._usb_cx + off))
        if x == x0:
            return
        self._usb_rect = (x, y0, x + (x1 - x0), y1)
        self.coords(self._usb_item, x - USB_PAD, y0 - USB_PAD)
        self.move("usbw", x - x0, 0)

    def _tz_draw(self, a, rise):
        """Satu gambar RGB SOLID: potongan latar + bayangan lembut + kartu video bersudut bulat,
        semua dengan tingkat tampil a (pudar), naik `rise` px. Tk menempel RGB ~10x lebih cepat
        daripada gambar bertransparansi (yang dulu membuat animasi patah-patah)."""
        from elearning.ui.dashboard_view import _shadow
        tz = self._tz
        x, y, w, h = tz["rect"]
        yy = y + rise
        frame, mask = tz["frame"], tz["player"].mask
        if mask is None or mask.size != frame.size:
            return
        Image = photos.Image
        simg, pad = _shadow(w, h, 18, TEASER_BLUR, TEASER_SH_A)
        W, H = self._size
        # area gambar = kartu + ruang bayangan, dipotong tepi kanvas
        x0, y0 = max(0, x - pad), max(0, yy - pad + TEASER_SH_DY)
        x1, y1 = min(W, x + w + pad), min(H, yy + h + pad + TEASER_SH_DY)
        # lapisan bawah (latar + bayangan) di-cache: saat video diputar (a = 1, latar diam)
        # tiap frame cukup salin + tempel video
        key = (x0, y0, x1, y1, a, id(self._base))
        cached = tz.get("under")
        if cached is not None and cached[0] == key:
            under = cached[1].copy()
        else:
            if self._base is not None:
                under = self._base.crop((x0, y0, x1, y1))
            else:
                under = Image.new("RGB", (x1 - x0, y1 - y0), _rgb(C.BG))
            sx, sy = x0 - (x - pad), y0 - (yy - pad + TEASER_SH_DY)
            sa = simg.getchannel("A").crop((sx, sy, sx + (x1 - x0), sy + (y1 - y0)))
            if a < 0.999:
                sa = sa.point(lambda v, a=a: int(v * a))
            black = self.__dict__.setdefault("_tz_black", {})
            if black.get("size") != under.size:
                black.update(size=under.size, img=Image.new("RGB", under.size, (0, 0, 0)))
            under = Image.composite(black["img"], under, sa)
            tz["under"] = (key, under.copy())
        if a < 0.999:
            mask = mask.point(lambda v, a=a: int(v * a))
        under.paste(frame, (x - x0, yy - y0), mask)
        if tz["photo"] is None or tz.get("psize") != under.size:
            tz["photo"], tz["psize"] = photos.to_photoimage(under), under.size
            self.itemconfigure(self._tz_item, image=tz["photo"])
        else:
            tz["photo"].paste(under)
        self.coords(self._tz_item, x0, y0)

    def _tz_tick(self):
        """Satu langkah (jadwal tetap maks. 30 fps): pudar + naik teaser, geser widget USB,
        frame video terbaru dari thread."""
        self._tz_job = None
        if self._closed:
            return
        now = time.perf_counter()
        busy = False
        tz = self._tz
        if tz is not None:
            busy = True
            # kursor sudah keluar dari kanvas tanpa <Leave> (mis. jendela lain di depan)
            try:
                px, py = self.winfo_pointerxy()
                inside = (self.winfo_rootx() <= px < self.winfo_rootx() + self.winfo_width()
                          and self.winfo_rooty() <= py < self.winfo_rooty() + self.winfo_height())
                if not inside or self.winfo_toplevel().state() == "iconic":
                    self._tease(None)
            except tk.TclError:
                return
            x, y, w, h = tz["rect"]
            new = False
            nxt = tz["next"]
            if nxt is not None:
                img = nxt.get_latest()
                if img is not None and img.size == (w, h):     # video baru siap: tukar
                    tz["player"].stop()
                    tz.update(player=nxt, cid=tz["next_cid"], next=None, next_cid=None,
                              frame=img)
                    new = True
            if not new:
                img = tz["player"].get_latest()
                if img is not None and img.size == (w, h):
                    tz["frame"], new = img, True
            if tz["frame"] is not None and tz["t0"] is None and tz["a"] != tz["to"]:
                tz["t0"] = now                     # frame pertama siap: pudar mulai sekarang
            if tz["t0"] is not None and tz["a"] != tz["to"]:
                if C.lite():
                    tz["a"] = tz["to"]
                else:
                    t = min(1.0, (now - tz["t0"]) * 1000 / TEASER_FADE_MS)
                    e = _ease(t)
                    tz["a"] = tz["to"] if t >= 1.0 else tz["from"] + (tz["to"] - tz["from"]) * e
            a = tz["a"]
            rise = 0 if C.lite() else int(round(TEASER_RISE * (1 - a)))
            if tz["frame"] is not None and a > 0.0 and (new or tz["drawn"] != (a, rise)):
                self._tz_draw(a, rise)
                tz["drawn"] = (a, rise)
            elif a <= 0.0 and tz["drawn"] is not None:
                self.itemconfigure(self._tz_item, image="")
                tz.update(drawn=None, photo=None)
            if tz["to"] <= 0 and a <= 0.0 and self._tz_want is None:
                self._tz_clear()
                busy = False
        sl = self._usb_slide
        if sl is not None:
            t = min(1.0, (now - sl[2]) * 1000 / SLIDE_MS)
            self._usb_set_off(sl[0] + (sl[1] - sl[0]) * _ease(t))
            if t >= 1.0:
                self._usb_slide = None
            else:
                busy = True
        if busy or self._tz is not None:
            # jadwal TETAP: frame berikutnya pada kelipatan FRAME_MS dari awal, bukan "+34 ms
            # setelah selesai" (yang membuat jarak frame melar & patah-patah)
            nxt_t = getattr(self, "_tz_next_t", now)
            nxt_t = max(nxt_t + self.FRAME_MS / 1000, now + 0.002)
            if nxt_t - now > self.FRAME_MS / 1000:
                nxt_t = now + self.FRAME_MS / 1000
            self._tz_next_t = nxt_t
            self._tz_job = self.after(max(1, int((nxt_t - time.perf_counter()) * 1000)),
                                      self._tz_tick)
        else:
            self._tz_next_t = now

    def _tz_clear(self):
        tz, self._tz = self._tz, None
        if tz is not None:
            for pl in (tz["player"], tz["next"]):
                if pl is not None:
                    pl.stop()
        self.itemconfigure(self._tz_item, image="")
        self._usb_target()

    def destroy(self):
        self._closed = True
        if self._usb_stop is not None:
            self._usb_stop()
        self.video.stop()
        tz = self._tz
        if tz is not None:
            for pl in (tz["player"], tz.get("next")):
                if pl is not None:
                    pl.stop()
        super().destroy()

