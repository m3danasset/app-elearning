"""Foto profil bulat; kalau murid belum punya foto, tampil lingkaran berisi inisial."""

import tkinter as tk

from elearning import config as C
from elearning import photos

PALETTE = ["#4a90e2", "#3fb68b", "#b06bff", "#ff5c93", "#ea7600", "#2fb5c9"]


def initials(name):
    words = [w for w in str(name).split() if w]
    return "".join(w[0] for w in words[:2]).upper() or "?"


class Avatar(tk.Canvas):
    """Foto bulat. 'bg' harus sama dengan warna latar induknya (tepi bulat transparan)."""

    def __init__(self, master, student_id="", name="", size=48, bg=C.CARD):
        super().__init__(master, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self.student_id = student_id
        self.name = name
        self.size = size
        self._bg = bg
        self._photo = None  # simpan referensi supaya gambar tidak hilang
        self.refresh()

    def set_student(self, student_id, name):
        self.student_id, self.name = student_id, name
        self.refresh()

    def refresh(self):
        """Gambar ulang (dipanggil setelah foto diganti/dihapus/nama diubah)."""
        self.delete("all")
        self._photo = None
        s = self.size
        color = PALETTE[sum(ord(c) for c in str(self.student_id)) % len(PALETTE)]

        # Lingkaran digambar sebagai gambar Pillow dengan tepi anti-alias
        # (oval bawaan Tk bergerigi / pixelated).
        has_photo = False
        try:
            rendered = photos.render_avatar(self.student_id, s, self._bg,
                                            fill=color, ring=C.BORDER)
            if rendered is not None:
                img, has_photo = rendered
                self._photo = photos.to_photoimage(img)
                self.create_image(s / 2, s / 2, image=self._photo)
        except Exception as exc:
            C.log(f"Gagal menggambar avatar {self.student_id}: {exc!r}")
            self._photo = None

        if self._photo is None:  # cadangan kalau Pillow/ImageTk tidak ada
            self.create_oval(1, 1, s - 1, s - 1, fill=color, outline=color)
            self.create_oval(1, 1, s - 1, s - 1, outline=C.BORDER, width=2)
        if not has_photo:
            self.create_text(s / 2, s / 2, text=initials(self.name), fill="white",
                             font=(C.FONT, max(8, int(s * 0.34)), "bold"))
