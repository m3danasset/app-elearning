"""Kartu satu kursus: terbuka (bisa diklik) atau terkunci (abu-abu)."""

import tkinter as tk

from elearning import config as C


class CourseCard(tk.Frame):
    def __init__(self, master, course, unlocked, on_open, title_font):
        super().__init__(master, bg=C.CARD, highlightthickness=1,
                         highlightbackground=C.BORDER)
        self.course = course
        self.unlocked = unlocked
        self.on_open = on_open
        self._hover_widgets = [self]  # widget yang ikut berubah warna saat hover

        accent = course["color"] if unlocked else "#3a3f4d"
        title_fg = C.TEXT if unlocked else C.LOCKED
        body_fg = C.MUTED if unlocked else C.LOCKED

        # Garis warna di atas kartu
        tk.Frame(self, bg=accent, height=4).pack(fill="x")

        inner = tk.Frame(self, bg=C.CARD, padx=22, pady=18)
        inner.pack(fill="both", expand=True)
        self._hover_widgets.append(inner)

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
        inner.bind("<Configure>", self._fit_text)

        if unlocked:
            self._wire_events()

    def _fit_text(self, event):
        # Teks deskripsi menyesuaikan lebar kartu
        self.desc.config(wraplength=max(120, event.width - 44))

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

    def _on_enter(self, _event):
        self.config(highlightbackground=self.course["color"])
        for w in self._hover_widgets:
            w.config(bg=C.CARD_HOVER)

    def _on_leave(self, event):
        # Abaikan kalau kursor hanya pindah ke elemen lain di dalam kartu yang sama
        under = self.winfo_containing(event.x_root, event.y_root)
        while under is not None:
            if under is self:
                return
            under = under.master
        self.config(highlightbackground=C.BORDER)
        for w in self._hover_widgets:
            w.config(bg=C.CARD)
