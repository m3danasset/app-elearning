"""Layar utama setelah login (murid & trial): sidebar kiri + pilihan kursus / halaman Badge."""

import tkinter as tk

from elearning import achievements
from elearning import config as C
from elearning.courses import courses_for
from elearning.trial import is_trial
from elearning.ui.course_dock import CourseDock
from elearning.ui.sidebar import (AppSidebar, PageHeader, SidebarLayout, blender_footer,
                                  course_items, student_subtitle)
from elearning.ui.widgets import ScrollFrame


class HomeScreen(SidebarLayout):
    def __init__(self, master, student, on_open_course, on_logout, view="courses"):
        super().__init__(master)
        self.student = student
        self.on_open_course = on_open_course
        self.trial = is_trial(student)
        self.courses = courses_for(student["program"])   # dewasa / anak / trial
        self.allowed = set(student["courses"])
        self.view = "courses" if self.trial else view    # "courses" atau "badges"
        self.dock = None

        self.sb = AppSidebar(self, student, student_subtitle(student), on_logout,
                             self._populate, placeholder="Cari kursus",
                             on_search=self._on_search)
        self.attach(self.sb)
        self._render_view()

    # --- sidebar ---------------------------------------------------------------------
    def _populate(self, sb):
        sb.nav("Semua kursus", "grid", lambda: self._set_view("courses"),
               active=self.view == "courses")
        if not self.trial:     # akun trial dipakai bersama: tanpa badge
            got, total = achievements.summary(self.student)
            sb.nav("Badge", "award", lambda: self._set_view("badges"),
                   active=self.view == "badges", right=f"{got}/{total}")
        course_items(sb, self.courses, self.allowed, None, self.on_open_course)
        blender_footer(sb)

    def _on_search(self, _query):
        self.sb.refresh(keep_scroll=False)
        if self.view == "courses":
            self._build_grid()

    # --- isi kanan: kursus / badge -------------------------------------------------------
    def _set_view(self, view):
        if view == self.view:
            return
        self.view = view
        self._render_view()
        self.sb.refresh()

    def _render_view(self):
        for w in self.content.winfo_children():
            w.destroy()
        self.dock = None
        if self.view == "badges":
            PageHeader(self.content, "Badge",
                       "Kumpulkan badge dengan belajar, berkarya, dan rajin datang.").pack(fill="x")
            scroll = ScrollFrame(self.content, bg=C.BG)
            scroll.pack(fill="both", expand=True, padx=(28, 12), pady=(4, 12))
            from elearning.ui.badge_ui import BadgeBoard
            BadgeBoard(scroll.inner, self.student).pack(fill="x", pady=(0, 12))
            return
        hello = ("Selamat datang, calon murid! Pilih satu kelas untuk mencoba belajar."
                 if self.trial else
                 f"Halo, {self.student['name']}! Lanjutkan belajar dari kursus yang terbuka.")
        # Kartu kursus mendatar di tengah (gaya Dock), latar video opsional
        self.dock = CourseDock(self.content, self.courses, self.allowed, self.on_open_course,
                               "Pilih kelas trial" if self.trial else "Pilih kursus", hello)
        self.dock.pack(fill="both", expand=True)
        self._build_grid()

    # --- kartu kursus (ikut tersaring kolom cari) -------------------------------------
    def _build_grid(self):
        if self.dock is None:
            return
        courses = [c for c in self.courses if self.sb.matches(c["title"], c["group"], c["desc"])]
        self.dock.set_courses(courses, f"Tidak ada kursus yang cocok dengan "
                                       f"“{self.sb.query.strip()}”.")
