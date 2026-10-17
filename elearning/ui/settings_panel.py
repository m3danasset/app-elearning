"""Panel Admin > Setting: pengaturan aplikasi (data\\settings.json, lihat app_settings.py).

Satu baris per pengaturan: kartu bersudut bulat (RoundPanel) berisi judul, keterangan, dan
switch. Disimpan langsung saat switch diklik.
"""

import tkinter as tk

from elearning import app_settings
from elearning import config as C
from elearning.ui.controls import RoundPanel
from elearning.ui.widgets import Switch

ITEMS = (
    ("login_carousel_rows3", "Carousel login 3 baris",
     "Tambah baris kartu portfolio di atas dan di bawah carousel layar login (bergerak "
     "berlawanan arah), total 30 portfolio. Berlaku saat layar login dibuka berikutnya. "
     "Lebih berat: di PC lambat carousel otomatis turun fps supaya tetap rata."),
)


class SettingsPanel(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C.BG)
        self.msg = tk.Label(self, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 9), anchor="w")
        for key, title, desc in ITEMS:
            panel = RoundPanel(self, padx=4, pady=2)
            panel.pack(fill="x", pady=4)
            row = panel.inner
            sw_box = tk.Frame(row, bg=C.CARD)
            sw_box.pack(side="right", padx=(10, 16))
            info = tk.Frame(row, bg=C.CARD, padx=16, pady=12)
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=title, bg=C.CARD, fg=C.TEXT, font=(C.FONT, 12, "bold"),
                     anchor="w").pack(fill="x")
            tk.Label(info, text=desc, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 9), anchor="w",
                     justify="left", wraplength=640).pack(fill="x", pady=(2, 0))
            Switch(sw_box, value=bool(app_settings.get(key)), bg=C.CARD,
                   command=lambda v, k=key, t=title: self._save(k, v, t)).pack()
        self.msg.pack(fill="x", pady=(8, 0))

    def _save(self, key, value, title):
        try:
            app_settings.set(key, bool(value))
        except OSError as exc:
            C.log(f"Setting {key} gagal disimpan: {exc!r}")
            self.msg.config(text="Gagal menyimpan. Pastikan folder data bisa ditulis.",
                            fg=C.ERROR)
            return False
        self.msg.config(text=f"Tersimpan: {title} {'ON' if value else 'OFF'}.", fg=C.MUTED)
        return True

    def refresh(self):
        pass
