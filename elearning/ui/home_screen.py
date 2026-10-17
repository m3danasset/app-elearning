"""Layar utama setelah login (murid & trial): sidebar kiri + pilihan kursus.
Badge berlaku per kursus (halaman Badges ada di layar kursus). Teks English (layar murid)."""

import tkinter as tk

from elearning import config as C
from elearning.courses import visible_for
from elearning.trial import is_trial
from elearning.ui.course_dock import CourseDock
from elearning.ui.sidebar import (AppSidebar, SidebarLayout, blender_footer,
                                  course_items, student_subtitle)


class HomeScreen(SidebarLayout):
    def __init__(self, master, student, on_open_course, on_logout, view="courses"):
        super().__init__(master)
        self.student = student
        self.on_open_course = on_open_course
        self.trial = is_trial(student)
        self.courses = visible_for(student)   # dewasa / anak / trial, minus yang disembunyikan
        self.allowed = set(student["courses"])
        self.view = "courses"     # badge per kursus: halaman Badges ada di layar kursus
        self.dock = None

        self.sb = AppSidebar(self, student, student_subtitle(student), on_logout,
                             self._populate, placeholder="Search", palette=True,
                             on_search=self._on_search)
        self.attach(self.sb)
        # tanpa kolom cari di bawah: search palette dibuka dari kolom cari sidebar / Ctrl+K
        self._render_view()

    def search_sources(self):
        from elearning.ui.search_sources import student_sources
        return student_sources(self, self.student)

    # --- sidebar ---------------------------------------------------------------------
    def _populate(self, sb):
        # Badge berlaku per kursus: menu Badges ada di sidebar layar kursus, bukan di sini
        sb.nav("All courses", "grid", lambda: self._set_view("courses"),
               active=self.view == "courses")
        if self.trial:   # trial: SATU menu Resources untuk semua kelas (folder resources	rial)
            sb.nav("Resources", "folder", lambda: self._set_view("resource"),
                   active=self.view == "resource")
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
        if self.view == "resource":
            from elearning.ui.file_browser import ResourcePage
            from elearning.ui.sidebar import PageHeader
            PageHeader(self.content, "Resources", "Trial class").pack(fill="x")
            ResourcePage(self.content, {"id": "trial", "title": "Trial", "program": "trial"}
                         ).pack(fill="both", expand=True)
            return
        hello = ("Welcome! Pick a class to try learning."
                 if self.trial else
                 f"Hi, {self.student['name']}! Continue learning from your open courses.")
        # Kartu kursus mendatar di tengah (gaya Dock), latar video opsional
        self.dock = CourseDock(self.content, self.courses, self.allowed, self.on_open_course,
                               "Pick a trial class" if self.trial else "Pick a course", hello)
        self.dock.pack(fill="both", expand=True)
        self._build_grid()

    # --- kartu kursus (ikut tersaring kolom cari) -------------------------------------
    def _build_grid(self):
        if self.dock is None:
            return
        courses = [c for c in self.courses if self.sb.matches(c["title"], c["group"], c["desc"])]
        self.dock.set_courses(courses, f"No courses match "
                                       f"“{self.sb.query.strip()}”.")
