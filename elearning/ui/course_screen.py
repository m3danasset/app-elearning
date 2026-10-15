"""Layar satu kursus: sidebar kiri (bisa dilipat) + area materi."""

import tkinter as tk

from elearning import config as C
from elearning import blender_icon, blender_launcher, portfolio, sidebar_icons
from elearning import lessons as lessons_mod
from elearning.courses import courses_for
from elearning.trial import is_trial
from elearning.ui.avatar import Avatar
from elearning.ui.lesson_view import LessonsPanel
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
        self.view = "materi"   # "materi", "resource" atau "portfolio"
        self.lesson_items = lessons_mod.lessons_for(course)   # pelajaran di bawah Materi (sidebar)
        self.lesson_index = 0
        self.panel = None      # LessonsPanel yang sedang tampil (view "materi")

        self.sidebar = tk.Frame(self, bg=C.CARD, width=EXPANDED_W)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.sidebar_line = tk.Frame(self, bg=C.BORDER, width=1)
        self.sidebar_line.pack(side="left", fill="y")

        # --- Kanan: judul kursus + area materi -------------------------------
        content = self.content = tk.Frame(self, bg=C.BG)
        content.pack(side="left", fill="both", expand=True)

        bar = self.topbar = tk.Frame(content, bg=C.CARD, height=56, highlightthickness=1,
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
        self.panel = None
        for w in self.body.winfo_children():
            w.destroy()
        course = self.course
        if self.view == "portfolio":
            self.title_lbl.config(text=f"{course['title']}  ·  Portfolio")
            PortfolioPanel(self.body, self.student, course,
                           on_change=self._build_sidebar).pack(fill="both", expand=True)
            return
        if self.view == "resource":
            self.title_lbl.config(text=f"{course['title']}  ·  Resource")
            msg = tk.Frame(self.body, bg=C.BG)
            msg.place(relx=0.5, rely=0.5, anchor="center")
            tk.Label(msg, text="Resource", bg=C.BG, fg=course["color"],
                     font=(C.FONT, 10, "bold")).pack()
            tk.Label(msg, text=course["title"], bg=C.BG, fg=C.TEXT,
                     font=(C.FONT, 24, "bold")).pack(pady=(2, 8))
            tk.Label(msg, text="File resource kursus akan tampil di sini.",
                     bg=C.BG, fg=C.MUTED, font=(C.FONT, 11)).pack()
            return
        self.title_lbl.config(text=course["title"])
        # Pemutar video untuk semua murid (termasuk trial)
        self.panel = LessonsPanel(self.body, course, self.lesson_items, self.lesson_index,
                                  on_select=self._on_lesson_changed,
                                  on_fullscreen=self._set_fullscreen)
        self.panel.pack(fill="both", expand=True)

    def _set_fullscreen(self, want):
        """Layar penuh pemutar video: sembunyikan sidebar dan bar judul, jendela layar penuh."""
        top = self.winfo_toplevel()
        if want:
            self.sidebar.pack_forget()
            self.sidebar_line.pack_forget()
            self.topbar.pack_forget()
            try:
                top.attributes("-fullscreen", True)
            except Exception as exc:
                C.log(f"Layar penuh gagal: {exc!r}")
            return
        try:
            top.attributes("-fullscreen", False)
        except Exception:
            pass
        if not self.sidebar.winfo_manager():
            self.sidebar.pack(side="left", fill="y", before=self.content)
            self.sidebar_line.pack(side="left", fill="y", before=self.content)
            self.topbar.pack(fill="x", before=self.body)

    def destroy(self):
        try:
            self.winfo_toplevel().attributes("-fullscreen", False)   # jangan terjebak layar penuh
        except Exception:
            pass
        super().destroy()

    def _on_lesson_changed(self, index):
        """Pelajaran berganti (tombol Sebelumnya/Selanjutnya): sorotan di sidebar ikut pindah."""
        self.lesson_index = index
        self._build_sidebar()

    def _open_lesson(self, index):
        """Klik pelajaran di sidebar."""
        if self.view == "materi" and self.panel is not None:
            self.panel.select(index)    # memanggil _on_lesson_changed
            return
        self.lesson_index = index
        self.view = "materi"
        self._render_body()
        self._build_sidebar()

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
        # Shortcut Blender tepat di atas tombol kembali (sama seperti saat sidebar dilipat)
        self._build_blender_item()

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

        # Menu di dalam kursus yang sedang dibuka: Materi (dengan daftar pelajaran di
        # bawahnya), lalu Resource dan Portfolio
        tk.Label(sb, text="DI KURSUS INI", bg=C.CARD, fg=C.MUTED, anchor="w",
                 font=(C.FONT, 9, "bold")).pack(fill="x", padx=20, pady=(18, 6))
        self._build_view_item("Materi", "materi", C.TEXT)
        if is_trial(st):   # calon murid: tanpa daftar pelajaran di sidebar, tanpa resource/portfolio
            return
        for i, it in enumerate(self.lesson_items):
            self._build_lesson_item(i, it)
        n = portfolio.count(st["id"], self.course["id"])
        self._build_view_item("Resource", "resource", C.TEXT)
        self._build_view_item("Portfolio" + (f"   ·  {n}" if n else ""), "portfolio",
                              C.ACCENT)

    def _build_lesson_item(self, index, item):
        """Satu pelajaran, menjorok di bawah 'Materi' (hierarki: kursus > Materi > pelajaran)."""
        current = self.view == "materi" and index == self.lesson_index
        bg = C.CARD_HOVER if current else C.CARD
        row = tk.Frame(self.sidebar, bg=bg)
        row.pack(fill="x", padx=(30, 10), pady=1)
        tk.Frame(row, bg=self.course["color"] if current else "#3a3f4d",
                 width=3).pack(side="left", fill="y")
        lbl = tk.Label(row, text=item["label"], bg=bg, fg=C.TEXT if current else C.MUTED,
                       anchor="w", justify="left", padx=10, pady=5, wraplength=170,
                       font=(C.FONT, 9, "bold" if current else "normal"), cursor="hand2")
        lbl.pack(side="left", fill="x", expand=True)
        for w in (row, lbl):
            w.bind("<Button-1>", lambda e, k=index: self._open_lesson(k))
        if not current:
            def enter(e):
                row.config(bg=C.CARD_HOVER)
                lbl.config(bg=C.CARD_HOVER, fg=C.TEXT)

            def leave(e):
                row.config(bg=C.CARD)
                lbl.config(bg=C.CARD, fg=C.MUTED)
            for w in (row, lbl):
                w.bind("<Enter>", enter)
                w.bind("<Leave>", leave)

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

    # --- tombol Blender (semua murid: trial, superkids, dewasa) --------------
    def _open_blender(self):
        app = self.winfo_toplevel()
        if blender_launcher.open_blender(app):
            ctl = getattr(app, "blender_float", None)
            if ctl is not None:   # Blender terbuka -> aplikasi mengecil jadi ikon mengambang
                ctl.enter()

    def _blender_icon(self, parent, bg, size):
        """Ikon Blender (gambar) berukuran size x size; cadangan: lingkaran oranye."""
        photo = blender_icon.get_photo(size)
        if photo is not None:
            lbl = tk.Label(parent, image=photo, bg=bg, bd=0, highlightthickness=0,
                           cursor="hand2")
            lbl.image = photo   # simpan referensi supaya gambar tidak hilang
            return lbl
        cv = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0,
                       bd=0, cursor="hand2")
        cv.create_oval(1, 1, size - 1, size - 1, fill=C.ACCENT, outline=C.ACCENT)
        m = size * 0.27
        cv.create_oval(m, m, size - m, size - m, fill=C.ACCENT, outline="white", width=2)
        c = size / 2
        cv.create_oval(c - 2, c - 2, c + 2, c + 2, fill="white", outline="white")
        return cv

    def _bind_blender_click(self, widgets, hover_targets, normal, hover):
        def set_bg(color):
            for w in hover_targets:
                w.config(bg=color)
        for w in widgets:
            w.bind("<Button-1>", lambda e: self._open_blender())
            w.bind("<Enter>", lambda e: set_bg(hover))
            w.bind("<Leave>", lambda e: set_bg(normal))

    def _build_blender_item(self):
        """Dipasang di dasar sidebar (side="bottom": baris dulu, baru labelnya di atas)."""
        row = tk.Frame(self.sidebar, bg=C.CARD)
        row.pack(side="bottom", fill="x", padx=10, pady=(1, 6))
        tk.Label(self.sidebar, text="BLENDER", bg=C.CARD, fg=C.MUTED, anchor="w",
                 font=(C.FONT, 9, "bold")).pack(side="bottom", fill="x", padx=20, pady=(0, 4))
        tk.Frame(row, bg=C.ACCENT, width=4).pack(side="left", fill="y")
        icon = self._blender_icon(row, C.CARD, blender_icon.SIZE_EXPANDED)
        icon.pack(side="left", padx=(12, 0), pady=6)
        lbl = tk.Label(row, text=f"Buka Blender {blender_launcher.VERSION}", bg=C.CARD,
                       fg=C.TEXT, anchor="w", padx=10, pady=8, font=(C.FONT, 10),
                       cursor="hand2")
        lbl.pack(side="left", fill="x", expand=True)
        self._bind_blender_click((row, icon, lbl), (row, icon, lbl), C.CARD, C.CARD_HOVER)

    def _build_blender_icon_only(self):
        holder = tk.Frame(self.sidebar, bg=C.CARD)
        holder.pack(fill="x", padx=14, pady=(18, 0))
        icon = self._blender_icon(holder, C.CARD, blender_icon.SIZE_COLLAPSED)
        icon.pack(pady=4)
        self._bind_blender_click((holder, icon), (holder, icon), C.CARD, C.CARD_HOVER)

    def _build_collapsed(self):
        sb, st = self.sidebar, self.student

        # Paling bawah: tombol kembali, lalu ikon Blender tepat di atasnya
        bottom = tk.Frame(sb, bg=C.CARD)
        bottom.pack(side="bottom", fill="x", padx=8, pady=(6, 14))
        self._flat_button(bottom, "←", self.on_back, font_size=13, fill="x")
        holder = tk.Frame(sb, bg=C.CARD)
        holder.pack(side="bottom", fill="x", padx=14, pady=(0, 6))
        icon = self._blender_icon(holder, C.CARD, blender_icon.SIZE_COLLAPSED)
        icon.pack(pady=4)
        self._bind_blender_click((holder, icon), (holder, icon), C.CARD, C.CARD_HOVER)

        # Atas: lipat/buka, foto murid, lalu ikon Materi (video), Resource, Portfolio
        self._flat_button(sb, "»", self._toggle_sidebar, font_size=14,
                          fill="x", padx=14, pady=(14, 6))
        Avatar(sb, st["id"], st["name"], size=44, bg=C.CARD).pack(pady=(8, 0))
        self._build_view_icon(sidebar_icons.MATERI, "materi", pady=(18, 0))
        if is_trial(st):   # calon murid: tidak ada resource/portfolio
            return
        self._build_view_icon(sidebar_icons.RESOURCE, "resource", pady=(10, 0))
        self._build_view_icon(sidebar_icons.PORTFOLIO, "portfolio", pady=(10, 0))

    def _build_view_icon(self, kind, view, pady):
        """Ikon bulat 44 px untuk berpindah antara materi dan portfolio (sidebar dilipat)."""
        active = self.view == view
        normal = sidebar_icons.get_photo(kind, active=active)
        hover = sidebar_icons.get_photo(kind, active=active, hover=True)
        if normal is None:   # cadangan kalau Pillow tidak ada: tombol teks
            self._flat_button(self.sidebar,
                              {"portfolio": "▦", "resource": "▤"}.get(kind, "▶"),
                              lambda v=view: self._set_view(v),
                              fg=C.ACCENT if active else C.MUTED, font_size=14,
                              fill="x", padx=14, pady=pady)
            return
        lbl = tk.Label(self.sidebar, image=normal, bg=C.CARD, bd=0, highlightthickness=0,
                       cursor="hand2")
        lbl.image, lbl.hover_image = normal, hover   # simpan referensi supaya gambar tidak hilang
        lbl.pack(pady=pady)
        lbl.bind("<Button-1>", lambda e, v=view: self._set_view(v))
        if not active:
            lbl.bind("<Enter>", lambda e: lbl.config(image=hover))
            lbl.bind("<Leave>", lambda e: lbl.config(image=normal))
