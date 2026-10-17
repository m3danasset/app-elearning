"""Resource kelas trial: daftar file langsung tampil (tanpa file browser), klik = buka.

File .blend dibuka dengan Blender aplikasi (lalu mode mengambang seperti tombol Open Blender);
file lain dengan aplikasi bawaan Windows. Isi folder: resources.course_folder (satu folder
bersama untuk semua kelas trial), termasuk subfolder; cadangan Blender (.blend1 ...) disembunyikan.
Tampilan: kartu seperti kartu kursus di halaman utama (ui/course_dock.CourseDock).
"""

import os
import re
import tkinter as tk

from elearning import config as C
from elearning import portfolio, resources

LIMIT = 300
_HIDE = re.compile(r"\.blend\d+$", re.IGNORECASE)


def list_files(folder):
    """[(path, nama, subfolder relatif, ukuran)] urut subfolder lalu nama."""
    out = []
    for base, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith((".", "_")))
        rel = os.path.relpath(base, folder)
        for n in sorted(names, key=str.lower):
            if n.startswith((".", "~$")) or _HIDE.search(n) or n.lower().endswith((".tmp", ".part")):
                continue
            p = os.path.join(base, n)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            out.append((p, n, "" if rel == "." else rel, size))
            if len(out) >= LIMIT:
                return out
    return out


class ResourceList(tk.Frame):
    """Kartu file berdampingan seperti kartu kursus di halaman utama (CourseDock): klik = buka."""

    def __init__(self, master, course):
        super().__init__(master, bg=C.BG)
        from elearning.ui.course_dock import CourseDock
        self.folder = resources.course_folder(course)
        self.files = list_files(self.folder) if os.path.isdir(self.folder) else []
        cards = []
        for path, name, rel, size in self.files:
            blend = name.lower().endswith(".blend")
            stem = os.path.splitext(name)[0]
            cards.append({"id": path, "title": stem,
                          "group": ("BLENDER FILE" if blend else os.path.splitext(name)[1][1:].upper()
                                    or "FILE"),
                          "desc": "  ·  ".join(t for t in (rel, name, portfolio.format_size(size)) if t),
                          "color": C.ACCENT if blend else C.MUTED,
                          "foot": "Open in Blender  →" if blend else "Open  →"})
        self.dock = CourseDock(self, cards, [c["id"] for c in cards], self._open_card,
                               "Resources",
                               "Click a file to open it. Blender files open in Blender.",
                               foot=("Open  →", ""))
        self.dock.pack(fill="both", expand=True)
        self.dock.set_courses(cards, "No resources for this class yet.")

    def _open_card(self, card):
        path = card["id"]
        if path.lower().endswith(".blend"):
            self._open_blend(path)
            return
        try:
            portfolio.open_file(path)
        except Exception as exc:
            C.log(f"Resource trial: gagal membuka {path!r}: {exc!r}")

    def _open_blend(self, path):
        from elearning import blender_launcher as BL
        app = self.winfo_toplevel()
        if BL.blender_running():
            BL._show_message(app, "info", "Close Blender first",
                             "Blender is already open.\n\nSave your work (Ctrl+S), close Blender, "
                             "then click this file again.")
            return
        if not BL.open_blender(app, [path]):
            return
        tracker = getattr(app, "badges", None)
        if tracker is not None:
            try:
                tracker.event("siap_berkarya")
            except Exception:
                pass
        ctl = getattr(app, "blender_float", None)
        if ctl is not None:     # seperti tombol Open Blender: aplikasi jadi ikon mengambang
            ctl.enter()
