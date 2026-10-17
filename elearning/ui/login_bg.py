"""Latar layar login: SATU canvas berisi video latar (opacity rendah, opsional) dan pita
carousel 3D (carousel3d.py). Teks kolom login digambar sebagai teks canvas di atasnya.

Video: taruh .mp4 di  assets\\video\\login\\  (tanpa video: latar polos seperti biasa).
Dibaca & dicampur di thread terpisah (maks. 12 fps). Frame video yang sama dipakai untuk
latar pita kartu, jadi tidak ada sambungan / garis di tepi pita.
"""

import os
import threading
import tkinter as tk

from elearning import config as C
from elearning import photos
from elearning.ui import ui_icons as I

LOGIN_VIDEO_DIR = os.path.join(C.APP_DIR, "assets", "video", "login")
OPACITY = getattr(C, "LOGIN_VIDEO_OPACITY", 0.22)
FPS = 12
STRIP = 160          # tinggi maks. satu strip video latar (baris)


class LoginBackground(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, bg=C.LOGIN_BG, highlightthickness=0, bd=0,
                         takefocus=1)
        # Video latar = bagian di ATAS dan di BAWAH pita kartu (pita sudah berisi video),
        # dipotong jadi strip tipis (maks. STRIP baris). Strip ditempel satu per satu, disebar
        # sepanjang frame: tidak pernah ada satu tempelan besar yang menahan frame kartu
        # (penting di 2560x1440, satu tempelan penuh bisa > 30 ms).
        self._strips = []           # [(item, y0, y1)]
        self._strip_key = None      # (lebar, tinggi, pita) saat strip dibuat
        self._band_y = None         # (y0, y1) pita kartu terakhir
        self._vpending = None       # frame video yang menunggu ditempel
        self._vjobs = []
        self._band_item = self.create_image(0, 0, anchor="nw")
        self._imgs = {}
        self._player = None
        self._vlock = threading.Lock()
        self._vlast = None          # frame video terakhir (dipakai thread carousel)
        self._vshown = None
        self._vsize = None
        try:
            from elearning.ui import video_background as VB
            path = VB.find_video(LOGIN_VIDEO_DIR)
            if path and VB.HAS_VIDEO:
                self._player = self._make_player(VB, path)
                C.log(f"Video latar login: {path}")
        except Exception as exc:
            C.log(f"Video latar login tidak dipakai: {exc!r}")

    @staticmethod
    def _make_player(VB, path):
        Image = photos.Image
        bg = I._rgb(C.LOGIN_BG)

        class P(VB.VideoPlayer):
            def _prepare(self_, frame):
                img = VB.VideoPlayer._prepare(self_, frame)
                return Image.blend(Image.new("RGB", img.size, bg), img, OPACITY)

        p = P(path, dim=1.0, max_fps=FPS)
        p.start()
        return p

    # --- video (dipanggil thread carousel) --------------------------------------------------
    def video_frame(self):
        p = self._player
        if p is None:
            return None
        if p.failed:
            return None
        img = p.get_latest()
        with self._vlock:
            if img is not None and img.size == self._vsize:
                self._vlast = img
            return self._vlast

    # --- thread utama ------------------------------------------------------------------------
    def reset_video(self, size):
        """Ukuran jendela berubah: frame video terakhir diskalakan ke ukuran baru dan dipakai
        sampai pembaca video menghasilkan frame ukuran baru (latar tidak sempat kosong/berkedip)."""
        with self._vlock:
            old = self._vlast
        stand_in = None
        if old is not None:
            try:
                stand_in = old.resize(size, photos.Image.BILINEAR)
            except Exception:
                stand_in = None
        with self._vlock:
            self._vsize = size
            self._vlast = stand_in
        self._vshown = None
        if stand_in is not None:
            self.show_video(stand_in)
        else:
            for item, _a, _b in self._strips:
                self.itemconfigure(item, image="")
        p = self._player
        if p is not None:
            if p.failed:
                C.log(f"Video latar login gagal: {p.error}")
                p.stop()
                self._player = None
            else:
                p.set_size(*size)

    def _put(self, name, item, img):
        """Gambar ukuran sama: isi foto lama ditimpa (lebih ringan daripada membuat baru)."""
        ph = self._imgs.get(name)
        if ph is not None and (ph.width(), ph.height()) == img.size:
            ph.paste(img)
            return
        self._imgs[name] = photos.to_photoimage(img)
        self.itemconfigure(item, image=self._imgs[name])

    def _layout_strips(self, size):
        """Buat ulang item strip kalau ukuran video / posisi pita berubah."""
        W, H = size
        y0, y1 = self._band_y if self._band_y else (H, H)
        y0, y1 = max(0, min(H, y0)), max(0, min(H, y1))
        key = (W, H, y0, y1)
        if key == self._strip_key:
            return
        self._strip_key = key
        for item, _a, _b in self._strips:
            self.delete(item)
        for name in [n for n in self._imgs if n.startswith("v")]:
            self._imgs.pop(name, None)
        self._strips = []
        for a, b in ((0, y0), (y1, H)):
            while a < b:
                c = min(b, a + STRIP)
                item = self.create_image(0, a, anchor="nw")
                self.tag_lower(item, self._band_item)
                self._strips.append((item, a, c))
                a = c

    def show_video(self, img, now=True, period_ms=None):
        """now=False: strip ditempel menyusul, disebar dalam period_ms (setelah pita tampil)."""
        if img is self._vshown:
            return
        self._vshown = img
        self._vpending = img
        for j in self._vjobs:
            self.after_cancel(j)
        self._vjobs = []
        self._layout_strips(img.size)
        if now or self._band_y is None:
            for i in range(len(self._strips)):
                self._paste_strip(i)
            return
        n = len(self._strips)
        span = 0.6 * (period_ms or C.UI_FRAME_MS)      # sisakan akhir frame untuk frame berikut
        step = span / max(1, n)
        self._vjobs = [self.after(1 + int(i * step), self._paste_strip, i) for i in range(n)]

    def _paste_strip(self, i):
        img = self._vpending
        if img is None or i >= len(self._strips):
            return
        item, a, b = self._strips[i]
        if b > img.size[1]:
            return
        self._put(f"v{i}", item, img.crop((0, a, img.size[0], b)))

    def show_band(self, img, y):
        self._put("band", self._band_item, img)
        self.coords(self._band_item, 0, int(y))
        band = (int(y), int(y) + img.size[1])
        if band != self._band_y:      # pita pindah / berubah tinggi: strip video ikut
            self._band_y = band
            if self._vshown is not None:
                self._vpending = self._vshown
                self._layout_strips(self._vshown.size)
                for i in range(len(self._strips)):
                    self._paste_strip(i)

    def destroy(self):
        for j in self._vjobs:
            try:
                self.after_cancel(j)
            except Exception:
                pass
        self._vjobs = []
        if self._player is not None:
            p, self._player = self._player, None
            p.stop()
            try:          # tunggu pembaca video selesai (keluar aplikasi tidak crash)
                p.join(timeout=0.6)
            except Exception:
                pass
        super().destroy()
