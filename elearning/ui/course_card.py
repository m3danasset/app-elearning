"""Kartu satu kursus: terbuka (bisa diklik) atau terkunci (abu-abu). Sudut membulat."""

import tkinter as tk

from elearning import config as C
from elearning.ui.controls import RoundPanel


class CourseCard(RoundPanel):
    def __init__(self, master, course, unlocked, on_open, title_font):
        super().__init__(master, fill=C.CARD, border=C.BORDER, radius=16, padx=22, pady=20,
                         stretch=True)
        self.course = course
        self.unlocked = unlocked
        self.on_open = on_open
        inner = self.inner
        self._hover_widgets = [inner]   # widget yang ikut berubah warna saat hover

        accent = course["color"] if unlocked else C.TRACK_OFF
        title_fg = C.TEXT if unlocked else C.LOCKED
        body_fg = C.MUTED if unlocked else C.LOCKED

        # Garis warna pendek membulat di atas (pengganti garis penuh lama)
        bar = tk.Canvas(inner, width=34, height=4, bg=C.CARD, highlightthickness=0, bd=0)
        bar.pack(anchor="w", pady=(0, 12))
        self._bar = bar
        self._accent = accent
        self._paint_bar(C.CARD)

        chip = tk.Label(inner, text=course["group"], bg=C.CARD, fg=accent,
                        font=(C.FONT, 9, "bold"), anchor="w")
        chip.pack(fill="x")
        title = tk.Label(inner, text=course["title"], bg=C.CARD, fg=title_fg,
                         font=title_font, anchor="w")
        title.pack(fill="x", pady=(2, 8))
        self.desc = tk.Label(inner, text=course["desc"], bg=C.CARD, fg=body_fg,
                             font=(C.FONT, 10), anchor="nw", justify="left",
                             wraplength=200)
        self.desc.pack(fill="x")

        if unlocked:
            status_text, status_fg = "Buka kursus  →", C.ACCENT
        else:
            status_text, status_fg = "Terkunci  ·  hubungi guru", C.LOCKED
        status = tk.Label(inner, text=status_text, bg=C.CARD, fg=status_fg,
                          font=(C.FONT, 10, "bold"), anchor="w")
        status.pack(side="bottom", fill="x", pady=(14, 0))

        self._hover_widgets += [chip, title, self.desc, status]
        inner.bind("<Configure>", self._fit_text, add="+")

        if unlocked:
            self._wire_events()

    def _paint_bar(self, bg):
        from elearning.ui import ui_icons as I
        self._bar.config(bg=bg)
        self._bar.delete("all")
        p = I.pill(34, 4, self._accent, bg, r=2)
        if p is not None:
            self._bar.image = p
            self._bar.create_image(0, 0, image=p, anchor="nw")

    def _fit_text(self, event):
        # Teks deskripsi menyesuaikan lebar kartu
        self.desc.config(wraplength=max(120, event.width - 4))

    # --- interaksi (hanya kartu terbuka) ------------------------------------
    def _wire_events(self):
        for w in self._all_widgets(self):
            w.config(cursor="hand2")
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")
            w.bind("<Button-1>", lambda e: self.on_open(self.course), add="+")

    def _all_widgets(self, widget):
        yield widget
        for child in widget.winfo_children():
            yield from self._all_widgets(child)

    def _set_bg(self, bg, border):
        self.set_style(fill=bg, border=border)
        for w in self._hover_widgets:
            w.config(bg=bg)
        self._paint_bar(bg)

    def _on_enter(self, _event):
        self._set_bg(C.CARD_HOVER, self.course["color"])

    def _on_leave(self, event):
        # Abaikan kalau kursor hanya pindah ke elemen lain di dalam kartu yang sama
        under = self.winfo_containing(event.x_root, event.y_root)
        while under is not None:
            if under is self:
                return
            under = under.master
        self._set_bg(C.CARD, C.BORDER)
