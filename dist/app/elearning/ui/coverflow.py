"""Slideshow 3D (coverflow) di layar login: 5 kartu karya murid, kartu tengah paling besar,
kartu samping lebih kecil, sedikit miring (perspektif), dan lebih redup.

- Berganti otomatis tiap config.SHOWCASE_SECONDS detik; klik kartu samping / panah < >
  untuk geser, klik kartu tengah = berikutnya.
- Gambar kartu untuk setiap langkah animasi disiapkan di thread terpisah (bentuk 3D lewat
  Image.transform PERSPECTIVE, tanpa ImageDraw), lalu diputar maks. 60 fps hanya dengan
  mengganti gambar & posisi item canvas (ringan).
- Kartu = gambar RGBA bersudut bulat dengan tepi transparan, langsung di atas video latar.
"""

import threading
import time
import tkinter as tk

from elearning import config as C
from elearning import photos, portfolio
from elearning.ui import showcase as SC
from elearning.ui import ui_icons as I

SLOTS = 2              # kartu di kiri & kanan kartu tengah (total 5)
FRAMES = 16            # langkah animasi geser yang disiapkan
DURATION = 0.28        # lama geser (detik); frame dipilih menurut waktu, maks. 60 fps
FRAME_MS = 16
RADIUS = 16
PAD = 3                # tepi transparan supaya sisi miring tetap halus
# per jarak dari tengah: (skala, geser x relatif lebar kartu, kecerahan, tepi luar dipendekkan)
LOOK = {0: (1.00, 0.00, 0.68, 0.00), 1: (0.80, 0.74, 0.54, 0.10), 2: (0.64, 1.30, 0.36, 0.14),
        3: (0.52, 1.72, 0.0, 0.16)}


def _lerp(a, b, t):
    return a + (b - a) * t


def _look(d):
    """Tampilan kartu pada jarak d (boleh pecahan) dari tengah: (skala, x, terang, miring)."""
    s = -1 if d < 0 else 1
    a = abs(d)
    i = min(int(a), 3)
    j = min(i + 1, 3)
    t = a - i
    sc, x, br, sk = (_lerp(LOOK[i][k], LOOK[j][k], t) for k in range(4))
    return sc, s * x, br, s * sk


def _solve(src, dst):
    """Koefisien Image.PERSPECTIVE yang memetakan titik keluaran (dst) ke sumber (src)."""
    m, v = [], []
    for (x, y), (u, w) in zip(dst, src):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); v.append(u)
        m.append([0, 0, 0, x, y, 1, -w * x, -w * y]); v.append(w)
    n = 8                                   # eliminasi Gauss kecil (tanpa numpy)
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        v[c], v[p] = v[p], v[c]
        for r in range(n):
            if r != c and m[c][c]:
                f = m[r][c] / m[c][c]
                m[r] = [a - f * b for a, b in zip(m[r], m[c])]
                v[r] -= f * v[c]
    return [v[i] / m[i][i] for i in range(n)]


class Coverflow:
    def __init__(self, canvas):
        self.cv = canvas
        self.items = []
        self.base = {}             # indeks -> gambar RGBA sudut bulat (ukuran kartu tengah)
        self.index = 0             # kartu di tengah
        self.geom = None           # (cx, cy, cw, ch)
        self.cards = {}            # indeks -> id item canvas
        self.photos = {}
        self._anim = None
        self._auto = None
        self._busy = False
        self._closed = False
        self._lock = threading.Lock()
        self._ready = None
        self._frames = {}          # arah (+1/-1) -> daftar frame [{indeks: (img, x, y)}]
        self._gen = 0
        self.on_change = None      # fn(): kartu tengah berganti (untuk keterangan)
        self.on_busy = None        # fn(bool): animasi geser mulai / selesai

    # --- data -----------------------------------------------------------------------
    def start(self):
        self.items = SC.collect(limit=10)
        C.log(f"Slideshow 3D login: {len(self.items)} karya")
        self._load_bases()

    def set_geometry(self, cx, cy, cw, ch):
        g = (int(cx), int(cy), int(cw), int(ch))
        if g == self.geom:
            return
        size_changed = self.geom is None or g[2:] != self.geom[2:]
        self.geom = g
        if size_changed:
            self._gen += 1
            self.base = {}
            self._frames = {}
            self._load_bases()
        else:
            self._draw_static()

    def _load_bases(self):
        if self.geom is None or not self.items:
            self._draw_static()
            return
        gen, (_cx, _cy, cw, ch) = self._gen, self.geom
        items = list(self.items)

        def work():
            out = {}
            for i, it in enumerate(items):
                try:
                    img = SC._open_image(it, cw, ch)
                except Exception as exc:
                    C.log(f"Slideshow 3D: {it['path']!r}: {exc!r}")
                    img = None
                if img is None:
                    img = photos.Image.new("RGB", (cw, ch), I._rgb(C.CARD))
                img = SC._finish(img, cw, ch, C.LOGIN_BG, shade=True, rounded=False)
                rgba = photos.Image.new("RGBA", (cw + 2 * PAD, ch + 2 * PAD), (0, 0, 0, 0))
                body = img.convert("RGBA")
                body.putalpha(I.round_mask(cw, ch, RADIUS))
                rgba.paste(body, (PAD, PAD))
                out[i] = rgba
            with self._lock:
                if gen == self._gen:
                    self.base = out
                    self._ready = gen

        self._ready = None
        threading.Thread(target=work, daemon=True).start()
        self._wait_bases(gen)

    def _wait_bases(self, gen):
        """Tunggu thread selesai (Tk hanya boleh dipanggil dari thread utama)."""
        if self._closed or gen != self._gen:
            return
        if self._ready != gen:
            self.cv.after(50, lambda: self._wait_bases(gen))
            return
        self._bases_ready()

    def _bases_ready(self):
        if self._closed:
            return
        self._draw_static()
        self._prepare_frames()
        self._schedule()

    # --- render satu kartu pada jarak d ----------------------------------------------
    def _render(self, i, d):
        src = self.base.get(i)
        if src is None:
            return None
        sc, xr, br, sk = _look(d)
        _cx, _cy, cw, ch = self.geom
        w, h = max(8, int(cw * sc)), max(8, int(ch * sc))
        img = src.resize((w + 2 * PAD, h + 2 * PAD), photos._RESAMPLE)
        if br < 0.999:
            rgb = img.convert("RGB")
            dark = photos.Image.new("RGB", img.size, I._rgb(C.LOGIN_BG))
            a = img.getchannel("A")
            img = photos.Image.blend(dark, rgb, max(0.0, br)).convert("RGBA")
            img.putalpha(a)
        if abs(sk) > 0.001:       # sisi luar lebih pendek: kesan kartu menghadap ke tengah
            W, H = img.size
            k = abs(sk) * H / 2
            if sk > 0:            # kartu kanan: tepi kanan dipendekkan
                dst = [(0, 0), (W, k), (W, H - k), (0, H)]
            else:
                dst = [(0, k), (W, 0), (W, H), (0, H - k)]
            src_pts = [(0, 0), (W, 0), (W, H), (0, H)]
            img = img.transform((W, H), photos.Image.PERSPECTIVE, _solve(src_pts, dst),
                                photos.Image.BICUBIC, fillcolor=(0, 0, 0, 0))
        return img, xr, sc

    def _layout_frame(self, center_pos):
        """Semua kartu terlihat untuk posisi tengah (pecahan) -> {indeks: (img, x, y)}."""
        n = len(self.items)
        cx, cy, cw, _ch = self.geom
        out = {}
        if n == 0:
            return out
        base = int(round(center_pos))
        for k in range(-SLOTS - 1, SLOTS + 2):
            i = base + k
            d = i - center_pos
            if abs(d) > SLOTS + 0.999 or (n < 2 * SLOTS + 1 and abs(k) > n // 2):
                continue
            r = self._render(i % n, d)
            if r is None:
                continue
            img, xr, _sc = r
            out[i] = (img, cx + xr * cw, cy)
        return out

    # --- animasi -----------------------------------------------------------------------------
    def _prepare_frames(self):
        """Siapkan frame geser maju & mundur di thread (kartu tengah saat ini sebagai awal)."""
        if not self.base or len(self.items) < 2:
            return
        start, gen = self.index, self._gen

        def work():
            res = {}
            for direction in (1, -1):
                frames = []
                for f in range(1, FRAMES + 1):
                    t = f / FRAMES
                    e = 1 - (1 - t) ** 3
                    frames.append(self._layout_frame(start + direction * e))
                res[direction] = frames
            with self._lock:
                if gen == self._gen and start == self.index:
                    self._frames = res

        threading.Thread(target=work, daemon=True).start()

    def move(self, direction):
        if self._busy or len(self.items) < 2 or self.geom is None:
            return
        with self._lock:
            frames = self._frames.get(direction)
        if not frames:            # belum siap: coba lagi sebentar lagi
            self.cv.after(60, lambda: self.move(direction))
            return
        self._busy = True
        self._cancel_auto()
        if self.on_busy:
            self.on_busy(True)    # video latar ditahan sebentar supaya geseran mulus
        if self.on_change:
            self.on_change(None)  # sembunyikan keterangan selama bergeser
        self._play(frames, direction, time.perf_counter(), -1)

    def _play(self, frames, direction, t0, last):
        """Frame dipilih berdasarkan waktu: kalau PC sedang sibuk, frame dilewati
        (durasi tetap sama, tidak melambat / patah-patah)."""
        if self._closed:
            return
        t = time.perf_counter()
        f = min(len(frames) - 1, int((t - t0) / DURATION * len(frames)))
        if f != last:
            self._show(frames[f])
        if f + 1 < len(frames):
            spent = int((time.perf_counter() - t) * 1000)
            self._anim = self.cv.after(max(1, FRAME_MS - spent),
                                       lambda: self._play(frames, direction, t0, f))
            return
        self._anim = None
        self.index = (self.index + direction) % len(self.items)
        with self._lock:
            self._frames = {}
        self._busy = False
        if self.on_busy:
            self.on_busy(False)
        # frame terakhir = susunan diam untuk kartu tengah baru (tidak dirender ulang)
        if self.on_change:
            self.on_change(self.items[self.index])
        self._prepare_frames()
        self._schedule()

    def _show(self, frame):
        """Ganti gambar & posisi item canvas; kartu dekat tengah di atas."""
        keep = set()
        order = sorted(frame.items(), key=lambda kv: -abs(kv[1][1] - self.geom[0]))
        for i, (img, x, y) in order:
            key = i
            ph = photos.to_photoimage(img)
            self.photos[key] = ph
            item = self.cards.get(key)
            if item is None:
                item = self.cv.create_image(x, y, image=ph, tags=("cover",))
                self.cards[key] = item
            else:
                self.cv.coords(item, x, y)
                self.cv.itemconfigure(item, image=ph, state="normal")
            self.cv.tag_raise(item)
            keep.add(key)
        for key in list(self.cards):
            if key not in keep:
                self.cv.delete(self.cards.pop(key))
                self.photos.pop(key, None)
        self.cv.tag_raise("over")        # logo / keterangan selalu di atas kartu

    def _draw_static(self):
        if self.geom is None:
            return
        if not self.items or not self.base:
            for key in list(self.cards):
                self.cv.delete(self.cards.pop(key))
            if self.on_change:
                self.on_change(None)
            return
        # kartu yang tampil dinamai ulang sesuai indeks baru (0 = tengah)
        for key in list(self.cards):
            self.cv.delete(self.cards.pop(key))
        self.photos = {}
        self._show(self._layout_frame(self.index))
        if self.on_change:
            self.on_change(self.items[self.index % len(self.items)])

    # --- otomatis & klik ---------------------------------------------------------------------
    def _schedule(self):
        self._cancel_auto()
        if not self._closed and len(self.items) > 1:
            self._auto = self.cv.after(C.SHOWCASE_SECONDS * 1000, lambda: self.move(1))

    def _cancel_auto(self):
        if self._auto is not None:
            try:
                self.cv.after_cancel(self._auto)
            except Exception:
                pass
            self._auto = None

    def click(self, x, y):
        """Klik di area kartu: kiri = mundur, kanan / tengah = maju. True kalau ditangani."""
        if self.geom is None or not self.items:
            return False
        cx, cy, cw, ch = self.geom
        if abs(y - cy) > ch / 2:
            return False
        if x < cx - cw / 2:
            self.move(-1)
        else:
            self.move(1)
        return True

    def hit(self, x, y):
        if self.geom is None or not self.items:
            return False
        cx, cy, cw, ch = self.geom
        return abs(y - cy) <= ch / 2 and abs(x - cx) <= cw * 1.9

    def close(self):
        self._closed = True
        self._cancel_auto()
        if self._anim is not None:
            try:
                self.cv.after_cancel(self._anim)
            except Exception:
                pass
