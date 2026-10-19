"""Halaman "Kursus" di jendela Dev: panel kursus (buat / ubah / urutkan / hapus / pulihkan,
untuk kurikulum yang berganti) + MASTER TOGGLE akses murid.

Akses murid = tabel di SATU kanvas: baris = murid program yang dipilih (disaring kolom
Search Dev), kolom = "Semua kursus" + tiap kursus. Tiap sel dua ikon: MATA = kursus tampil
di halaman murid (students.json "hidden"), GEMBOK = kursus terbuka ("courses"). Ikon di
kepala kolom / awal baris / pojok kiri atas = master: semua murid yang tampil x kursus itu
(semua tercentang -> dimatikan, selain itu -> dinyalakan). Setiap perubahan langsung
disimpan SEKALI tulis (students.bulk_access) dan bisa diurungkan (Urungkan, bertingkat).
Gaya sama dengan jendela Dev (Settings Claude), tanpa animasi.
"""

import os
import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import courses as K
from elearning.ui import dev_panel as DP
from elearning.ui import ui_icons as I

PANEL, FG, MUTED, LINE = DP.PANEL, DP.FG, DP.MUTED, DP.LINE
DIM = "#6f6c64"            # ikon mati
GREEN = "#3fb68b"          # gembok terbuka
HOV = DP.NAV_HOV
UNDO_MAX = 30


def _photo(img, keep):
    if img is not None:
        keep.append(img)
    return img


class IconBtn(tk.Canvas):
    """Tombol ikon 30 x 30 (sorot pill saat kursor di atas)."""

    def __init__(self, master, icon, command, tip_color=FG, bg=PANEL, danger=False):
        super().__init__(master, width=30, height=30, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.icon, self.command, self._bg = icon, command, bg
        self.color = "#ff6b6b" if danger else tip_color
        self.enabled = True
        self._imgs = []
        self.bind("<Button-1>", lambda e: self.enabled and self.command())
        self.bind("<Enter>", lambda e: self._draw(True))
        self.bind("<Leave>", lambda e: self._draw(False))
        self._draw(False)

    def set_enabled(self, on):
        self.enabled = on
        self.configure(cursor="hand2" if on else "arrow")
        self._draw(False)

    def _draw(self, hov):
        self.delete("all")
        self._imgs = []
        hov = hov and self.enabled
        bg = HOV if hov else self._bg
        if hov:
            self.create_image(0, 0, anchor="nw", image=_photo(DP._pill(30, 30, bg, self._bg, r=8),
                                                               self._imgs))
        col = (self.color if hov else MUTED) if self.enabled else "#4a4945"
        ic = _photo(I.icon(self.icon, col, bg, 18), self._imgs)
        if ic is not None:
            self.create_image(15, 15, image=ic)


class CoursesPage(tk.Frame):
    ROW_H, HEAD_H, NAME_W, CELL_MIN = 36, 82, 180, 66
    MASTER_Y = 48                     # ikon master di kepala kolom
    BTN = 26                          # kotak ikon di sel

    def __init__(self, panel, parent):
        from elearning.ui.widgets import DarkScrollbar
        super().__init__(parent, bg=PANEL)
        self.panel = panel
        self.prog = DP._ui_state().get("crs_prog") or "adult"
        if self.prog not in dict(K.PROGRAMS):
            self.prog = "adult"
        self._undo = []
        self._hov = None              # (baris, kolom, jenis) yang disorot
        self._refresh_job = None
        self._changed_ids = set()
        self.f_head = tkfont.Font(family=C.FONT, size=8, weight="bold")
        self.f_name = tkfont.Font(family=C.FONT, size=10)
        self.f_id = tkfont.Font(family="Consolas", size=9)
        cv = self.cv = tk.Canvas(self, bg=PANEL, highlightthickness=0, bd=0)
        sb = DarkScrollbar(self, command=cv.yview, bg=PANEL)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 6))
        cv.pack(fill="both", expand=True)
        inner = self.inner = tk.Frame(cv, bg=PANEL)
        self._win = cv.create_window(28, 0, window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", self._on_width)
        self._build()

    # --- kerangka ----------------------------------------------------------------------
    def _build(self):
        f = self.inner
        tk.Label(f, text="Kursus", bg=PANEL, fg=FG, font=(C.FONT, 14, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(f, text="Buat dan hapus panel kursus saat kurikulum berganti, lalu atur murid "
                         "mana yang melihat dan membuka tiap kursus. Semua perubahan langsung "
                         "tersimpan.", bg=PANEL, fg=MUTED, font=(C.FONT, 10), anchor="w",
                 justify="left", wraplength=640).pack(fill="x", pady=(2, 14))
        bar = tk.Frame(f, bg=PANEL)
        bar.pack(fill="x")
        self.seg = DP.Seg(bar, K.PROGRAMS, self.prog, self._set_prog)
        self.seg.pack(side="left")
        self.count_lbl = tk.Label(bar, text="", bg=PANEL, fg=MUTED, font=(C.FONT, 10))
        self.count_lbl.pack(side="right")
        self._section(f, "Panel kursus",
                      "Urutan di sini = urutan kartu di halaman murid. Data murid (progres, "
                      "badge, portfolio, video) tidak ikut terhapus bersama kursus.")
        self.list = tk.Frame(f, bg=PANEL)
        self.list.pack(fill="x")
        self.removed = tk.Frame(f, bg=PANEL)
        self.removed.pack(fill="x")
        self.acc_head = self._section(
            f, "Akses murid",
            "Mata = kursus tampil di halaman murid, gembok = kursus terbuka. Ikon di kepala "
            "kolom = kursus itu untuk semua murid; kolom Semua kursus = semua kursus murid "
            "itu; kepala Semua kursus = semuanya. Hanya murid yang tersaring kolom Search.")
        self.grid_cv = tk.Canvas(f, bg=PANEL, highlightthickness=0, bd=0, height=80)
        self.grid_cv.pack(fill="x", pady=(4, 20))
        # lebar tabel baru final setelah tata letak: gambar ulang SELURUHNYA saat lebar berubah
        # (dulu hanya baris yang digambar ulang saat disorot -> kolom bergeser dari judulnya)
        self._grid_w = None
        self.grid_cv.bind("<Configure>", self._on_grid_width)
        self.grid_cv.bind("<Motion>", self._motion)
        self.grid_cv.bind("<Leave>", lambda e: self._set_hov(None))
        self.grid_cv.bind("<Button-1>", self._click)
        self.empty = tk.Label(f, text="", bg=PANEL, fg=MUTED, font=(C.FONT, 10), anchor="w",
                              justify="left")

    def _section(self, f, title, desc):
        box = tk.Frame(f, bg=PANEL)
        box.pack(fill="x", pady=(24, 6))
        tk.Label(box, text=title, bg=PANEL, fg=FG, font=(C.FONT, 12, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(box, text=desc, bg=PANEL, fg=MUTED, font=(C.FONT, 9), anchor="w",
                 justify="left", wraplength=640).pack(fill="x", pady=(2, 0))
        return box

    def _on_width(self, e):
        self.cv.itemconfigure(self._win, width=max(300, e.width - 56))
        self.after_idle(self._draw_grid)

    def _on_grid_width(self, e):
        if e.width != self._grid_w:
            self._grid_w = e.width
            self._draw_grid()

    def _set_prog(self, prog):
        self.prog = prog
        self.seg.set(prog)
        DP._ui_save(crs_prog=prog)
        self.refresh()
        self.cv.yview_moveto(0)

    # --- isi -----------------------------------------------------------------------------
    def refresh(self):
        """Muat ulang murid + kursus program ini, gambar ulang daftar & tabel."""
        from elearning.students import list_students
        self.all_courses = [c for c in K.COURSES if c["program"] == self.prog]
        self.courses = list(self.all_courses)
        self.students = [s for s in list_students() if s["program"] == self.prog]
        self._fill_list()
        self.filter()

    def filter(self, switched=False):
        """Kolom Search: kata yang cocok dengan murid (ID / nama) menyaring baris; kata yang
        hanya cocok dengan kursus (judul / ID / grup) menyaring kolom. Tidak ada murid cocok di
        program ini tapi ada di program lain -> pindah ke program itu."""
        words = self.panel._q.get().lower().split()

        def stext(s):
            return f"{s['id']} {s['name']}".lower()

        def ctext(c):
            return f"{c['id']} {c['title']} {c['group']}".lower()
        cwords = [w for w in words if not any(w in stext(s) for s in self.students)
                  and any(w in ctext(c) for c in self.all_courses)]
        swords = [w for w in words if w not in cwords]
        self.courses = [c for c in self.all_courses if all(w in ctext(c) for w in cwords)]
        self.shown = [s for s in self.students if all(w in stext(s) for w in swords)]
        if words and not self.shown and not switched and self.prog != "trial":
            from elearning.students import list_students
            for prog, label in K.PROGRAMS:
                if prog in (self.prog, "trial"):
                    continue
                if any(s["program"] == prog and all(w in stext(s) for w in words)
                       for s in list_students()):
                    self._set_prog(prog)
                    self.filter(switched=True)
                    self.panel._note(f"Ditemukan di program {label}.")
                    return
        if self.prog == "trial":
            self.count_lbl.config(text="")
        elif words:
            extra = (f"  ·  {len(self.courses)} dari {len(self.all_courses)} kursus"
                     if cwords else "")
            self.count_lbl.config(text=f"{len(self.shown)} dari {len(self.students)} murid"
                                  + extra)
        else:
            self.count_lbl.config(text=f"{len(self.students)} murid")
        self._draw_grid()

    def _fill_list(self):
        from elearning import progress
        for w in self.list.winfo_children() + self.removed.winfo_children():
            w.destroy()
        for fr in (self.list, self.removed):     # frame kosong tidak menyusut sendiri di Tk
            fr.configure(height=1)
        self._limgs = []
        opened = {c["id"]: 0 for c in self.all_courses}
        hidden = dict(opened)
        for s in self.students:
            for cid in s["courses"]:
                if cid in opened:
                    opened[cid] += 1
            for cid in s.get("hidden") or ():
                if cid in hidden:
                    hidden[cid] += 1
        n = len(self.all_courses)
        for i, c in enumerate(self.all_courses):
            row = tk.Frame(self.list, bg=PANEL)
            row.pack(fill="x")
            dot = tk.Label(row, bg=PANEL,
                           image=_photo(I.dot(c["color"], PANEL, 14, 6.5), self._limgs))
            dot.pack(side="left", padx=(2, 12), pady=12)
            left = tk.Frame(row, bg=PANEL)
            left.pack(side="left", fill="x", expand=True, pady=8)
            tk.Label(left, text=c["title"], bg=PANEL, fg=FG, font=(C.FONT, 11, "bold"),
                     anchor="w").pack(fill="x")
            if K.has_video(c):
                nv = len(progress.lesson_titles(c))
                vid = f"{nv} video" if nv else "belum ada video"
            else:
                vid = "tanpa video"
            if self.prog == "trial":
                acc = "semua akun trial"
            else:
                acc = f"{opened[c['id']]} buka · {hidden[c['id']]} sembunyi"
            tk.Label(left, text=f"{c['id']}  ·  {c['group']}  ·  {vid}  ·  {acc}", bg=PANEL,
                     fg=MUTED, font=(C.FONT, 9), anchor="w").pack(fill="x")
            btns = tk.Frame(row, bg=PANEL)
            btns.pack(side="right")
            up = IconBtn(btns, "chev_up", lambda c=c: self._move(c, -1))
            down = IconBtn(btns, "chev_down", lambda c=c: self._move(c, 1))
            up.set_enabled(i > 0)
            down.set_enabled(i < n - 1)
            for b in (up, down, IconBtn(btns, "pen", lambda c=c: CourseEditor(self, c)),
                      IconBtn(btns, "trash", lambda c=c: CourseDelete(self, c), danger=True)):
                b.pack(side="left", padx=1)
            tk.Frame(self.list, bg=LINE, height=1).pack(fill="x")
        if not self.all_courses:
            tk.Label(self.list, text="Belum ada kursus untuk program ini. Klik \"Kursus baru\".",
                     bg=PANEL, fg=MUTED, font=(C.FONT, 10), anchor="w").pack(fill="x", pady=10)
        gone = [c for c in K.removed_builtins() if c["program"] == self.prog]
        if gone:
            tk.Label(self.removed, text="Kursus bawaan yang dihapus", bg=PANEL, fg=MUTED,
                     font=(C.FONT, 9), anchor="w").pack(fill="x", pady=(14, 4))
            for c in gone:
                row = tk.Frame(self.removed, bg=PANEL)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"{c['title']}   ({c['id']})", bg=PANEL, fg=DIM,
                         font=(C.FONT, 10), anchor="w").pack(side="left")
                DP._btn(row, "Pulihkan", lambda c=c: self._restore(c)).pack(side="right")

    # --- tabel akses -------------------------------------------------------------------
    ALL_W = 76                        # kolom "Semua kursus" (sempit: ruang untuk judul kursus)

    def _geo(self):
        """(lebar kolom nama, lebar kolom kursus). Sisa lebar dibagi ke kolom kursus."""
        w = max(300, self.grid_cv.winfo_width())
        n = max(1, len(self.courses))
        cell = max(self.CELL_MIN, (w - self.NAME_W - self.ALL_W) // n)
        return self.NAME_W, cell

    def _cx(self, col):
        """Tengah kolom col (0 = Semua kursus, 1.. = kursus)."""
        name_w, cell = self._geo()
        if col == 0:
            return name_w + self.ALL_W / 2
        return name_w + self.ALL_W + (col - 1) * cell + cell / 2

    def _width(self):
        name_w, cell = self._geo()
        return name_w + self.ALL_W + cell * len(self.courses)

    def _col_at(self, x):
        name_w, cell = self._geo()
        if x < name_w:
            return -1
        if x < name_w + self.ALL_W:
            return 0
        return 1 + int((x - name_w - self.ALL_W) // cell)

    def _draw_grid(self):
        g = self.grid_cv
        g.delete("all")
        self._gimgs = []
        if self.prog == "trial" or not self.courses or not self.shown:
            g.configure(height=1)
            if self.prog == "trial":
                text = "Kursus trial terlihat dan terbuka untuk semua akun trial."
            elif not self.courses:
                text = ""
            elif not self.students:
                text = "Belum ada murid di program ini."
            else:
                text = "Tidak ada murid yang cocok dengan kolom Cari."
            self.empty.config(text=text)
            if text:
                self.empty.pack(fill="x", after=self.grid_cv, pady=(0, 20))
            else:
                self.empty.pack_forget()
            return
        self.empty.pack_forget()
        rows = len(self.shown)
        h = self.HEAD_H + rows * self.ROW_H + 2
        g.configure(height=h)
        name_w, cell = self._geo()
        W = self._width()
        # kepala
        g.create_text(8, 26, text="Murid", anchor="w", font=self.f_head, fill=MUTED)
        heads = [("Semua kursus", None)] + [(c["title"], c["color"]) for c in self.courses]
        for col, (title, color) in enumerate(heads):
            tx = self._cx(col)
            cw = self.ALL_W if col == 0 else cell
            if color:
                g.create_image(tx, 7, image=_photo(I.dot(color, PANEL, 8, 3.6), self._gimgs))
            g.create_text(tx, 27, text=self._wrap2(title, cw - 6), font=self.f_head,
                          fill=FG if color else MUTED, justify="center")
            self._master_btns(col - 1, tx - self.BTN - 1, self.MASTER_Y)
        g.create_line(0, self.HEAD_H - 1, W, self.HEAD_H - 1, fill=LINE)
        # garis kolom "Semua kursus"
        g.create_line(name_w + self.ALL_W, 4, name_w + self.ALL_W, h, fill=LINE)
        for r in range(rows):
            self._draw_row(r)

    def _master_btns(self, ci, x, y):
        """Ikon master (mata + gembok) di kepala kolom: semua murid yang tampil x kursus ci
        (-1 = kolom "Semua kursus" = semua murid x semua kursus)."""
        for k, kind in enumerate(("vis", "open")):
            state = self._state(None, ci, kind)
            self._icon_box(x + k * (self.BTN + 2), y, kind, state, master=True,
                           hov=self._hov == (None, ci, kind), tag="head")

    def _draw_row(self, r):
        g = self.grid_cv
        tag = f"r{r}"
        g.delete(tag)
        name_w, cell = self._geo()
        W = self._width()
        y0 = self.HEAD_H + r * self.ROW_H
        hov_row = self._hov is not None and self._hov[0] == r
        bg = HOV if hov_row else PANEL
        if hov_row:
            g.create_image(0, y0 + 2, anchor="nw", tags=tag,
                           image=_photo(DP._pill(W, self.ROW_H - 4, HOV, PANEL, r=8), self._gimgs))
        s = self.shown[r]
        cy = y0 + self.ROW_H / 2
        g.create_text(10, cy, text=s["id"], anchor="w", font=self.f_id, fill=MUTED, tags=tag)
        g.create_text(10 + self.f_id.measure("0") * 8, cy,
                      text=self._fit(s["name"], name_w - self.f_id.measure("0") * 8 - 20,
                                     self.f_name),
                      anchor="w", font=self.f_name, fill=FG, tags=tag)
        for col in range(len(self.courses) + 1):
            x0 = self._cx(col) - self.BTN - 1
            for k, kind in enumerate(("vis", "open")):
                self._icon_box(x0 + k * (self.BTN + 2), y0 + (self.ROW_H - self.BTN) / 2, kind,
                               self._state(r, col - 1, kind), master=col == 0,
                               hov=self._hov == (r, col - 1, kind), tag=tag, bg=bg)
        g.create_line(0, y0 + self.ROW_H, W, y0 + self.ROW_H, fill=LINE, tags=tag)

    def _icon_box(self, x, y, kind, state, master, hov, tag, bg=PANEL):
        """state: True semua / False tidak ada / None campuran."""
        g, B = self.grid_cv, self.BTN
        on_icon, off_icon = ("eye", "eye_off") if kind == "vis" else ("unlock", "lock")
        on_col = FG if kind == "vis" else GREEN
        fill = None
        if hov:
            fill = "#3a3935"
        elif master and state is not False:
            fill = DP.SEG_ON if state else None
        if fill or (master and state is None):
            img = DP._pill(B, B, fill or bg, bg, r=7,
                           border=DP.SEG_LINE if (master and state is None) else None)
            g.create_image(x, y, anchor="nw", image=_photo(img, self._gimgs), tags=tag)
        ibg = fill or bg
        if state is None:
            ic = I.icon(on_icon, MUTED, ibg, 16)
        else:
            ic = I.icon(on_icon if state else off_icon, on_col if state else DIM, ibg, 16)
        if ic is not None:
            g.create_image(x + B / 2, y + B / 2, image=_photo(ic, self._gimgs), tags=tag)

    def _wrap2(self, text, px):
        """Judul kolom maks. 2 baris selebar px (baris ke-2 dipotong dengan ...)."""
        f, lines, cur = self.f_head, [], ""
        for word in text.split():
            test = f"{cur} {word}".strip()
            if cur and f.measure(test) > px:
                lines.append(cur)
                cur = word
            else:
                cur = test
        lines.append(cur)
        if len(lines) > 2:
            lines = [lines[0], " ".join(lines[1:])]
        return "\n".join(self._fit(t, px, f) for t in lines)

    @staticmethod
    def _fit(text, px, f):
        if f.measure(text) <= px:
            return text
        while text and f.measure(text + "…") > px:
            text = text[:-1]
        return text + "…"

    # status: baris r (None = semua yang tampil), kolom ci (-1 = semua kursus)
    def _targets(self, r, ci):
        studs = self.shown if r is None else [self.shown[r]]
        cids = [c["id"] for c in self.courses] if ci < 0 else [self.courses[ci]["id"]]
        return studs, cids

    @staticmethod
    def _is_on(s, cid, kind):
        if kind == "vis":
            return cid not in (s.get("hidden") or ())
        return cid in s["courses"]

    def _state(self, r, ci, kind):
        studs, cids = self._targets(r, ci)
        vals = {self._is_on(s, cid, kind) for s in studs for cid in cids}
        if len(vals) != 1:
            return None if vals else False
        return vals.pop()

    def _hit(self, x, y):
        name_w, cell = self._geo()
        ncol = len(self.courses) + 1
        B = self.BTN
        if y < self.HEAD_H:
            r, by = None, self.MASTER_Y
        else:
            r = int((y - self.HEAD_H) // self.ROW_H)
            if not 0 <= r < len(self.shown):
                return None
            by = self.HEAD_H + r * self.ROW_H + (self.ROW_H - B) / 2
        col = self._col_at(x)
        if not 0 <= col < ncol or not by <= y < by + B:
            return None
        x0 = self._cx(col) - B - 1
        k = int((x - x0) // (B + 2)) if x >= x0 else -1
        if k not in (0, 1) or x - x0 - k * (B + 2) > B:
            return None
        return (r, col - 1, ("vis", "open")[k])

    def _motion(self, e):
        self._set_hov(self._hit(e.x, e.y), row=self._row_at(e.y))

    def _row_at(self, y):
        if y < self.HEAD_H:
            return None
        r = int((y - self.HEAD_H) // self.ROW_H)
        return r if 0 <= r < len(self.shown) else None

    def _set_hov(self, hit, row=None):
        """Sorot baris di bawah kursor + ikon di bawah kursor (hanya baris itu digambar ulang)."""
        new = hit if hit is not None else ((row, None, None) if row is not None else None)
        if new == self._hov:
            return
        old, self._hov = self._hov, new
        self.grid_cv.configure(cursor="hand2" if hit else "")
        for h in (old, new):
            if h is None:
                continue
            if h[0] is None:
                self._redraw_head()
            elif h[0] < len(self.shown):
                self._draw_row(h[0])

    def _redraw_head(self):
        self.grid_cv.delete("head")
        for col in range(len(self.courses) + 1):
            self._master_btns(col - 1, self._cx(col) - self.BTN - 1, self.MASTER_Y)

    def _click(self, e):
        hit = self._hit(e.x, e.y)
        if hit is None:
            return
        r, ci, kind = hit
        studs, cids = self._targets(r, ci)
        turn_on = self._state(r, ci, kind) is not True
        self._apply(studs, cids, kind, turn_on)

    def _apply(self, studs, cids, kind, turn_on):
        from elearning import students as ST
        changes, before = {}, {}
        for s in studs:
            opened, hidden = set(s["courses"]), set(s.get("hidden") or ())
            for cid in cids:
                if kind == "open":
                    (opened.add if turn_on else opened.discard)(cid)
                else:
                    (hidden.discard if turn_on else hidden.add)(cid)
            if opened != set(s["courses"]) or hidden != set(s.get("hidden") or ()):
                before[s["id"]] = (list(s["courses"]), list(s.get("hidden") or ()))
                changes[s["id"]] = (sorted(opened, key=K.order_of),
                                    sorted(hidden, key=K.order_of))
        if not changes:
            return
        try:
            ST.bulk_access(changes)
        except OSError as exc:
            C.log(f"Dev: akses kursus gagal disimpan: {exc!r}")
            self.panel._note("Gagal menyimpan (folder data?).")
            return
        self._undo.append(before)
        del self._undo[:-UNDO_MAX]
        self._after_access(changes)
        what = ("dibuka" if turn_on else "dikunci") if kind == "open" else \
            ("ditampilkan" if turn_on else "disembunyikan")
        names = ", ".join(K.title_of(c) for c in cids) if len(cids) <= 2 else \
            f"{len(cids)} kursus"
        self.panel._note(f"{names} {what} untuk {len(changes)} murid. Urungkan = kembalikan.")

    def undo(self):
        from elearning import students as ST
        if not self._undo:
            self.panel._note("Tidak ada yang bisa diurungkan.")
            return
        before = self._undo.pop()
        try:
            ST.bulk_access(before)
        except OSError as exc:
            C.log(f"Dev: urungkan akses gagal: {exc!r}")
            self.panel._note("Gagal menyimpan (folder data?).")
            self._undo.append(before)
            return
        self._after_access(before)
        self.panel._note(f"Diurungkan ({len(before)} murid).")

    def _after_access(self, changes):
        for s in self.students:
            if s["id"] in changes:
                s["courses"], s["hidden"] = (list(changes[s["id"]][0]),
                                             list(changes[s["id"]][1]))
        self._fill_list()
        self._draw_grid()
        self.panel.undo_btn_state(bool(self._undo))
        self._changed_ids.update(changes)
        self._schedule_app()

    # --- aplikasi ikut berubah --------------------------------------------------------
    def _schedule_app(self, courses_changed=False):
        """Murid yang sedang login ikut diperbarui (digabung: sekali per 500 ms)."""
        self._courses_changed = getattr(self, "_courses_changed", False) or courses_changed
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(500, self._refresh_app)

    def _refresh_app(self):
        from elearning import students as ST
        from elearning.ui.course_screen import CourseScreen
        self._refresh_job = None
        ids, self._changed_ids = self._changed_ids, set()
        courses_changed, self._courses_changed = self._courses_changed, False
        app = self.panel.app
        cur = getattr(app, "_student", None)
        try:
            if cur is not None and cur.get("id") in ids:
                fresh = ST.lookup_student(cur["id"])
                if fresh is not None:
                    app._student = fresh
                    scr = getattr(app, "_screen", None)
                    if scr is not None and getattr(scr, "student", None) is not None:
                        scr.student = fresh
            elif not courses_changed:
                return
            scr = getattr(app, "_screen", None)
            if isinstance(scr, CourseScreen):
                course = K.by_id(scr.course["id"])
                st = scr.student
                gone = course is None or (st.get("program") != "trial" and (
                    course["id"] not in st.get("courses", ())
                    or course["id"] in (st.get("hidden") or ())))
                if gone:                     # kursus dihapus / dikunci: kembali ke Dashboard
                    app.show_home(st)
                    return
                scr.course = course
            app.rebuild_screen()
        except Exception as exc:
            C.log(f"Dev: layar tidak dibangun ulang setelah ubah kursus: {exc!r}")

    # --- panel kursus ------------------------------------------------------------------
    def course_saved(self, text):
        self.refresh()
        self.panel._note(text)
        self._schedule_app(courses_changed=True)

    def _move(self, c, step):
        try:
            if K.move_course(c["id"], step):
                self.course_saved(f"Urutan {c['title']} diubah.")
        except OSError as exc:
            C.log(f"Dev: urutan kursus gagal disimpan: {exc!r}")
            self.panel._note("Gagal menyimpan (folder data?).")

    def _restore(self, c):
        try:
            K.restore_builtin(c["id"])
        except (ValueError, OSError) as exc:
            self.panel._note(str(exc) if isinstance(exc, ValueError) else
                             "Gagal menyimpan (folder data?).")
            return
        C.log(f"Dev: kursus bawaan {c['id']} dipulihkan")
        self.course_saved(f"{c['title']} dipulihkan.")

    def new_course(self):
        CourseEditor(self, None)


# --- dialog --------------------------------------------------------------------------------
class _Card(tk.Toplevel):
    """Kartu dialog bersudut bulat gaya jendela Dev, di tengah panel, selalu di atas."""

    def __init__(self, page, w, h):
        super().__init__(page.panel)
        self.page, self.W, self.H = page, w, h
        self.withdraw()
        self.attributes("-topmost", True)
        self.body = DP._rounded_window(self, w, h)
        p = page.panel
        self.geometry(f"{w}x{h}+{p.winfo_rootx() + (p.winfo_width() - w) // 2}"
                      f"+{p.winfo_rooty() + max(20, (p.winfo_height() - h) // 2)}")
        self.bind("<Escape>", lambda e: self.destroy())

    def show(self, focus):
        self.deiconify()
        self.lift()
        self.after(10, lambda: (self.focus_force(), focus.focus_set()))


class CourseEditor(_Card):
    """Buat kursus baru / ubah kursus (judul, grup, deskripsi, warna, video)."""

    def __init__(self, page, course):
        from elearning.ui.controls import RoundEntry
        from elearning.ui.widgets import Switch
        super().__init__(page, 520, 600 if course is None else 540)
        self.course = course
        new = course is None
        c = course or {"program": page.prog, "title": "", "id": "", "group": "", "desc": "",
                       "desc_en": "", "color": K.BLUE}
        b = tk.Frame(self.body, bg=PANEL)
        b.pack(fill="both", expand=True, padx=22, pady=(16, 16))
        DP._draggable(self, b)
        tk.Label(b, text="Kursus baru" if new else f"Edit kursus {c['title']}", bg=PANEL,
                 fg=FG, font=(C.FONT, 14, "bold"), anchor="w").pack(fill="x")
        tk.Label(b, text=("Panel kursus baru muncul di halaman murid program ini (terkunci "
                          "sampai dibuka di Akses murid)." if new else
                          f"ID {c['id']} dan program tidak bisa diubah."), bg=PANEL, fg=MUTED,
                 font=(C.FONT, 9), anchor="w", justify="left", wraplength=470).pack(
            fill="x", pady=(2, 10))
        grid = tk.Frame(b, bg=PANEL)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        self.v = {k: tk.StringVar(value=c.get(k, "")) for k in
                  ("title", "id", "group", "desc", "desc_en")}
        self.prog, self.color = c["program"], c["color"]
        self.video = K.has_video(c) if not new else True
        self._id_auto = new

        def label(r, text, hint=""):
            box = tk.Frame(grid, bg=PANEL)
            box.grid(row=r, column=0, sticky="nw", padx=(0, 14), pady=(9, 5))
            tk.Label(box, text=text, bg=PANEL, fg=FG, font=(C.FONT, 10), anchor="w").pack(
                fill="x")
            if hint:
                tk.Label(box, text=hint, bg=PANEL, fg=MUTED, font=(C.FONT, 8), anchor="w",
                         justify="left", wraplength=150).pack(fill="x")

        def entry(r, key, ph=""):
            e = RoundEntry(grid, self.v[key], placeholder=ph, width_chars=26, font=(C.FONT, 10),
                           height=34, fill=DP.SEG_BG, radius=8)
            e.grid(row=r, column=1, sticky="we", pady=4)
            e.entry.bind("<Return>", lambda ev: self._save())
            return e
        r = 0
        label(r, "Program")
        if new:
            DP.Seg(grid, K.PROGRAMS, self.prog, self._set_prog).grid(row=r, column=1, sticky="w",
                                                                   pady=4)
        else:
            tk.Label(grid, text=dict(K.PROGRAMS)[self.prog], bg=PANEL, fg=FG,
                     font=(C.FONT, 10), anchor="w").grid(row=r, column=1, sticky="w")
        r += 1
        label(r, "Judul kursus", "Tampil di kartu")
        first = entry(r, "title", "mis. BASIC 3")
        r += 1
        label(r, "ID kursus", "Tetap, tidak bisa diganti" if new else "")
        if new:
            id_e = entry(r, "id", "otomatis dari judul")
            id_e.entry.bind("<Key>", lambda ev: setattr(self, "_id_auto", False), add="+")
            self.v["title"].trace_add("write", lambda *a: self._auto_id())
        else:
            tk.Label(grid, text=c["id"], bg=PANEL, fg=FG, font=("Consolas", 10),
                     anchor="w").grid(row=r, column=1, sticky="w")
        r += 1
        label(r, "Grup", "Label kecil di atas judul")
        entry(r, "group", "mis. BASIC (kosong = judul)")
        r += 1
        label(r, "Deskripsi", "Dilihat guru & admin")
        entry(r, "desc", "Bahasa Indonesia")
        r += 1
        label(r, "Deskripsi murid", "English, di kartu murid")
        entry(r, "desc_en", "English")
        r += 1
        label(r, "Warna kursus")
        opts = list(K.COLORS)
        if all(col != self.color for _k, col, _n in opts):
            opts.append(("cur", self.color, "Sekarang"))
        DP.Swatches(grid, [(col, col, name) for _k, col, name in opts], self.color,
                    lambda v: setattr(self, "color", v)).grid(row=r, column=1, sticky="w",
                                                              pady=6)
        r += 1
        label(r, "Punya video", "Mati = tanpa menu video (mis. AI)")
        vrow = tk.Frame(grid, bg=PANEL)
        vrow.grid(row=r, column=1, sticky="we", pady=4)
        Switch(vrow, self.video, command=lambda v: setattr(self, "video", v),
               bg=PANEL).pack(side="left")
        if not new and K.has_video(c):
            link = tk.Label(vrow, text="Buka folder video", bg=PANEL, fg=C.ACCENT,
                            cursor="hand2", font=(C.FONT, 10))
            link.pack(side="left", padx=(14, 0))
            link.bind("<Button-1>", lambda e: self._open_folder())
        r += 1
        self.open_all = False
        if new:
            label(r, "Buka untuk semua murid", "Langsung terbuka untuk murid program ini")
            self.all_row = tk.Frame(grid, bg=PANEL)
            self.all_row.grid(row=r, column=1, sticky="we", pady=4)
            self.all_sw = Switch(self.all_row, False,
                                 command=lambda v: setattr(self, "open_all", v), bg=PANEL)
            self.all_sw.pack(side="left")
            self.all_lbl = tk.Label(self.all_row, text="", bg=PANEL, fg=MUTED,
                                    font=(C.FONT, 9))
            self.all_lbl.pack(side="left", padx=(12, 0))
            self._all_text()
        self.msg = tk.Label(b, text=("Video: letakkan di assets\\lessons\\<ID>." if new else ""),
                            bg=PANEL, fg=MUTED, font=(C.FONT, 9), anchor="w", justify="left",
                            wraplength=470)
        self.msg.pack(fill="x", pady=(10, 0))
        btns = tk.Frame(b, bg=PANEL)
        btns.pack(side="bottom", fill="x")
        DP._btn(btns, "Buat kursus" if new else "Simpan", self._save, "primary").pack(
            side="right")
        DP._btn(btns, "Batal", self.destroy).pack(side="right", padx=(0, 8))
        self.show(first.entry)

    def _set_prog(self, prog):
        self.prog = prog
        self._all_text()

    def _all_text(self):
        from elearning.students import list_students
        if self.prog == "trial":
            self.all_lbl.config(text="Trial: selalu terbuka")
            self.all_sw.pack_forget()
            return
        if not self.all_sw.winfo_ismapped():
            self.all_sw.pack(side="left", before=self.all_lbl)
        n = sum(1 for s in list_students() if s["program"] == self.prog)
        self.all_lbl.config(text=f"{n} murid {dict(K.PROGRAMS)[self.prog]}")

    def _auto_id(self):
        if self._id_auto:
            self.v["id"].set(K.slug(self.v["title"].get()))

    def _open_folder(self):
        path = K.lesson_dir(self.course)
        try:
            os.makedirs(path, exist_ok=True)
            os.startfile(path)
        except OSError as exc:
            self.msg.config(text=f"Folder tidak bisa dibuka: {exc}", fg=C.ERROR)

    def _save(self):
        spec = {k: v.get() for k, v in self.v.items()}
        spec.update(program=self.prog, color=self.color, video=self.video)
        try:
            if self.course is None:
                c = K.add_course(spec)
                if self.open_all and c["program"] != "trial":
                    self._open_for_all(c)
                text = f"Kursus {c['title']} dibuat."
                C.log(f"Dev: kursus baru {c['id']} ({c['program']})")
            else:
                c = K.update_course(self.course["id"], spec)
                text = f"{c['title']} disimpan."
                C.log(f"Dev: kursus {c['id']} diubah")
        except ValueError as exc:
            self.msg.config(text=str(exc), fg=C.ERROR)
            return
        except OSError as exc:
            C.log(f"Dev: kursus gagal disimpan: {exc!r}")
            self.msg.config(text="Gagal menyimpan (folder data?).", fg=C.ERROR)
            return
        page = self.page
        self.destroy()
        page.prog = c["program"]
        page.seg.set(c["program"])
        page.course_saved(text)

    def _open_for_all(self, c):
        from elearning import students as ST
        changes = {s["id"]: (s["courses"] + [c["id"]], s.get("hidden") or [])
                   for s in ST.list_students() if s["program"] == c["program"]}
        ST.bulk_access(changes)
        self.page._changed_ids.update(changes)


class CourseDelete(_Card):
    """Konfirmasi hapus kursus (fokus awal di Batal)."""

    def __init__(self, page, course):
        super().__init__(page, 440, 250)
        self.course = course
        n = sum(1 for s in page.students if course["id"] in s["courses"])
        builtin = any(x["id"] == course["id"] for x in K.BUILTIN)
        b = tk.Frame(self.body, bg=PANEL)
        b.pack(fill="both", expand=True, padx=22, pady=(18, 16))
        DP._draggable(self, b)
        tk.Label(b, text=f"Hapus kursus {course['title']}?", bg=PANEL, fg=FG,
                 font=(C.FONT, 13, "bold"), anchor="w").pack(fill="x")
        who = (f"{n} murid membukanya" if n else "belum ada murid yang membukanya") \
            if course["program"] != "trial" else "semua akun trial"
        more = (" Kursus bawaan bisa dipulihkan dari daftar." if builtin else
                f" Buat lagi kursus ber-ID {course['id']} untuk memulihkan.")
        tk.Label(b, text=(f"Panel kursus ini hilang dari halaman murid ({who}). Video, "
                          f"progres, badge, portfolio dan assignment murid TIDAK dihapus." + more),
                 bg=PANEL, fg=MUTED, font=(C.FONT, 10), anchor="w", justify="left",
                 wraplength=390).pack(fill="x", pady=(6, 0))
        self.msg = tk.Label(b, text="", bg=PANEL, fg=C.ERROR, font=(C.FONT, 9), anchor="w")
        self.msg.pack(fill="x", pady=(6, 0))
        btns = tk.Frame(b, bg=PANEL)
        btns.pack(side="bottom", fill="x")
        DP._btn(btns, "Hapus kursus", self._do, "danger").pack(side="right")
        cancel = DP._btn(btns, "Batal", self.destroy)
        cancel.pack(side="right", padx=(0, 8))
        self.show(cancel)                    # Enter tidak langsung menghapus

    def _do(self):
        try:
            K.delete_course(self.course["id"])
        except (ValueError, OSError) as exc:
            self.msg.config(text=str(exc) if isinstance(exc, ValueError) else
                            "Gagal menyimpan (folder data?).")
            return
        C.log(f"Dev: kursus {self.course['id']} dihapus")
        page, title = self.page, self.course["title"]
        self.destroy()
        page.course_saved(f"Kursus {title} dihapus.")
