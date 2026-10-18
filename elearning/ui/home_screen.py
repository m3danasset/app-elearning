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
        # "courses", atau "resource" (trial: satu halaman Resources untuk semua kelas trial)
        self.view = "resource" if (self.trial and view == "resource") else "courses"
        self.dock = None
        # menu flashdisk (murid SK / PB / IC, bukan trial / murid AI): satu menu per USB
        from elearning.courses import ai_only
        self.usb_ok = not self.trial and not ai_only(student)
        self.drives = []
        self._usb_stop = None

        self.sb = AppSidebar(self, student, student_subtitle(student), on_logout,
                             self._populate, placeholder="Search", palette=True,
                             on_search=self._on_search)
        self.attach(self.sb)
        # tanpa kolom cari di bawah: search palette dibuka dari kolom cari sidebar / Ctrl+K
        self._render_view()
        if self.usb_ok:
            from elearning.ui import usb_save
            self._usb_stop = usb_save.monitor(self).subscribe(self._drives_changed)

    def search_sources(self):
        from elearning.ui.search_sources import student_sources
        return student_sources(self, self.student)

    # --- sidebar ---------------------------------------------------------------------
    def _populate(self, sb):
        # Badge berlaku per kursus: menu Badges ada di sidebar layar kursus, bukan di sini
        sb.nav("Dashboard", "home", lambda: self._set_view("courses"),
               active=self.view == "courses")
        from elearning.ui.usb_save import drive_name
        for d in self.drives:           # nama flashdisk, mis. "KINGSTON (E:)"
            sb.nav(drive_name(d), "usb", lambda r=d[0]: self._set_view("usb:" + r),
                   active=self.view == "usb:" + d[0])
        if self.trial:   # trial: SATU menu Resources untuk semua kelas (folder resources/trial)
            sb.nav("Resources", "folder", lambda: self._set_view("resource"),
                   active=self.view == "resource")
        course_items(sb, self.courses, self.allowed, None, self.on_open_course)
        blender_footer(sb)

    def _drives_changed(self, drives):
        """Flashdisk dicolok / dicabut / dikeluarkan: menu sidebar ikut berubah."""
        old = [(d[0], d[1]) for d in self.drives]
        self.drives = list(drives)
        if self.view.startswith("usb:") and \
                not any("usb:" + d[0] == self.view for d in self.drives):
            from elearning.ui.search_palette import close_palette
            close_palette()               # file browser USB yang terbuka ikut ditutup
            self.view = "courses"
            self._render_view()
            self.sb.refresh()
        elif [(d[0], d[1]) for d in self.drives] != old:
            self.sb.refresh()

    def destroy(self):
        if self._usb_stop is not None:
            self._usb_stop()
        super().destroy()

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
        if self.view.startswith("usb:"):
            from elearning.ui.file_browser import UsbPage
            drive = next((d for d in self.drives if "usb:" + d[0] == self.view), None)
            if drive is not None:
                UsbPage(self.content, drive).pack(fill="both", expand=True)
                return
            self.view = "courses"
        if self.view == "resource":
            from elearning.ui.resource_list import ResourceList
            # trial: daftar file langsung (klik = buka, .blend di Blender), tanpa file browser
            ResourceList(self.content, {"id": "trial", "title": "Trial", "program": "trial"}
                         ).pack(fill="both", expand=True)
            return
        # Dashboard murid (gaya Dashboard admin / guru): sapaan besar + tanggal, kartu kursus
        from datetime import datetime
        now = datetime.now()
        if self.trial:
            title, hello = "Welcome!", "Pick a class to try learning."
        else:
            greet = ("Good morning" if now.hour < 11 else "Good afternoon" if now.hour < 18
                     else "Good evening")
            title = f"{greet}, {self.student['name'].split()[0]}"
            hello = f"{now.strftime('%A, %d %B %Y')}  ·  Pick a course to continue learning"
        # Kartu kursus mendatar di tengah (gaya Dock), latar video opsional; widget USB untuk
        # murid SUPERKIDS / BASIC / INTERMEDIATE (bukan trial, bukan murid AI)
        from elearning.courses import ai_only
        self.dock = CourseDock(self.content, self.courses, self.allowed, self.on_open_course,
                               title, hello, hero=True,
                               usb=not self.trial and not ai_only(self.student))
        self.dock.pack(fill="both", expand=True)
        self._build_grid()

    # --- kartu kursus (ikut tersaring kolom cari) -------------------------------------
    def _build_grid(self):
        if self.dock is None:
            return
        courses = [c for c in self.courses if self.sb.matches(c["title"], c["group"], c["desc"])]
        self.dock.set_courses(courses, f"No courses match "
                                       f"“{self.sb.query.strip()}”.")
