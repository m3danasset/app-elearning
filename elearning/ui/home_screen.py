"""Layar utama setelah login: pilihan kursus."""

import tkinter as tk
from tkinter import font as tkfont

from elearning import config as C
from elearning.courses import courses_for
from elearning.ui.course_card import CourseCard
from elearning.ui.topbar import TopBar

COLUMNS = 3


class HomeScreen(tk.Frame):
    def __init__(self, master, student, on_open_course, on_logout):
        super().__init__(master, bg=C.BG)
        self.student = student
        self.on_open_course = on_open_course

        TopBar(self, student, on_logout).pack(fill="x")

        body = tk.Frame(self, bg=C.BG, padx=48, pady=24)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Pilih kursus", bg=C.BG, fg=C.TEXT,
                 font=(C.FONT, 22, "bold"), anchor="w").pack(fill="x")
        tk.Label(body, text=f"Halo, {student['name']}! Lanjutkan belajar dari kursus yang terbuka.",
                 bg=C.BG, fg=C.MUTED, font=(C.FONT, 11),
                 anchor="w").pack(fill="x", pady=(4, 20))

        grid = tk.Frame(body, bg=C.BG)
        grid.pack(fill="both", expand=True)

        courses = courses_for(student["program"])  # dewasa / anak punya daftar sendiri
        rows = (len(courses) + COLUMNS - 1) // COLUMNS
        for c in range(COLUMNS):
            grid.columnconfigure(c, weight=1, uniform="col")
        for r in range(rows):
            grid.rowconfigure(r, weight=1, uniform="row")

        # Ukuran judul kartu dibuat sama untuk semua kartu & menyesuaikan lebar jendela
        self.title_font = tkfont.Font(family=C.FONT, size=18, weight="bold")
        self._longest_title = max((c["title"] for c in courses), key=len)
        grid.bind("<Configure>", self._fit_title_font)

        allowed = set(student["courses"])
        for i, course in enumerate(courses):
            card = CourseCard(grid, course,
                              unlocked=course["id"] in allowed,
                              on_open=self.on_open_course,
                              title_font=self.title_font)
            card.grid(row=i // COLUMNS, column=i % COLUMNS,
                      sticky="nsew", padx=8, pady=8)

    def _fit_title_font(self, event):
        avail = event.width / COLUMNS - 16 - 44 - 4  # jarak antar kartu, isi kartu, garis tepi
        for size in (18, 16, 15, 14, 13, 12, 11):
            self.title_font.config(size=size)
            if self.title_font.measure(self._longest_title) <= avail:
                break
