"""Layar utama setelah login (murid & trial): sidebar kiri + pilihan kursus."""

import tkinter as tk
from tkinter import font as tkfont

from elearning import config as C
from elearning.courses import courses_for
from elearning.trial import is_trial
from elearning.ui.course_card import CourseCard
from elearning.ui.sidebar import (AppSidebar, SidebarLayout, blender_footer, course_items,
                                  student_subtitle)

COLUMNS = 3


class HomeScreen(SidebarLayout):
    def __init__(self, master, student, on_open_course, on_logout):
        super().__init__(master)
        self.student = student
        self.on_open_course = on_open_course
        self.trial = is_trial(student)
        self.courses = courses_for(student["program"])   # dewasa / anak / trial
        self.allowed = set(student["courses"])

        self.sb = AppSidebar(self, student, student_subtitle(student), on_logout,
                             self._populate, placeholder="Cari kursus",
                             on_search=self._on_search)
        self.attach(self.sb)

        body = self.body = tk.Frame(self.content, bg=C.BG, padx=48, pady=32)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="Pilih kelas trial" if self.trial else "Pilih kursus", bg=C.BG,
                 fg=C.TEXT, font=(C.FONT, 22, "bold"), anchor="w").pack(fill="x")
        hello = ("Selamat datang, calon murid! Pilih satu kelas untuk mencoba belajar."
                 if self.trial else
                 f"Halo, {student['name']}! Lanjutkan belajar dari kursus yang terbuka.")
        tk.Label(body, text=hello, bg=C.BG, fg=C.MUTED, font=(C.FONT, 11),
                 anchor="w").pack(fill="x", pady=(4, 20))

        # Ukuran judul kartu dibuat sama untuk semua kartu & menyesuaikan lebar jendela
        self.title_font = tkfont.Font(family=C.FONT, size=18, weight="bold")
        self._longest_title = max((c["title"] for c in self.courses), key=len)
        self.cols = max(1, min(COLUMNS, len(self.courses)))
        self.grid_box = None
        self._build_grid()

    # --- sidebar ---------------------------------------------------------------------
    def _populate(self, sb):
        sb.nav("Semua kursus", "grid", lambda: None, active=True)
        course_items(sb, self.courses, self.allowed, None, self.on_open_course)
        blender_footer(sb)

    def _on_search(self, _query):
        self.sb.refresh(keep_scroll=False)
        self._build_grid()

    # --- kartu kursus (ikut tersaring kolom cari) -------------------------------------
    def _build_grid(self):
        if self.grid_box is not None:
            self.grid_box.destroy()
        grid = self.grid_box = tk.Frame(self.body, bg=C.BG)
        grid.pack(fill="both", expand=True)
        courses = [c for c in self.courses if self.sb.matches(c["title"], c["group"], c["desc"])]
        if not courses:
            tk.Label(grid, text=f"Tidak ada kursus yang cocok dengan "
                                f"“{self.sb.query.strip()}”.",
                     bg=C.BG, fg=C.MUTED, font=(C.FONT, 11), anchor="w").pack(fill="x")
            return
        all_rows = (len(self.courses) + self.cols - 1) // self.cols
        rows = (len(courses) + self.cols - 1) // self.cols
        for c in range(self.cols):
            grid.columnconfigure(c, weight=1, uniform="col")
        for r in range(rows):
            if all_rows == 1 or rows < all_rows:   # baris sedikit: kartu tidak ditarik setinggi layar
                grid.rowconfigure(r, weight=0, minsize=210)
            else:
                grid.rowconfigure(r, weight=1, uniform="row")
        grid.bind("<Configure>", self._fit_title_font)
        for i, course in enumerate(courses):
            card = CourseCard(grid, course, unlocked=course["id"] in self.allowed,
                              on_open=self.on_open_course, title_font=self.title_font)
            card.grid(row=i // self.cols, column=i % self.cols, sticky="nsew", padx=8, pady=8)

    def _fit_title_font(self, event):
        avail = event.width / self.cols - 16 - 44 - 4  # jarak antar kartu, isi kartu, garis tepi
        for size in (18, 16, 15, 14, 13, 12, 11):
            self.title_font.config(size=size)
            if self.title_font.measure(self._longest_title) <= avail:
                break
