"""Carousel 3D di layar login: kartu karya murid berjajar melingkar (seperti dilihat dari
dalam sebuah silinder) dan terus berputar pelan tanpa henti (loop).

- Maks. 10 gambar (10 unggahan portfolio terbaru). Kalau gambar lebih sedikit dari kartu
  yang terlihat, gambar diulang. Belum ada portfolio: kartu polos warna lembut.
- Kartu tengah paling jauh (paling kecil), kartu di tepi lebih dekat & lebih tinggi.
  Bentuk 3D dihitung dengan Image.transform PERSPECTIVE (tanpa ImageDraw / numpy).
- Gambar per frame dibuat di 2 thread kerja (Pillow melepas GIL, jadi benar-benar paralel)
  hanya untuk pita kartu, sudah termasuk video latar, logo, dan kolom login. Thread utama
  cuma menempel satu gambar per frame -> layar tetap responsif.
- Maks. 30 fps dengan jadwal frame yang rata (frame disiapkan sedikit lebih dulu lalu
  ditampilkan tepat waktunya), gerak lambat. Tepi kiri & kanan memudar (fade).
  Saat di-minimize berhenti. Gerakan dihitung dari waktu, jadi kalau PC sedang sibuk
  kecepatan putar tetap sama (tidak melambat / patah-patah).
"""

import math
import sys
import threading
import time

from elearning import config as C
from elearning import photos
from elearning.ui import showcase as SC
from elearning.ui import ui_icons as I

MAX_ITEMS = 10
SPEED = 1 / 9.0          # gerak lambat: satu kartu bergeser tiap 9 detik
HALF = math.radians(11)  # setengah lebar sudut satu kartu
STEP = math.radians(24)  # jarak sudut antar kartu (sisanya = celah)
K = 0.6                  # posisi kamera di belakang pusat silinder (makin besar = makin datar)
ASPECT = 0.68            # lebar : tinggi kartu
BRIGHT = 0.78            # kartu sedikit diredupkan supaya logo & kolom login terbaca
RADIUS = 0.035           # sudut bulat (proporsi tinggi kartu)
PAD = 3                  # tepi transparan: sisi miring tetap halus (tidak bergerigi)
WORKERS = max(1, int(getattr(C, "WORKER_THREADS", 2)))   # dibatasi config (maks. 2)
FPS = max(10, min(30, int(getattr(C, "LOGIN_CAROUSEL_FPS", 30))))   # maks. 30 fps
# Jadwal frame di kisi 2x FPS (60): frame dibuat tiap DIVS langkah = 30 / 20 / 15 / 10 fps,
# selalu rata. Layar besar (2560x1440) yang tidak sanggup 30 tetap mulus di 20 fps.
GRID = 2 * FPS
DIVS = (2, 3, 4, 6)
LEAD = 0.12              # frame disiapkan maks. sekian detik sebelum tampil
FADE = 0.22              # lebar fade tepi kiri & kanan (proporsi lebar layar)
PLACEHOLDER = ("#4a5866", "#617d66", "#8d957a", "#83a09a", "#949a7b", "#5d6c7d")


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


class Geo:
    """Ukuran & posisi untuk satu ukuran jendela (tidak diubah setelah dibuat)."""

    def __init__(self, W, H, cy, ch, extra=()):
        self.W, self.H = int(W), int(H)
        self.cx = W / 2
        self.ch = ch
        z0 = math.cos(HALF) + K
        self.B = ch / 2 * z0                         # tinggi setengah kartu x kedalaman
        self.A = ASPECT * ch / 2 * z0 / math.sin(HALF)
        hmax = ch / 2
        for deg in range(0, 86):                     # kartu tertinggi yang masih di layar
            p = math.radians(deg)
            z = math.cos(p) + K
            if self.A * math.sin(p) / z > W / 2 + 4:
                break
            hmax = max(hmax, self.B / z)
        top, bot = cy - hmax - PAD, cy + hmax + PAD
        for y0, y1 in extra:                         # logo / kolom login ikut di pita
            top, bot = min(top, y0), max(bot, y1)
        self.y0 = max(0, int(top))
        self.y1 = min(self.H, int(math.ceil(bot)))
        self.cyb = cy - self.y0
        self.bh = self.y1 - self.y0
        self.key = (self.W, self.H, int(cy), int(ch), self.y0, self.y1)


def render(geo, tex, phase, band, overlays):
    """Gambar semua kartu yang terlihat ke `band` (RGB, ukuran pita), lalu overlay."""
    n = len(tex)
    fw = int(geo.W * FADE)
    if fw > 2:      # latar asli tepi kiri & kanan (untuk fade)
        left = band.crop((0, 0, fw, geo.bh))
        right = band.crop((geo.W - fw, 0, geo.W, geo.bh))
    if n:
        W, bh, cx, cyb, A, B = geo.W, geo.bh, geo.cx, geo.cyb, geo.A, geo.B
        base = math.floor(phase)
        for g in range(base - 3, base + 5):
            th = (g - phase) * STEP
            p1, p2 = th - HALF, th + HALF
            z1, z2 = math.cos(p1) + K, math.cos(p2) + K
            if z1 < 0.25 or z2 < 0.25:
                continue
            x1, x2 = cx + A * math.sin(p1) / z1, cx + A * math.sin(p2) / z2
            if x2 - x1 < 3 or x2 < -2 or x1 > W + 2:
                continue
            h1, h2 = B / z1, B / z2
            ox, ex = max(0, int(x1) - 2), min(W, int(x2) + 3)
            oy = max(0, int(cyb - max(h1, h2)) - 2)
            ey = min(bh, int(cyb + max(h1, h2)) + 3)
            if ex <= ox or ey <= oy:
                continue
            src = tex[g % n]
            sw, sh = src.size
            dst = [(x1 - ox, cyb - h1 - oy), (x2 - ox, cyb - h2 - oy),
                   (x2 - ox, cyb + h2 - oy), (x1 - ox, cyb + h1 - oy)]
            s = [(PAD, PAD), (sw - PAD, PAD), (sw - PAD, sh - PAD), (PAD, sh - PAD)]
            img = src.transform((ex - ox, ey - oy), photos.Image.PERSPECTIVE, _solve(s, dst),
                                photos.Image.BILINEAR)
            band.paste(img, (ox, oy), img)
    if fw > 2:
        mask = _fade_mask(fw, geo.bh)
        band.paste(left, (0, 0), mask)
        band.paste(right, (geo.W - fw, 0), mask.transpose(0))
    for ov, x, y in overlays:
        band.paste(ov, (x, y), ov)
    return band


_masks = {}


def _fade_mask(w, h):
    """Masker L: 255 di tepi kiri -> 0 ke dalam (halus, ease)."""
    m = _masks.get((w, h))
    if m is None:
        Image = photos.Image
        row = Image.new("L", (w, 1))
        row.putdata([int(255 * (1 - t) ** 2) for t in (i / max(1, w - 1) for i in range(w))])
        m = row.resize((w, h))
        _masks.clear()
        _masks[(w, h)] = m
    return m


def _texture(img, tw, th):
    """Kartu RGBA: diredupkan, sudut bulat, tepi transparan PAD."""
    Image = photos.Image
    dark = Image.new("RGB", img.size, I._rgb(C.LOGIN_BG))
    img = Image.blend(dark, img.convert("RGB"), BRIGHT).convert("RGBA")
    img.putalpha(I.round_mask(tw, th, max(4, int(th * RADIUS))))
    out = Image.new("RGBA", (tw + 2 * PAD, th + 2 * PAD), (0, 0, 0, 0))
    out.paste(img, (PAD, PAD))
    # warna "premultiplied": transform tidak perlu konversi bolak-balik tiap frame (lebih cepat)
    return out.convert("RGBa")


def _timer_res(on):
    """Timer Windows 1 ms selama carousel jalan (default ~15,6 ms membuat jarak frame tidak
    rata: 31 / 47 ms). Dikembalikan saat layar login ditutup."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        winmm = ctypes.windll.winmm
        (winmm.timeBeginPeriod if on else winmm.timeEndPeriod)(1)
    except Exception as exc:
        C.log(f"Carousel 3D: timer 1 ms tidak bisa diatur: {exc!r}")


class Carousel3D:
    def __init__(self, bg):
        """bg = LoginBackground (canvas dengan item video & item pita)."""
        self.bg = bg
        self.items = []
        self.geo = None
        self.tex = []              # gambar kartu RGBA (dipakai semua ukuran jendela)
        self._tex_h = 0
        self._tex_loading = None
        self._ov_band = ()         # overlays dalam koordinat pita (untuk thread)
        self._lock = threading.Lock()
        self._frames = {}          # nomor frame -> (k, geo, gambar, frame video)
        self._k_next = 0
        # PC lambat (render > waktu frame): hanya frame kelipatan _div yang dibuat, jadi
        # 30 -> 15 -> 10 fps tapi TETAP rata (lebih mulus daripada frame terlewat acak).
        self._div = DIVS[0]
        self._cost = 0.0           # rata-rata waktu render satu frame (detik)
        self._paused = False
        self._stop = threading.Event()
        self._t0 = time.perf_counter()
        self._shown_key = None
        self._ticks = 0
        self._after = None
        self._solid = {}           # key -> pita warna polos (tanpa video)
        self._threads = []
        self.last_input = time.perf_counter()   # diperbarui layar login (ketik / gerak mouse)

    # --- mulai / berhenti ------------------------------------------------------------
    def start(self):
        _timer_res(True)
        self.items = SC.collect(limit=MAX_ITEMS)
        C.log(f"Carousel 3D login: {len(self.items)} karya")
        for _ in range(WORKERS):
            t = threading.Thread(target=self._work, daemon=True)
            t.start()
            self._threads.append(t)
        self._tick()

    def close(self):
        if not self._stop.is_set():
            _timer_res(False)
        self._stop.set()
        for t in self._threads:      # frame yang sedang dibuat diselesaikan dulu (maks. sebentar)
            try:
                t.join(timeout=0.3)
            except Exception:
                pass
        self._threads = []
        if self._after is not None:
            try:
                self.bg.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

    # --- tata letak (thread utama) ---------------------------------------------------------
    def configure(self, W, H, cy, ch, overlays, extra):
        geo = Geo(W, H, cy, ch, extra)
        same = self.geo is not None and geo.key == self.geo.key
        if same:
            geo = self.geo
        ov = tuple((img, int(x), int(y) - geo.y0) for img, x, y in overlays)
        if same and [(id(a), b, c) for a, b, c in ov] == \
                [(id(a), b, c) for a, b, c in self._ov_band]:
            return
        with self._lock:
            self.geo = geo
            self._ov_band = ov
            if not same:
                self._frames = {}
        self._ensure_textures(geo)
        if same:
            return
        self.bg.reset_video((geo.W, geo.H))
        # frame pertama ukuran baru dibuat langsung: tidak ada sisa pita ukuran lama.
        # Latar pita = frame video (sementara: frame lama yang diskalakan), sama dengan latar layar.
        vframe = self.bg.video_frame()
        self._display(time.perf_counter(), geo, render(geo, list(self.tex), self._phase(),
                                                        self._band_bg(geo, vframe), ov), vframe)

    def _phase(self, t=None):
        return ((t or time.perf_counter()) - self._t0) * SPEED

    def _band_bg(self, geo, vframe):
        if vframe is not None and vframe.size == (geo.W, geo.H):
            return vframe.crop((0, geo.y0, geo.W, geo.y1))
        solid = self._solid.get(geo.key)
        if solid is None:
            self._solid = {geo.key: photos.Image.new("RGB", (geo.W, max(1, geo.bh)),
                                                      I._rgb(C.LOGIN_BG))}
            solid = self._solid[geo.key]
        return solid.copy()

    def _ensure_textures(self, geo):
        """Gambar kartu dibuat ulang hanya kalau ukurannya jauh berbeda."""
        th = int(geo.ch * 1.2)
        if self.tex and 0.7 * self._tex_h <= th <= 1.15 * self._tex_h:
            return
        if self._tex_loading == th:
            return
        self._tex_loading = th
        tw = int(th * ASPECT)
        items = list(self.items)

        def work():
            Image = photos.Image
            out = []
            for it in items:
                try:
                    img = SC._open_image(it, tw, th)
                except Exception as exc:
                    C.log(f"Carousel 3D: {it['path']!r}: {exc!r}")
                    img = None
                if img is not None:
                    out.append(_texture(img, tw, th))
            if not out:            # belum ada karya: kartu polos warna lembut
                out = [_texture(Image.new("RGB", (tw, th), I._rgb(c)), tw, th)
                       for c in PLACEHOLDER]
            with self._lock:
                if self._tex_loading == th:
                    self.tex = out
                    self._tex_h = th
                    self._tex_loading = None

        threading.Thread(target=work, daemon=True).start()

    # --- thread kerja --------------------------------------------------------------------
    # Frame dibuat untuk waktu tetap  T_k = t0 + k / FPS  (jadwal rata), beberapa frame di
    # depan waktu sekarang; thread utama menampilkan frame k tepat pada waktunya.
    def _T(self, k):
        return self._t0 + k / GRID

    def _work(self):
        while not self._stop.is_set():
            with self._lock:
                geo, ov, tex = self.geo, self._ov_band, self.tex
                ready = geo is not None and not self._paused and geo.bh > 0
                if ready:
                    now_k = int((time.perf_counter() - self._t0) * GRID)
                    d = self._div
                    k = max(self._k_next, now_k + 1)
                    k = -(-k // d) * d                      # kelipatan d berikutnya
                    self._k_next = k + d
            if not ready:
                self._stop.wait(0.05)
                continue
            wait = self._T(k) - LEAD - time.perf_counter()
            if wait > 0 and self._stop.wait(wait):
                return
            try:
                t_r = time.perf_counter()
                vframe = self.bg.video_frame()
                img = render(geo, tex, self._phase(self._T(k)), self._band_bg(geo, vframe), ov)
                self._adapt(time.perf_counter() - t_r)
            except Exception as exc:
                C.log(f"Carousel 3D gagal menggambar: {exc!r}")
                self._stop.wait(0.5)
                continue
            with self._lock:
                if geo is self.geo:
                    self._frames[k] = (k, geo, img, vframe)

    def _adapt(self, cost):
        """Atur _div dari rata-rata waktu render (beberapa worker bergantian membuat frame)."""
        with self._lock:
            self._cost = cost if self._cost == 0 else self._cost * 0.9 + cost * 0.1
            budget = WORKERS / GRID            # waktu per langkah kisi untuk semua worker
            i = DIVS.index(self._div)
            if self._cost > self._div * budget * 0.85 and i + 1 < len(DIVS):
                self._div = DIVS[i + 1]
                C.log(f"Carousel 3D: render {self._cost * 1000:.0f} ms -> "
                      f"{GRID // self._div} fps rata")
            elif i > 0 and self._cost < DIVS[i - 1] * budget * 0.6:
                self._div = DIVS[i - 1]

    # --- thread utama: tempel frame pada waktunya ----------------------------------------
    def _tick(self):
        if self._stop.is_set():
            return
        self._ticks += 1
        if self._ticks % 15 == 1:
            try:
                iconic = self.bg.winfo_toplevel().state() == "iconic"
            except Exception:
                return
            with self._lock:
                if iconic != self._paused:
                    self._frames = {}
                self._paused = iconic
        now = time.perf_counter()
        kd = int((now - self._t0) * GRID)
        out = None
        with self._lock:
            ready = [k for k in self._frames if k <= kd]
            if ready:
                out = self._frames[max(ready)]
                for k in ready:
                    del self._frames[k]
        if out is not None and out[1] is self.geo:
            self._display(*out)
        if self._paused:
            delay = 200
        else:
            d = self._div                      # bangun tepat di frame berikutnya (kelipatan d)
            nxt = (kd // d + 1) * d
            delay = max(1, int((self._T(nxt) - time.perf_counter()) * 1000) + 1)
        self._after = self.bg.after(delay, self._tick)

    def _display(self, _t, geo, img, vframe):
        try:
            self.bg.show_band(img, geo.y0)        # kartu dulu, tepat waktu
            if vframe is not None:
                self.bg.show_video(vframe, now=False,   # video latar menyusul dalam frame ini
                                   period_ms=1000.0 * self._div / GRID)
        except Exception as exc:       # canvas sudah ditutup
            C.log(f"Carousel 3D: {exc!r}")
