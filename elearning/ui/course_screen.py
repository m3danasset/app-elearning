"""Layar satu kursus (murid & trial): sidebar kiri gaya claude.ai + area materi.

Sidebar: logo, kolom cari (menyaring pelajaran & kursus), menu Semua kursus / Materi /
Resource / Portfolio, daftar pelajaran, daftar kursus, Buka Blender, lalu profil murid
di paling bawah (klik -> Keluar).
"""

import tkinter as tk

from elearning import config as C
from elearning import portfolio
from elearning import lessons as lessons_mod
from elearning.courses import courses_for
from elearning.trial import is_trial
from elearning.ui.lesson_view import LessonsPanel
from elearning.ui.portfolio_view import PortfolioPanel
from elearning.ui.sidebar import (AppSidebar, PageHeader, SidebarLayout, blender_footer,
                                  course_items, student_subtitle)


class CourseScreen(SidebarLayout):
    def __init__(self, master, student, course, on_back, on_logout, on_open_course):
        super().__init__(master)
        self.student = student
        self.course = course
        self.on_back = on_back
        self.on_logout = on_logout
        self.on_open_course = on_open_course
        self.trial = is_trial(student)
        self.view = "materi"   # "materi", "resource" atau "portfolio"
        self.lesson_items = lessons_mod.lessons_for(course)   # pelajaran di bawah Materi (sidebar)
        self.lesson_index = 0
        self.panel = None      # LessonsPanel yang sedang tampil (view "materi")

        self.sb = AppSidebar(self, student, student_subtitle(student), on_logout,
                             self._populate,
                             placeholder="Cari kursus" if self.trial else "Cari pelajaran")
        self.attach(self.sb)

        # --- Kanan: judul kursus + area materi -------------------------------
        self.header = PageHeader(self.content, course["title"])
        self.header.pack(fill="x")
        self.body = tk.Frame(self.content, bg=C.BG)
        self.body.pack(fill="both", expand=True)
        self._render_body()

    # --- sidebar -----------------------------------------------------------------
    def _populate(self, sb):
        sb.nav("Semua kursus", "grid", self.on_back)
        sb.nav("Materi", "play", lambda: self._set_view("materi"),
               active=self.view == "materi")
        if not self.trial:   # calon murid: tanpa resource/portfolio & daftar pelajaran
            n = portfolio.count(self.student["id"], self.course["id"])
            sb.nav("Resource", "folder", lambda: self._set_view("resource"),
                   active=self.view == "resource")
            sb.nav("Portfolio", "image", lambda: self._set_view("portfolio"),
                   active=self.view == "portfolio", right=str(n) if n else None)

            shown = [(i, it) for i, it in enumerate(self.lesson_items)
                     if sb.matches(it["label"], it.get("title"))]
            sb.section(f"Pelajaran  ·  {self.course['title']}", top=10,
                       right=str(len(shown)))
            for i, it in shown:
                sb.item(it["label"], lambda k=i: self._open_lesson(k), marquee=True,
                        active=self.view == "materi" and i == self.lesson_index)
            if not shown:
                sb.note(f"Tidak ada pelajaran yang cocok dengan “{sb.query.strip()}”.")

        allowed = set(self.student["courses"])
        course_items(sb, courses_for(self.student["program"]), allowed, self.course["id"],
                     self.on_open_course)
        blender_footer(sb)

    # --- isi kanan: materi / resource / portfolio ------------------------------------
    def _render_body(self):
        self.panel = None
        for w in self.body.winfo_children():
            w.destroy()
        course = self.course
        if self.view == "portfolio":
            self.header.set_title(course["title"], "Portfolio")
            PortfolioPanel(self.body, self.student, course,
                           on_change=self.sb.refresh).pack(fill="both", expand=True)
            return
        if self.view == "resource":
            self.header.set_title(course["title"], "Resource")
            msg = tk.Frame(self.body, bg=C.BG)
            msg.place(relx=0.5, rely=0.5, anchor="center")
            tk.Label(msg, text="Resource", bg=C.BG, fg=course["color"],
                     font=(C.FONT, 10, "bold")).pack()
            tk.Label(msg, text=course["title"], bg=C.BG, fg=C.TEXT,
                     font=(C.FONT, 24, "bold")).pack(pady=(2, 8))
            tk.Label(msg, text="File resource kursus akan tampil di sini.",
                     bg=C.BG, fg=C.MUTED, font=(C.FONT, 11)).pack()
            return
        self.header.set_title(course["title"], "Materi")
        # Pemutar video untuk semua murid (termasuk trial)
        self.panel = LessonsPanel(self.body, course, self.lesson_items, self.lesson_index,
                                  on_select=self._on_lesson_changed,
                                  on_fullscreen=self._set_fullscreen,
                                  show_nav=not self.trial)
        self.panel.pack(fill="both", expand=True)

    def _set_fullscreen(self, want):
        """Layar penuh pemutar video: sembunyikan sidebar dan judul, jendela layar penuh."""
        top = self.winfo_toplevel()
        if want:
            self.hide_sidebar()
            self.header.pack_forget()
            try:
                top.attributes("-fullscreen", True)
            except Exception as exc:
                C.log(f"Layar penuh gagal: {exc!r}")
            return
        try:
            top.attributes("-fullscreen", False)
        except Exception:
            pass
        self.show_sidebar()
        if not self.header.winfo_manager():
            self.header.pack(fill="x", before=self.body)

    def destroy(self):
        try:
            self.winfo_toplevel().attributes("-fullscreen", False)   # jangan terjebak layar penuh
        except Exception:
            pass
        super().destroy()

    def _on_lesson_changed(self, index):
        """Pelajaran berganti (tombol Sebelumnya/Selanjutnya): sorotan di sidebar ikut pindah."""
        self.lesson_index = index
        self.sb.refresh()

    def _open_lesson(self, index):
        """Klik pelajaran di sidebar."""
        if self.view == "materi" and self.panel is not None:
            self.panel.select(index)    # memanggil _on_lesson_changed
            return
        self.lesson_index = index
        self.view = "materi"
        self._render_body()
        self.sb.refresh()

    def _set_view(self, view):
        if view == self.view:
            return
        self.view = view
        self._render_body()
        self.sb.refresh()
