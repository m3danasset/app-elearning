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
        self._base_item = self.create_image(0, 0, anchor="nw")
        self._band_item = self.create_image(0, 0, anchor="nw")
        self._imgs = {}
        self._player = None
        self._vlock = threading.Lock()
        self._vlast = None          # frame video terakhir (dipakai thread carousel)
        self._vshown = None
        self._vsize = None
        self.offset = (0, 0)        # geser sementara (tetap di tengah selama resize)
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
        """Ukuran jendela berubah: frame video lama disembunyikan sampai ukuran baru siap."""
        # frame terakhir diperbesar / diperkecil ke ukuran baru dan langsung dipakai, jadi
        # latar & pita tidak berkedip polos / hitam selama video menyiapkan ukuran baru
        last = self._vshown
        fill = None
        if last is not None and last.size != size:
            try:
                fill = last.resize(size, photos.Image.BILINEAR)
            except Exception:
                fill = None
        with self._vlock:
            self._vsize = size
            self._vlast = fill
        self._vshown = None
        if fill is not None:
            self.show_video(fill)
        elif last is None or last.size != size:
            self.itemconfigure(self._base_item, image="")
            self._imgs.pop("base", None)
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

    def show_video(self, img):
        if img is self._vshown:
            return
        self._vshown = img
        self._put("base", self._base_item, img)

    def show_band(self, img, y):
        self._put("band", self._band_item, img)
        ox, oy = self.offset
        self.coords(self._band_item, ox, int(y) + oy)

    def shift_to(self, ox, oy):
        """Latar & pita digeser (tanpa render ulang), mis. supaya tetap di tengah saat
        jendela berubah ukuran sebelum frame ukuran baru siap."""
        dx, dy = ox - self.offset[0], oy - self.offset[1]
        self.offset = (ox, oy)
        if dx or dy:
            self.move(self._base_item, dx, dy)
            self.move(self._band_item, dx, dy)

    def destroy(self):
        if self._player is not None:
            p, self._player = self._player, None
            p.stop()
            try:          # tunggu pembaca video selesai (keluar aplikasi tidak crash)
                p.join(timeout=0.6)
            except Exception:
                pass
        super().destroy()
