"""Layar utama setelah login (murid & trial): sidebar kiri + pilihan kursus."""

import tkinter as tk

from elearning import config as C
from elearning.courses import courses_for
from elearning.trial import is_trial
from elearning.ui.course_dock import CourseDock
from elearning.ui.sidebar import (AppSidebar, SidebarLayout, blender_footer, course_items,
                                  student_subtitle)


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

        hello = ("Selamat datang, calon murid! Pilih satu kelas untuk mencoba belajar."
                 if self.trial else
                 f"Halo, {student['name']}! Lanjutkan belajar dari kursus yang terbuka.")
        # Kartu kursus mendatar di tengah (gaya Dock), latar video opsional
        self.dock = CourseDock(self.content, self.courses, self.allowed, on_open_course,
                               "Pilih kelas trial" if self.trial else "Pilih kursus", hello)
        self.dock.pack(fill="both", expand=True)
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
        courses = [c for c in self.courses if self.sb.matches(c["title"], c["group"], c["desc"])]
        self.dock.set_courses(courses, f"Tidak ada kursus yang cocok dengan "
                                       f"\u201c{self.sb.query.strip()}\u201d.")
