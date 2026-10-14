"""Bar atas yang dipakai di semua layar setelah login."""

import tkinter as tk

from elearning import config as C
from elearning.ui.avatar import Avatar
from elearning.ui.widgets import add_hover


class TopBar(tk.Frame):
    def __init__(self, master, student, on_logout, on_back=None, title=None):
        super().__init__(master, bg=C.CARD, height=56, highlightthickness=1,
                         highlightbackground=C.BORDER)
        self.pack_propagate(False)

        if on_back is not None:
            back = tk.Button(self, text="←  Kembali", command=on_back,
                             bg=C.CARD, fg=C.MUTED, activebackground=C.BORDER,
                             activeforeground=C.TEXT, relief="flat", bd=0, highlightthickness=0,
                             font=(C.FONT, 10), cursor="hand2", padx=14)
            back.pack(side="left", padx=(12, 0), pady=12)
            add_hover(back, C.CARD, C.BORDER)

        tk.Label(self, text=title or C.APP_NAME, bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 13, "bold")).pack(side="left", padx=16)

        out = tk.Button(self, text="Keluar", command=on_logout,
                        bg=C.CARD, fg=C.MUTED, activebackground=C.BORDER,
                        activeforeground=C.TEXT, relief="flat", bd=0, highlightthickness=0,
                        font=(C.FONT, 10), cursor="hand2", padx=14)
        out.pack(side="right", padx=12, pady=12)
        add_hover(out, C.CARD, C.BORDER)

        tk.Label(self, text=f"{student['name']}  ·  {student['id']}",
                 bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="right", padx=(8, 4))
        Avatar(self, student["id"], student["name"], size=36,
               bg=C.CARD).pack(side="right", padx=(8, 0))
