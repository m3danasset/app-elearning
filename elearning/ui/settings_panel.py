"""Panel Admin > Setting: pengaturan aplikasi (data\\app_settings.json, lihat app_settings.py).

Tampilan login: tiga pilihan (radio) di satu kartu bersudut bulat. Disimpan langsung saat
pilihan diklik; berlaku saat layar login dibuka berikutnya.
"""

import tkinter as tk

from elearning import app_settings
from elearning import config as C
from elearning.ui import ui_icons as I
from elearning.ui.controls import RoundPanel

LOGIN_OPTIONS = (
    ("carousel", "Carousel + video latar",
     "Carousel 3D satu baris (10 portfolio) di atas video latar. Paling ringan."),
    ("rows3", "Carousel 3 baris, tanpa video latar",
     "Tiga baris kartu bertumpuk (30 portfolio), baris atas & bawah bergerak berlawanan arah. "
     "Paling berat: di PC lambat / layar besar carousel otomatis turun fps supaya tetap rata."),
    ("video", "Video latar saja",
     "Tanpa carousel: hanya video latar, logo, dan kolom login."),
)


class SettingsPanel(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C.BG)
        self._imgs = []
        self._rows = {}
        panel = RoundPanel(self, padx=4, pady=2)
        panel.pack(fill="x", pady=4)
        box = tk.Frame(panel.inner, bg=C.CARD, padx=16, pady=12)
        box.pack(fill="x")
        tk.Label(box, text="Tampilan login", bg=C.CARD, fg=C.TEXT, font=(C.FONT, 12, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(box, text="Berlaku saat layar login dibuka berikutnya.", bg=C.CARD,
                 fg=C.MUTED, font=(C.FONT, 9), anchor="w").pack(fill="x", pady=(2, 8))
        for key, title, desc in LOGIN_OPTIONS:
            row = tk.Frame(box, bg=C.CARD, cursor="hand2")
            row.pack(fill="x", pady=4)
            dot = tk.Canvas(row, width=18, height=18, bg=C.CARD, highlightthickness=0, bd=0)
            dot.pack(side="left", anchor="n", padx=(0, 12), pady=(2, 0))
            text = tk.Frame(row, bg=C.CARD)
            text.pack(side="left", fill="x", expand=True)
            t = tk.Label(text, text=title, bg=C.CARD, fg=C.TEXT, font=(C.FONT, 10, "bold"),
                         anchor="w")
            t.pack(fill="x")
            d = tk.Label(text, text=desc, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 9), anchor="w",
                         justify="left", wraplength=640)
            d.pack(fill="x")
            for w in (row, dot, text, t, d):
                w.bind("<Button-1>", lambda e, k=key, ti=title: self._choose(k, ti))
            self._rows[key] = (dot, t)
        self.msg = tk.Label(self, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 9), anchor="w")
        self.msg.pack(fill="x", pady=(8, 0))
        self._paint(app_settings.login_mode())

    def _paint(self, current):
        """Lingkaran pilihan (antialias): oranye + titik putih = dipilih, cincin abu = tidak."""
        self._imgs = []
        for key, (dot, title) in self._rows.items():
            on = key == current
            dot.delete("all")
            ring = I.pill(18, 18, C.ACCENT if on else C.CARD, C.CARD, r=9,
                          border=None if on else C.LOCKED)
            if ring is not None:
                self._imgs.append(ring)
                dot.create_image(0, 0, image=ring, anchor="nw")
            if on:
                inner = I.dot("#ffffff", C.ACCENT, 8, 3.2)
                if inner is not None:
                    self._imgs.append(inner)
                    dot.create_image(9, 9, image=inner)
            title.config(fg=C.TEXT if on else C.MUTED)

    def _choose(self, key, title):
        if key == app_settings.login_mode():
            return
        try:
            app_settings.set("login_mode", key)
        except OSError as exc:
            C.log(f"Setting login_mode gagal disimpan: {exc!r}")
            self.msg.config(text="Gagal menyimpan. Pastikan folder data bisa ditulis.",
                            fg=C.ERROR)
            return
        self._paint(key)
        self.msg.config(text=f"Tersimpan: {title}.", fg=C.MUTED)

    def refresh(self):
        pass
