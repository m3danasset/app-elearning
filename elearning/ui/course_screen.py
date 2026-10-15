"""Layar satu kursus: sidebar kiri (bisa dilipat) + area materi."""

import tkinter as tk

from elearning import config as C
from elearning import portfolio
from elearning.courses import courses_for
from elearning.trial import is_trial
from elearning.ui.avatar import Avatar
from elearning.ui.portfolio_view import PortfolioPanel
from elearning.ui.widgets import add_hover

EXPANDED_W = 270
COLLAPSED_W = 76

# Pilihan lipat/buka diingat selama aplikasi terbuka (tidak berubah saat pindah kursus)
_state = {"collapsed": False}


class CourseScreen(tk.Frame):
    def __init__(self, master, student, course, on_back, on_logout, on_open_course):
        super().__init__(master, bg=C.BG)
        self.student = student
        self.course = course
        self.on_back = on_back
        self.on_logout = on_logout
        self.on_open_course = on_open_course
        self.view = "materi"   # "materi" atau "portfolio"

        self.sidebar = tk.Frame(self, bg=C.CARD, width=EXPANDED_W)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Frame(self, bg=C.BORDER, width=1).pack(side="left", fill="y")

        # --- Kanan: judul kursus + area materi -------------------------------
        content = tk.Frame(self, bg=C.BG)
        content.pack(side="left", fill="both", expand=True)

        bar = tk.Frame(content, bg=C.CARD, height=56, highlightthickness=1,
                       highlightbackground=C.BORDER)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self.title_lbl = tk.Label(bar, text=course["title"], bg=C.CARD, fg=C.TEXT,
                                  font=(C.FONT, 13, "bold"))
        self.title_lbl.pack(side="left", padx=20)
        out = tk.Button(bar, text="Keluar", command=self.on_logout, bg=C.CARD,
                        fg=C.MUTED, activebackground=C.BORDER,
                        activeforeground=C.TEXT, relief="flat", bd=0,
                        highlightthickness=0, font=(C.FONT, 10), cursor="hand2",
                        padx=14)
        out.pack(side="right", padx=12, pady=12)   # pojok kanan atas, sama seperti layar utama
        add_hover(out, C.CARD, C.BORDER)

        self.body = tk.Frame(content, bg=C.BG)
        self.body.pack(fill="both", expand=True)

        self._render_body()
        self._build_sidebar()

    # --- isi kanan: materi / portfolio ---------------------------------------
    def _render_body(self):
        for w in self.body.winfo_children():
            w.destroy()
        course = self.course
        if self.view == "portfolio":
            self.title_lbl.config(text=f"{course['title']}  ·  Portfolio")
            PortfolioPanel(self.body, self.student, course,
                           on_change=self._build_sidebar).pack(fill="both", expand=True)
            return
        self.title_lbl.config(text=course["title"])
        msg = tk.Frame(self.body, bg=C.BG)
        msg.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(msg, text=course["group"], bg=C.BG, fg=course["color"],
                 font=(C.FONT, 10, "bold")).pack()
        tk.Label(msg, text=course["title"], bg=C.BG, fg=C.TEXT,
                 font=(C.FONT, 24, "bold")).pack(pady=(2, 8))
        tk.Label(msg, text="Video dan materi kursus akan tampil di sini.",
                 bg=C.BG, fg=C.MUTED, font=(C.FONT, 11)).pack()

    def _set_view(self, view):
        if view == self.view:
            return
        self.view = view
        self._render_body()
        self._build_sidebar()

    # --- sidebar -----------------------------------------------------------
    def _toggle_sidebar(self):
        _state["collapsed"] = not _state["collapsed"]
        self._build_sidebar()

    def _build_sidebar(self):
        for w in self.sidebar.winfo_children():
            w.destroy()
        if _state["collapsed"]:
            self.sidebar.config(width=COLLAPSED_W)
            self._build_collapsed()
        else:
            self.sidebar.config(width=EXPANDED_W)
            self._build_expanded()

    def _flat_button(self, parent, text, command, fg=C.MUTED, font_size=10, **pack):
        btn = tk.Button(parent, text=text, command=command, bg=C.CARD, fg=fg,
                        activebackground=C.BORDER, activeforeground=C.TEXT,
                        relief="flat", bd=0, highlightthickness=0,
                        font=(C.FONT, font_size), cursor="hand2", pady=7)
        add_hover(btn, C.CARD, C.BORDER)
        btn.pack(**pack)
        return btn

    def _build_expanded(self):
        sb, st = self.sidebar, self.student

        # Paling bawah: kembali (tombol Keluar ada di pojok kanan atas layar)
        bottom = tk.Frame(sb, bg=C.CARD)
        bottom.pack(side="bottom", fill="x", padx=12, pady=(6, 14))
        self._flat_button(bottom, "←  Kembali ke daftar kursus", self.on_back,
                          fill="x")

        # Paling atas: foto + nama murid + tombol lipat
        head = tk.Frame(sb, bg=C.CARD, padx=16, pady=16)
        head.pack(fill="x")
        self._flat_button(head, "«", self._toggle_sidebar, font_size=14,
                          side="right", anchor="n")  # dipasang dulu agar tidak tergencet nama
        Avatar(head, st["id"], st["name"], size=56, bg=C.CARD).pack(side="left")
        who = tk.Frame(head, bg=C.CARD)
        who.pack(side="left", fill="x", expand=True, padx=(12, 4))
        tk.Label(who, text=st["name"], bg=C.CARD, fg=C.TEXT, anchor="w",
                 justify="left", wraplength=110,
                 font=(C.FONT, 12, "bold")).pack(fill="x")
        tk.Label(who, text=st["id"], bg=C.CARD, fg=C.MUTED, anchor="w",
                 font=(C.FONT, 9)).pack(fill="x")
        tk.Frame(sb, bg=C.BORDER, height=1).pack(fill="x")

        # Daftar kursus
        tk.Label(sb, text="KURSUS", bg=C.CARD, fg=C.MUTED, anchor="w",
                 font=(C.FONT, 9, "bold")).pack(fill="x", padx=20, pady=(16, 6))
        allowed = set(st["courses"])
        for c in courses_for(st["program"]):
            self._build_course_item(c, c["id"] in allowed)

        if is_trial(st):   # calon murid: tidak ada portfolio
            return

        # Menu di dalam kursus yang sedang dibuka: materi dan portfolio
        tk.Label(sb, text="DI KURSUS INI", bg=C.CARD, fg=C.MUTED, anchor="w",
                 font=(C.FONT, 9, "bold")).pack(fill="x", padx=20, pady=(18, 6))
        n = portfolio.count(st["id"], self.course["id"])
        self._build_view_item("Materi", "materi", C.TEXT)
        self._build_view_item("Portfolio" + (f"   ·  {n}" if n else ""), "portfolio",
                              C.ACCENT)

    def _build_view_item(self, text, view, stripe):
        current = self.view == view
        bg = C.CARD_HOVER if current else C.CARD
        row = tk.Frame(self.sidebar, bg=bg)
        row.pack(fill="x", padx=10, pady=1)
        tk.Frame(row, bg=stripe if current else "#3a3f4d", width=4).pack(side="left", fill="y")
        lbl = tk.Label(row, text=text, bg=bg, fg=C.TEXT, anchor="w", padx=12, pady=8,
                       font=(C.FONT, 10, "bold" if current else "normal"), cursor="hand2")
        lbl.pack(side="left", fill="x", expand=True)
        lbl.bind("<Button-1>", lambda e, v=view: self._set_view(v))
        if not current:
            lbl.bind("<Enter>", lambda e: (lbl.config(bg=C.CARD_HOVER),
                                           row.config(bg=C.CARD_HOVER)))
            lbl.bind("<Leave>", lambda e: (lbl.config(bg=C.CARD), row.config(bg=C.CARD)))

    def _build_course_item(self, course, unlocked):
        current = course["id"] == self.course["id"]
        bg = C.CARD_HOVER if current else C.CARD
        row = tk.Frame(self.sidebar, bg=bg)
        row.pack(fill="x", padx=10, pady=1)
        stripe = course["color"] if unlocked else "#3a3f4d"
        tk.Frame(row, bg=stripe, width=4).pack(side="left", fill="y")
        text = course["title"] if unlocked else f"{course['title']}   ·  terkunci"
        fg = C.TEXT if unlocked else C.LOCKED
        lbl = tk.Label(row, text=text, bg=bg, fg=fg, anchor="w", padx=12, pady=8,
                       font=(C.FONT, 10, "bold" if current else "normal"))
        lbl.pack(side="left", fill="x", expand=True)
        if unlocked and not current:
            lbl.config(cursor="hand2")
            lbl.bind("<Button-1>", lambda e, c=course: self.on_open_course(c))
            lbl.bind("<Enter>", lambda e: (lbl.config(bg=C.CARD_HOVER),
                                           row.config(bg=C.CARD_HOVER)))
            lbl.bind("<Leave>", lambda e: (lbl.config(bg=C.CARD),
                                           row.config(bg=C.CARD)))

    def _build_collapsed(self):
        sb, st = self.sidebar, self.student

        bottom = tk.Frame(sb, bg=C.CARD)
        bottom.pack(side="bottom", fill="x", padx=8, pady=(6, 14))
        self._flat_button(bottom, "←", self.on_back, font_size=13, fill="x")

        self._flat_button(sb, "»", self._toggle_sidebar, font_size=14,
                          fill="x", padx=14, pady=(14, 6))
        Avatar(sb, st["id"], st["name"], size=44, bg=C.CARD).pack(pady=(8, 0))
        if is_trial(st):
            return
        on = self.view == "portfolio"
        btn = self._flat_button(
            sb, "▦", lambda: self._set_view("materi" if on else "portfolio"),
            fg=C.ACCENT if on else C.MUTED, font_size=14, fill="x", padx=14, pady=(18, 0))
        if on:
            btn.config(bg=C.CARD_HOVER)
