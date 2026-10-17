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
    """Ukuran & posisi untuk satu ukuran jendela (tidak diubah setelah dibuat).

    rows3=True: + baris kartu di ATAS dan di BAWAH baris utama, di SILINDER YANG SAMA (ukuran
    kartu sama, digeser vertikal di ruang 3D -> tepinya ikut melengkung oleh perspektif),
    bergerak berlawanan arah. Sebagian terpotong tepi layar.
    self.rows = [(cyb, B, half, step, arah, set tekstur, geser vertikal)]"""

    def __init__(self, W, H, cy, ch, extra=(), rows3=False):
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
        rows = [(cy, self.B, HALF, STEP, 1, 0, 0.0)]
        self.rows3 = bool(rows3)
        if rows3:
            off = 2 * self.B * 1.055                     # tinggi kartu + celah (~5.5 %)
            rows.append((cy, self.B, HALF, STEP, -1, 1, -off))   # baris atas
            rows.append((cy, self.B, HALF, STEP, -1, 2, off))    # baris bawah
            top, bot = 0, H                              # tiga baris menutup seluruh layar
        for y0, y1 in extra:                         # logo / kolom login ikut di pita
            top, bot = min(top, y0), max(bot, y1)
        self.y0 = max(0, int(top))
        self.y1 = min(self.H, int(math.ceil(bot)))
        self.cyb = cy - self.y0
        self.bh = self.y1 - self.y0
        self.rows = [(c - self.y0, b, hf, st, d, t, o) for c, b, hf, st, d, t, o in rows]
        self.key = (self.W, self.H, int(cy), int(ch), self.y0, self.y1, len(self.rows))


def render(geo, texsets, phase, band, overlays):
    """Gambar semua kartu yang terlihat ke `band` (RGB, ukuran pita), lalu overlay.
    texsets: [tekstur baris utama, tekstur baris atas, tekstur baris bawah] (sesuai geo.rows)."""
    fw = int(geo.W * FADE)
    if fw > 2:      # latar asli tepi kiri & kanan (untuk fade)
        left = band.crop((0, 0, fw, geo.bh))
        right = band.crop((geo.W - fw, 0, geo.W, geo.bh))
    for cyb, B, half, step, direction, t, off in geo.rows:
        tex = texsets[t] if t < len(texsets) and texsets[t] else (texsets[0] if texsets else [])
        if tex:     # baris atas & bawah: berlawanan arah, bergeser setengah kartu
            _render_row(geo, tex, phase * direction + (0.5 if t else 0.0), band, cyb, B, half,
                        step, off)
    if fw > 2:
        mask = _fade_mask(fw, geo.bh)
        band.paste(left, (0, 0), mask)
        band.paste(right, (geo.W - fw, 0), mask.transpose(0))
    for ov, x, y in overlays:
        band.paste(ov, (x, y), ov)
    return band


SLICE_PX = 64      # lebar maks. satu irisan kartu (px): tepi kartu melengkung halus


def _render_row(geo, tex, phase, band, cyb, B, half, step, off=0.0):
    """Satu baris kartu di silinder (radius = geo.A, lebar sudut kartu = half). off = geser
    vertikal di ruang 3D (baris atas / bawah): y layar = cyb + (off -+ B) / z.

    Kartu ikut MELENGKUNG di permukaan silinder: tiap kartu dibagi irisan vertikal tipis
    (maks. SLICE_PX), tiap irisan diproyeksikan dari sudutnya sendiri -> tepi atas/bawah kartu
    dan celah antar baris membentuk busur halus (dulu satu trapesium bertepi lurus). Semua
    irisan mengambil sampel dari tekstur utuh, jadi sambungan antar irisan tidak bercelah."""
    n = len(tex)
    if not n:
        return
    W, bh, cx, A = geo.W, geo.bh, geo.cx, geo.A
    Image = photos.Image
    span = int(math.radians(88) / step) + 2          # kartu terlihat sampai ~88 derajat
    base = math.floor(phase * STEP / step)
    ph = phase * STEP / step
    for g in range(base - span, base + span + 1):
        th = (g - ph) * step
        p1, p2 = th - half, th + half
        z1, z2 = math.cos(p1) + K, math.cos(p2) + K
        if z1 < 0.25 or z2 < 0.25:
            continue
        x1, x2 = cx + A * math.sin(p1) / z1, cx + A * math.sin(p2) / z2
        if x2 - x1 < 3 or x2 < -2 or x1 > W + 2:
            continue
        # cepat: seluruh kartu di luar layar secara vertikal (baris atas / bawah)
        zmin, zmax = min(z1, z2, math.cos(th) + K), max(z1, z2, math.cos(th) + K)
        top_hi = cyb + min((off - B) / zmin, (off - B) / zmax)
        bot_lo = cyb + max((off + B) / zmin, (off + B) / zmax)
        if bot_lo < 0 or top_hi > bh:
            continue
        src = tex[g % n]
        sw, sh = src.size
        k = max(2, min(12, int(math.ceil((x2 - x1) / SLICE_PX))))
        pts = []
        for i in range(k + 1):                       # titik tepi tiap irisan di silinder
            a = p1 + (p2 - p1) * i / k
            z = math.cos(a) + K
            pts.append((cx + A * math.sin(a) / z, cyb + (off - B) / z, cyb + (off + B) / z,
                        PAD + (sw - 2 * PAD) * i / k))
        for i in range(k):
            xa, ta, ba, ua = pts[i]
            xb, tb, bb, ub = pts[i + 1]
            ox = int(math.floor(xa)) - (2 if i == 0 else 0)
            ex = int(math.floor(xb)) + (3 if i == k - 1 else 0)
            ox, ex = max(0, ox), min(W, ex)
            oy = max(0, int(min(ta, tb)) - 2)
            ey = min(bh, int(max(ba, bb)) + 3)
            if ex <= ox or ey <= oy:
                continue
            dst = [(xa - ox, ta - oy), (xb - ox, tb - oy), (xb - ox, bb - oy), (xa - ox, ba - oy)]
            s = [(ua, PAD), (ub, PAD), (ub, sh - PAD), (ua, sh - PAD)]
            img = src.transform((ex - ox, ey - oy), Image.PERSPECTIVE, _solve(s, dst),
                                Image.BILINEAR)
            band.paste(img, (ox, oy), img)


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
        self.tex = []              # [tekstur baris utama, atas, bawah] (RGBA per kartu)
        try:                       # Panel Admin > Setting: baris atas & bawah (30 portfolio)
            from elearning import app_settings
            self.rows3 = bool(app_settings.get("login_carousel_rows3"))
        except Exception:
            self.rows3 = False
        self._tex_h = 0
        self._tex_key = (0, 0, 0)
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
        self.items = SC.collect(limit=MAX_ITEMS * (3 if self.rows3 else 1))
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
        geo = Geo(W, H, cy, ch, extra, rows3=self.rows3)
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
        self._display(time.perf_counter(), geo, render(geo, [list(t) for t in self.tex],
                                                        self._phase(),
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
        """Gambar kartu dibuat ulang hanya kalau ukurannya jauh berbeda. Baris atas & bawah
        (setting rows3): ukuran kartu sama, 10 karya lain per baris."""
        th = int(geo.ch * 1.2)
        th2 = th if geo.rows3 else 0                      # baris atas & bawah: ukuran sama
        want_sets = 3 if th2 else 1
        want = (th, th2, 0)
        if self.tex and len(self.tex) == want_sets and                 0.7 * self._tex_h <= th <= 1.15 * self._tex_h and                 (not th2 or self._tex_key[1:] == want[1:]):
            return
        if self._tex_loading == want:
            return
        self._tex_loading = want
        items = list(self.items)

        def groups():
            if want_sets == 1:
                return [(items[:MAX_ITEMS], th)]
            out = []
            for k in range(3):        # utama, atas, bawah: masing-masing 10 karya berbeda
                part = items[k * MAX_ITEMS:(k + 1) * MAX_ITEMS]
                if not part and items:            # karya kurang dari 30: putar ulang
                    part = items[k * 3 % len(items):] + items[:k * 3 % len(items)]
                    part = part[:MAX_ITEMS]
                out.append((part, th if k == 0 else th2))
            return out

        def work():
            Image = photos.Image
            sets = []
            for part, h in groups():
                tw = int(h * ASPECT)
                out = []
                for it in part:
                    try:
                        img = SC._open_image(it, tw, h)
                    except Exception as exc:
                        C.log(f"Carousel 3D: {it['path']!r}: {exc!r}")
                        img = None
                    if img is not None:
                        out.append(_texture(img, tw, h))
                if not out:        # belum ada karya: kartu polos warna lembut
                    out = [_texture(Image.new("RGB", (tw, h), I._rgb(c)), tw, h)
                           for c in PLACEHOLDER]
                sets.append(out)
            with self._lock:
                if self._tex_loading == want:
                    self.tex = sets
                    self._tex_h = th
                    self._tex_key = want
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
            elif i > 0 and self._cost < DIVS[i - 1] * budget * 0.75:   # naik lagi (jeda 75-85 %)
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
