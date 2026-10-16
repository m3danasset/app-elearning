"""Panel slideshow karya murid di layar login (sisi kanan, sudut membulat).

Sumber gambar: semua file portfolio yang diunggah murid (gambar, dan satu frame dari tiap
video), 10 unggahan terbaru (SHOWCASE_LIMIT). Berganti otomatis tiap
config.SHOWCASE_SECONDS detik dengan transisi memudar (crossfade). Daftar dibaca ulang tiap
putaran selesai, jadi unggahan baru ikut muncul tanpa membuka ulang aplikasi.

Kalau belum ada portfolio sama sekali: video latar login lama (assets\\video\\) diputar di
panel ini; kalau video juga tidak ada, tampil panel brand polos.

Gambar disiapkan di thread terpisah (buka + kecilkan + potong), jadi layar tetap lancar.
Tanpa ImageDraw / ImageFilter (tidak ikut terbungkus di .exe): hanya Image core.
"""

import os
import threading
import tkinter as tk

from elearning import config as C
from elearning import brand, portfolio, photos
from elearning.courses import COURSES
from elearning.ui import ui_icons as I

RADIUS = 22
FADE_STEPS = 12
FADE_MS = 30
SHOWCASE_LIMIT = 10        # hanya 10 unggahan terbaru
CAPTION_H = 0.18          # bagian bawah gambar yang digelapkan untuk teks (proporsi tinggi)

MONTHS = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def collect(limit=SHOWCASE_LIMIT, skip=()):
    """Semua item portfolio (terbaru dulu), dengan judul kursus & nama murid."""
    root = portfolio.root()
    try:
        sids = os.listdir(root)
    except OSError:
        return []
    titles = {c["id"]: c["title"] for c in COURSES}
    try:
        from elearning.students import list_students
        names = {s["id"]: s["name"] for s in list_students()}
    except Exception:
        names = {}
    items = []
    for sid in sids:
        sdir = os.path.join(root, sid)
        if sid.startswith((".", "_")) or not os.path.isdir(sdir):
            continue
        try:
            cids = os.listdir(sdir)
        except OSError:
            continue
        for cid in cids:
            if cid.startswith((".", "_")) or not os.path.isdir(os.path.join(sdir, cid)):
                continue
            try:
                for it in portfolio.list_items(sid, cid):
                    items.append(dict(it, student_id=sid, student=names.get(sid, ""),
                                      course=titles.get(cid, cid.upper())))
            except Exception as exc:
                C.log(f"Slideshow: gagal membaca portfolio {sid}/{cid}: {exc!r}")
    # hanya portfolio murid: bukan assignment / contoh dari guru (folder berawalan "_")
    rootn = os.path.normcase(os.path.abspath(root))
    def _is_portfolio(path):
        rel = os.path.relpath(os.path.normcase(os.path.abspath(path)), rootn)
        return not any(part.startswith("_") for part in rel.split(os.sep)[:-1])
    items = [i for i in items if i["path"] not in skip and _is_portfolio(i["path"])]
    items.sort(key=lambda i: i["added"], reverse=True)
    return items[:limit]


def _open_image(item, w, h):
    """Gambar Pillow RGB tepat w x h (cover, dipotong dari tengah), atau None."""
    Image = photos.Image
    img = None
    if item["kind"] == "image":
        with Image.open(item["path"]) as f:
            try:
                f.draft("RGB", (w * 2, h * 2))   # JPEG besar: dibaca langsung versi kecil (cepat)
            except Exception:
                pass
            f.load()
            img = photos._flatten(photos._fix_orientation(f))
    else:   # video: satu frame asli; kalau tidak terbaca, dilewati (bukan kotak polos)
        img = portfolio._video_frame(item["path"])
    if img is None:
        return None
    return portfolio._cover(img.convert("RGB"), w, h)


def _caption_shade(w, h):
    """Masker gradasi: makin ke bawah makin gelap (supaya teks putih terbaca)."""
    Image = photos.Image
    key = ("shade", w, h)
    m = I._img_cache.get(key)
    if m is None:
        start = int(h * (1 - CAPTION_H))
        col = Image.new("L", (1, h), 0)
        for y in range(start, h):
            t = (y - start) / max(1, h - start)
            col.putpixel((0, y), int(200 * t * t))
        m = col.resize((w, h))
        I._img_cache[key] = m
    return m


def _finish(img, w, h, bg, shade=True, rounded=True):
    """Gelapkan bawah (teks) lalu bulatkan sudut di atas warna latar."""
    Image = photos.Image
    if shade:
        img = Image.composite(Image.new("RGB", (w, h), (8, 8, 8)), img, _caption_shade(w, h))
    if not rounded:
        return img
    out = Image.new("RGB", (w, h), I._rgb(bg))
    out.paste(img, (0, 0), I.round_mask(w, h, RADIUS))
    return out


def _date(d):
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


class Showcase(tk.Canvas):
    def __init__(self, master, bg=C.LOGIN_BG, host=None):
        super().__init__(master, bg=bg, highlightthickness=0, bd=0)
        self.bg = bg
        # host: tanpa menggambar diri sendiri; gambar & keterangan dikirim ke layar login
        # (yang menggabungkannya dengan video latar). host.frame(img|None), host.caption(a, b)
        self.host = host
        self.size = (0, 0)
        self.items = []
        self.index = -1
        self.current = None       # gambar Pillow yang sedang tampil (sudah jadi)
        self._photo = None
        self._img_item = self.create_image(0, 0, anchor="nw")
        self._jobs = {}
        self._gen = 0             # naik tiap ukuran berubah: hasil lama dibuang
        self._ready = None
        self._lock = threading.Lock()
        self._video = None
        self._mode = None         # "slides", "video", "brand"
        self._closed = False
        self._bad = set()         # file yang gagal dibuka: tidak dicoba lagi
        self._fading = False
        self.bind("<Configure>", self._on_resize)
        self.bind("<Button-1>", lambda e: self.skip())   # klik gambar = gambar berikutnya
        self.bind("<Destroy>", lambda e: self._close() if e.widget is self else None, add="+")

    # --- jadwal ----------------------------------------------------------------------
    def _after(self, name, ms, fn):
        old = self._jobs.pop(name, None)
        if old is not None:
            try:
                self.after_cancel(old)
            except Exception:
                pass
        if not self._closed:
            self._jobs[name] = self.after(ms, fn)

    def _close(self):
        self._closed = True
        for job in self._jobs.values():
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._jobs = {}
        if self._video is not None:
            self._video.stop()

    def _on_resize(self, e):
        if e.width < 60 or e.height < 60:
            return
        self._after("resize", 180, lambda: self._resized(e.width, e.height))

    def _resized(self, w, h):
        if (w, h) == self.size:
            return
        self.size = (w, h)
        self._gen += 1
        if self._mode is None:
            self._start()
        elif self._mode == "slides":
            self._load(self.index, fade=False)
        elif self._mode == "video":
            self._video.set_size(w, h)
        else:
            self._draw_brand()

    def _start(self):
        self.items = collect(skip=self._bad)
        C.log(f"Slideshow login: {len(self.items)} karya dari {portfolio.root()}")
        if self.items:
            self._mode = "slides"
            self.config(cursor="hand2")
            self._next(fade=False)
            return
        if self._start_video():
            self._mode = "video"
            return
        self._mode = "brand"
        self._draw_brand()

    # --- slideshow portfolio -------------------------------------------------------------
    def skip(self):
        """Klik: langsung ke karya berikutnya (jadwal otomatis dimulai ulang)."""
        if self._mode != "slides" or len(self.items) < 2 or self._fading \
                or "poll" in self._jobs:      # sedang memuat / memudar: abaikan klik
            return
        for name in ("next",):
            job = self._jobs.pop(name, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._next(fade=True)

    def _next(self, fade=True):
        if not self.items:
            return
        self.index += 1
        if self.index >= len(self.items):   # satu putaran selesai: baca ulang (unggahan baru)
            self.items = collect(skip=self._bad) or self.items
            self.index = 0
        self._load(self.index, fade=fade)

    def _load(self, index, fade=True):
        item = self.items[index]
        w, h = self.size
        gen = self._gen

        def work():
            try:
                img = _open_image(item, w, h)
                out = (_finish(img, w, h, self.bg, rounded=self.host is None)
                       if img is not None else None)
            except Exception as exc:
                C.log(f"Slideshow: {item['path']!r} tidak bisa dibuka: {exc!r}")
                out = None
            with self._lock:
                self._ready = (gen, index, out, fade)

        threading.Thread(target=work, daemon=True).start()
        self._after("poll", 40, self._poll)

    def _poll(self):
        self._jobs.pop("poll", None)
        with self._lock:
            ready, self._ready = self._ready, None
        if ready is None:
            self._after("poll", 40, self._poll)
            return
        gen, index, img, fade = ready
        if gen != self._gen:            # ukuran berubah saat menyiapkan: siapkan ulang
            self._load(self.index, fade=False)
            return
        if img is None:                 # file rusak / video tak terbaca: lewati & ganti
            self._bad.add(self.items[index]["path"])
            self.items.pop(index)
            self.index -= 1
            if self.items:
                self._after("next", 50, self._next)
            else:
                self._start()
            return
        if fade and self.current is not None and self.current.size == img.size:
            self._fade(self.current, img, 1)
        else:
            self._show(img)
        self._after("next", C.SHOWCASE_SECONDS * 1000, self._next)

    def _fade(self, a, b, step):
        self._fading = step < FADE_STEPS
        Image = photos.Image
        t = step / FADE_STEPS
        self._set_photo(Image.blend(a, b, t * t * (3 - 2 * t)))   # halus di awal & akhir
        if step == FADE_STEPS // 2:
            self._caption()
        if step < FADE_STEPS:
            self._after("fade", FADE_MS, lambda: self._fade(a, b, step + 1))
        else:
            self.current = b

    def _show(self, img):
        self.current = img
        self._set_photo(img)
        self._caption()

    def _set_photo(self, img):
        if self.host is not None:
            self.host.frame(img)
            return
        try:
            self._photo = photos.to_photoimage(img)
            self.itemconfigure(self._img_item, image=self._photo)
        except Exception as exc:
            C.log(f"Slideshow gagal menampilkan gambar: {exc!r}")

    def _caption(self):
        if self.host is not None:
            if not self.items or not 0 <= self.index < len(self.items):
                self.host.caption("", "")
                return
            it = self.items[self.index]
            sub = _date(it["added"])
            if C.SHOWCASE_SHOW_NAMES and it.get("student"):
                sub = f"{it['student']}  ·  {sub}"
            self.host.caption(sub, f"{self.index + 1} / {len(self.items)}")
            return
        self.delete("caption")
        if not self.items or not 0 <= self.index < len(self.items):
            return
        it = self.items[self.index]
        w, h = self.size
        x, y = 34, h - 34
        sub = _date(it["added"])
        if C.SHOWCASE_SHOW_NAMES and it.get("student"):
            sub = f"{it['student']}  ·  {sub}"
        self.create_text(x, y, text=sub, anchor="sw", fill="#d9d6cd", font=(C.FONT, 10),
                         tags="caption")
        n = len(self.items)
        if n:
            self.create_text(w - 34, y, text=f"{self.index + 1} / {n}", anchor="se",
                             fill="#bdbab1", font=(C.FONT, 9), tags="caption")

    # --- cadangan 1: video latar login ---------------------------------------------------
    def _start_video(self):
        try:
            from elearning.ui import video_background as VB
        except Exception:
            return False
        path = VB.find_video(C.VIDEO_DIR)
        if not path or not VB.HAS_VIDEO:
            return False
        self._video = VB.VideoPlayer(path, dim=0.85, max_fps=24)   # cukup halus, lebih ringan
        self._video.set_size(*self.size)
        self._video.start()
        self._video_tick()
        return True

    def _video_tick(self):
        img = self._video.get_latest()
        if img is not None:
            w, h = img.size
            if (w, h) == self.size:
                self._set_photo(_finish(img, w, h, self.bg, shade=False,
                                        rounded=self.host is None))
        if self._video.failed:
            C.log(f"Video panel login gagal: {self._video.error}")
            self._mode = "brand"
            self._draw_brand()
            return
        self._after("video", 40, self._video_tick)

    # --- cadangan 2: panel brand polos -----------------------------------------------------
    def _draw_brand(self):
        if self.host is not None:
            self.host.frame(None)        # layar login menggambar panel brand sendiri
            self.host.caption("", "")
            return
        w, h = self.size
        self.delete("caption")
        p = I.pill(w, h, C.CARD, self.bg, r=RADIUS)
        self._photo = p
        self.itemconfigure(self._img_item, image=p)
        m = brand.mark(96, C.CARD)
        if m is not None:
            self.create_image(w / 2, h / 2 - 40, image=m, tags="caption")
        self.create_text(w / 2, h / 2 + 40, text="Karya murid akan tampil di sini",
                         fill=C.TEXT, font=(C.SERIF, 16), tags="caption")
        self.create_text(w / 2, h / 2 + 68,
                         text="Gambar & video portfolio yang diunggah murid berganti otomatis.",
                         fill=C.MUTED, font=(C.FONT, 10), tags="caption")
