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


class LoginBackground(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, bg=C.LOGIN_BG, highlightthickness=0, bd=0,
                         takefocus=1)
        # Video latar dibagi dua: bagian di ATAS dan di BAWAH pita kartu (pita sudah berisi
        # video). Lebih sedikit piksel ditempel, dan tiap bagian ditempel di saat berbeda
        # dalam satu frame, supaya kartu carousel tetap tepat waktu (tidak patah-patah).
        self._base_item = self.create_image(0, 0, anchor="nw")
        self._bot_item = self.create_image(0, 0, anchor="nw")
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
            self.itemconfigure(self._base_item, image="")
            self.itemconfigure(self._bot_item, image="")
            self._imgs.pop("base", None)
            self._imgs.pop("bot", None)
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

    def show_video(self, img, now=True):
        """now=False: tempel menyusul (atas lalu bawah), setelah pita kartu tampil."""
        if img is self._vshown:
            return
        self._vshown = img
        self._vpending = img
        for j in self._vjobs:
            self.after_cancel(j)
        self._vjobs = []
        if now or self._band_y is None:
            self._paste_video("top")
            self._paste_video("bot")
            return
        # Di awal frame (setelah pita tampil), jauh dari jadwal frame berikutnya.
        self._vjobs = [self.after(1, self._paste_video, "top"),
                       self.after(max(2, C.UI_FRAME_MS // 3), self._paste_video, "bot")]

    def _paste_video(self, part):
        img = self._vpending
        if img is None:
            return
        W, H = img.size
        y0, y1 = self._band_y if self._band_y else (H, H)
        y0, y1 = max(0, min(H, y0)), max(0, min(H, y1))
        if part == "top":
            if y0 > 0:
                self._put("base", self._base_item, img.crop((0, 0, W, y0)))
            else:
                self.itemconfigure(self._base_item, image="")
                self._imgs.pop("base", None)
        else:
            if y1 < H:
                self._put("bot", self._bot_item, img.crop((0, y1, W, H)))
                self.coords(self._bot_item, 0, y1)
            else:
                self.itemconfigure(self._bot_item, image="")
                self._imgs.pop("bot", None)

    def show_band(self, img, y):
        self._put("band", self._band_item, img)
        self.coords(self._band_item, 0, int(y))
        band = (int(y), int(y) + img.size[1])
        if band != self._band_y:      # pita pindah / berubah tinggi: bagian video ikut
            self._band_y = band
            if self._vshown is not None:
                self._vpending = self._vshown
                self._paste_video("top")
                self._paste_video("bot")

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
