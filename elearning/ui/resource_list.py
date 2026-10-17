"""Resource kelas trial: daftar file langsung tampil (tanpa file browser), klik = buka.

File .blend dibuka dengan Blender aplikasi (lalu mode mengambang seperti tombol Open Blender);
file lain dengan aplikasi bawaan Windows. Isi folder: resources.course_folder (satu folder
bersama untuk semua kelas trial), termasuk subfolder; cadangan Blender (.blend1 ...) disembunyikan.
Satu canvas, hover = tukar gambar baris (tanpa gambar ulang semua -> tidak kedip).
"""

import os
import re
import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import portfolio, resources
from elearning.ui import ui_icons as I
from elearning.ui.widgets import ScrollFrame

ROW_H, GAP = 56, 6
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
    def __init__(self, master, course):
        super().__init__(master, bg=C.BG)
        self.folder = resources.course_folder(course)
        self.files = list_files(self.folder) if os.path.isdir(self.folder) else []
        self._imgs = []
        self._rows = []          # (item gambar, foto biasa, foto hover)
        self._hover = None
        self.f = {"name": tkfont.Font(font=(C.FONT, 11, "bold")),
                  "sub": tkfont.Font(font=(C.FONT, 9)),
                  "msg": tkfont.Font(font=(C.FONT, 10))}
        self.msg = tk.Label(self, text="Click a file to open it. Blender files open in Blender.",
                            bg=C.BG, fg=C.MUTED, font=(C.FONT, 10), anchor="w")
        self.msg.pack(fill="x", padx=28, pady=(4, 8))
        sf = ScrollFrame(self, bg=C.BG)
        sf.pack(fill="both", expand=True, padx=(28, 12), pady=(0, 12))
        self.cv = tk.Canvas(sf.inner, bg=C.BG, highlightthickness=0, bd=0, height=60)
        self.cv.pack(fill="x")
        self.cv.bind("<Configure>", lambda e: self._draw())
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Leave>", lambda e: self._set_hover(None))
        self.cv.bind("<Button-1>", self._click)
        self._last_w = 0

    # --- gambar -----------------------------------------------------------------------------
    def _draw(self):
        W = self.cv.winfo_width()
        if W < 100 or W == self._last_w:
            return
        self._last_w = W
        cv = self.cv
        cv.delete("all")
        self._imgs, self._rows, self._hover = [], [], None
        if not self.files:
            cv.create_text(W / 2, 40, text="No resources for this class yet.", fill=C.MUTED,
                           font=self.f["msg"])
            cv.configure(height=80)
            return
        normal = I.pill(W - 4, ROW_H, C.CARD, C.BG, r=12, border=C.BORDER)
        hover = I.pill(W - 4, ROW_H, C.CARD_HOVER, C.BG, r=12, border=C.BORDER)
        self._imgs += [normal, hover]
        y = 0
        for path, name, rel, size in self.files:
            item = cv.create_image(0, y, image=normal, anchor="nw")
            self._rows.append((item, normal, hover))
            blend = name.lower().endswith(".blend")
            ic = I.icon("play" if blend else "file", C.ACCENT if blend else C.MUTED,
                        C.CARD, 20)
            if ic is not None:
                self._imgs.append(ic)
                cv.create_image(18, y + ROW_H / 2, image=ic, anchor="w")
            cv.create_text(52, y + ROW_H / 2 - 9, text=name, anchor="w", fill=C.TEXT,
                           font=self.f["name"])
            sub = ("Open in Blender" if blend else "Open") + "  ·  " + portfolio.format_size(size)
            if rel:
                sub = f"{rel}  ·  " + sub
            cv.create_text(52, y + ROW_H / 2 + 10, text=sub, anchor="w", fill=C.MUTED,
                           font=self.f["sub"])
            y += ROW_H + GAP
        cv.configure(height=y)

    def _row_at(self, y):
        i = int(y // (ROW_H + GAP))
        if 0 <= i < len(self.files) and y - i * (ROW_H + GAP) < ROW_H:
            return i
        return None

    def _set_hover(self, i):
        if i == self._hover:
            return
        for k, on in ((self._hover, False), (i, True)):
            if k is not None and k < len(self._rows):
                item, normal, hov = self._rows[k]
                self.cv.itemconfigure(item, image=hov if on else normal)
        self._hover = i
        self.cv.configure(cursor="hand2" if i is not None else "")

    def _motion(self, e):
        self._set_hover(self._row_at(e.y))

    # --- buka -------------------------------------------------------------------------------
    def _click(self, e):
        i = self._row_at(e.y)
        if i is None:
            return
        path = self.files[i][0]
        if path.lower().endswith(".blend"):
            self._open_blend(path)
            return
        try:
            portfolio.open_file(path)
        except Exception as exc:
            C.log(f"Resource trial: gagal membuka {path!r}: {exc!r}")
            self.msg.config(text="This file could not be opened.", fg=C.ERROR)

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
