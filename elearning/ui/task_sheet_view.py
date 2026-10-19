"""Laporan kerja guru gaya SHEET (lihat elearning/task_sheet.py).

TaskSheet      : bar atas (bulan + panah, Bulan ini, pilih guru untuk admin, ringkasan) + SATU
                 canvas berisi tiga bagian berwarna: MINGGU INI (merah), BULAN INI (hijau),
                 SUDAH SELESAI (biru). Kolom NO | tugas | DONE | LAPORAN | CHECK.
                 Guru: klik sel tugas / laporan = isi langsung (Entry di atas sel; Enter = simpan,
                 Tab = sel berikutnya, Esc = batal); baris kosong = tugas baru; centang DONE =
                 pindah otomatis ke Sudah selesai. Admin: hanya melihat + centang CHECK.
TaskSheetPanel : TaskSheet di dalam ScrollFrame (layar guru, menu Laporan Kerja).
"""

import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import task_sheet as TS
from elearning.ui import ui_icons as I
from elearning.ui.controls import RoundButton, RoundSelect

COLORS = {"week": "#8f1d1d", "month": "#3a6b1f", "done": "#1d4f8a"}
TITLES = dict(TS.SECTIONS, done="SUDAH SELESAI")
MIN_ROWS = {"week": 8, "month": 6}
HEAD_H, ROW_H, GAP = 38, 32, 22
COL_NO, COL_DONE, COL_CHECK = 52, 74, 84
HOVER = "#2a2927"


class TaskSheet(tk.Frame):
    def __init__(self, master, teacher=None, admin=None, bg=C.BG):
        """teacher = {id, name} (guru, bisa mengisi) ATAU admin = {id, name} (pilih guru,
        hanya centang CHECK)."""
        super().__init__(master, bg=bg)
        self.bg = bg
        self.admin = admin
        self.teacher = teacher
        self.month = TS.this_month()
        self._edit = None                 # (bagian, baris, kolom, var, entry, window)
        self._hov = None
        self._imgs = []
        self.f = {"head": tkfont.Font(family=C.FONT, size=11, weight="bold"),
                  "cell": tkfont.Font(family=C.FONT, size=10),
                  "no": tkfont.Font(family=C.FONT, size=10)}
        bar = tk.Frame(self, bg=bg)
        bar.pack(fill="x", pady=(0, 12))
        nav = tk.Frame(bar, bg=bg)
        nav.pack(side="left")
        self._nav_btn(nav, "chev_left", lambda: self._go(-1)).pack(side="left")
        self.month_lbl = tk.Label(nav, text="", bg=bg, fg=C.TEXT, font=(C.FONT, 15, "bold"),
                                  width=15)
        self.month_lbl.pack(side="left")
        self._nav_btn(nav, "chev_right", lambda: self._go(1)).pack(side="left")
        RoundButton(nav, text="Bulan ini", command=self._this_month, bg=C.CARD,
                    font=(C.FONT, 10), padx=12, pady=5).pack(side="left", padx=(12, 0))
        if admin is not None:
            from elearning import teachers as T
            self._teachers = T.list_teachers()
            names = [t["name"] for t in self._teachers] or ["(belum ada guru)"]
            self.t_var = tk.StringVar(value=names[0])
            tk.Label(bar, text="Guru", bg=bg, fg=C.MUTED, font=(C.FONT, 10)).pack(
                side="left", padx=(24, 8))
            RoundSelect(bar, self.t_var, *names, command=lambda v: self.reload()).pack(
                side="left")
        self.note = tk.Label(bar, text="", bg=bg, fg=C.MUTED, font=(C.FONT, 10))
        self.note.pack(side="right")
        self.carry = tk.Label(self, text="", bg=bg, fg=C.ACCENT, font=(C.FONT, 10),
                              cursor="hand2", anchor="w")
        self.carry.bind("<Button-1>", lambda e: self._carry())
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, height=200)
        self.cv.pack(fill="x")
        self.cv.bind("<Configure>", self._on_width)
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Leave>", lambda e: self._set_hov(None))
        self.cv.bind("<Button-1>", self._click)
        self._width = None
        self.reload()

    # --- bar atas -----------------------------------------------------------------------
    def _nav_btn(self, parent, icon, cmd):
        c = tk.Canvas(parent, width=30, height=30, bg=self.bg, highlightthickness=0, bd=0,
                      cursor="hand2")
        img = I.icon(icon, C.TEXT, self.bg, 18)
        if img is not None:
            c._img = img
            c.create_image(15, 15, image=img)
        c.bind("<Button-1>", lambda e: cmd())
        return c

    def _go(self, step):
        self._commit()
        self.month = TS.shift_month(self.month, step)
        self.reload()

    def _this_month(self):
        self._commit()
        self.month = TS.this_month()
        self.reload()

    def teacher_id(self):
        if self.admin is None:
            return self.teacher["id"]
        t = next((t for t in self._teachers if t["name"] == self.t_var.get()), None)
        return t["id"] if t else ""

    @property
    def editable(self):
        return self.admin is None

    # --- data ---------------------------------------------------------------------------
    def reload(self, keep_edit=None):
        """Muat ulang dari file (dilewati kalau sedang mengetik di sel, kecuali dipaksa)."""
        if self._edit is not None and keep_edit is None:
            return
        self._cancel()
        tid = self.teacher_id()
        self.groups = TS.grouped(tid, self.month) if tid else {"week": [], "month": [],
                                                               "done": []}
        self.month_lbl.config(text=TS.month_label(self.month))
        g = self.groups
        unchecked = sum(1 for x in g["done"] if not x.get("check"))
        self.note.config(text=f"{len(g['week']) + len(g['month'])} belum selesai  ·  "
                              f"{len(g['done'])} selesai  ·  {unchecked} belum dicek admin")
        n_prev = TS.open_previous(tid, self.month) if (tid and self.editable) else 0
        if n_prev and not (g["week"] or g["month"] or g["done"]):
            self.carry.config(text=f"Bawa {n_prev} tugas belum selesai dari "
                                   f"{TS.month_label(TS.shift_month(self.month, -1))}  →")
            if not self.carry.winfo_manager():
                self.carry.pack(fill="x", pady=(0, 10), before=self.cv)
        else:
            self.carry.pack_forget()
        self._layout()
        self.draw()
        if keep_edit:
            self._begin(*keep_edit)

    def _carry(self):
        try:
            n = TS.carry_over(self.teacher_id(), self.month)
        except (ValueError, OSError) as exc:
            C.log(f"Laporan sheet: bawa tugas gagal: {exc!r}")
            return
        self.reload()
        self.note.config(text=f"{n} tugas dibawa dari bulan lalu.")

    # --- tata letak ---------------------------------------------------------------------
    def _cols(self):
        W = max(500, self.cv.winfo_width())
        flex = W - COL_NO - COL_DONE - COL_CHECK
        task = int(flex * 0.46)
        xs = {"no": 0, "task": COL_NO, "done": COL_NO + task}
        xs["report"] = xs["done"] + COL_DONE
        xs["check"] = W - COL_CHECK
        xs["end"] = W
        return xs

    def _layout(self):
        """Daftar baris: [(bagian, y, tugas atau None)] + y kepala tiap bagian."""
        self.rows, self.heads = [], []
        y = 0
        for key in ("week", "month", "done"):
            items = self.groups.get(key, [])
            self.heads.append((key, y))
            y += HEAD_H
            n = len(items)
            if key == "done":
                total = max(1, n)
            else:
                total = max(MIN_ROWS[key], n + 1 if self.editable else n, 1)
            for i in range(total):
                self.rows.append((key, i, y, items[i] if i < n else None))
                y += ROW_H
            y += GAP
        self.H = y - GAP + 2
        self.cv.configure(height=self.H)

    def _on_width(self, e):
        if e.width != self._width:
            self._width = e.width
            self._cancel()
            self.draw()

    # --- gambar -------------------------------------------------------------------------
    def draw(self):
        cv = self.cv
        cv.delete("all")
        self._imgs = []
        xs = self._cols()
        W = xs["end"]
        for key, y in self.heads:
            n_rows = sum(1 for r in self.rows if r[0] == key)
            body = HEAD_H + n_rows * ROW_H
            self._img(I.pill(W, body, C.CARD, self.bg, r=10, border=C.BORDER), 0, y)
            self._img(I.pill(W, HEAD_H, COLORS[key], self.bg, r=10), 0, y)
            cv.create_rectangle(1, y + HEAD_H - 10, W - 1, y + HEAD_H, fill=COLORS[key],
                                width=0)
            cy = y + HEAD_H / 2
            for col, text in (("no", "NO."), ("task", TITLES[key]), ("done", "DONE"),
                              ("report", "LAPORAN"), ("check", "CHECK")):
                x0, x1 = xs[col], self._end(xs, col)
                cv.create_text((x0 + x1) / 2, cy, text=text, fill="white", font=self.f["head"])
            for col in ("task", "done", "report", "check"):
                cv.create_line(xs[col], y + HEAD_H, xs[col], y + body - 4, fill=C.BORDER)
        for idx in range(len(self.rows)):
            self._draw_row(idx)

    @staticmethod
    def _end(xs, col):
        order = ("no", "task", "done", "report", "check", "end")
        return xs[order[order.index(col) + 1]]

    def _img(self, ph, x, y, tags=()):
        if ph is not None:
            self._imgs.append(ph)
            self.cv.create_image(x, y, image=ph, anchor="nw", tags=tags)

    def _draw_row(self, idx):
        cv = self.cv
        tag = f"r{idx}"
        cv.delete(tag)
        key, i, y, item = self.rows[idx]
        xs = self._cols()
        W = xs["end"]
        last = idx + 1 >= len(self.rows) or self.rows[idx + 1][0] != key
        if self._hov == idx and (item is not None or self.editable):
            cv.create_rectangle(1, y, W - 1, y + ROW_H - (4 if last else 0), fill=HOVER,
                                width=0, tags=tag)
            for col in ("task", "done", "report", "check"):
                cv.create_line(xs[col], y, xs[col], y + ROW_H - (4 if last else 0),
                               fill=C.BORDER, tags=tag)
        if not last:
            cv.create_line(1, y + ROW_H, W - 1, y + ROW_H, fill=C.BORDER, tags=tag)
        cy = y + ROW_H / 2
        if key == "done" and item is None:
            cv.create_text(xs["task"] + 10, cy, text="Belum ada tugas selesai. Centang DONE "
                           "di atas = pindah ke sini.", anchor="w", fill=C.MUTED,
                           font=self.f["cell"], tags=tag)
            return
        cv.create_text(COL_NO / 2, cy, text=str(i + 1), fill=C.MUTED, font=self.f["no"],
                       tags=tag)
        bg = HOVER if self._hov == idx else C.CARD
        if item is not None:
            muted = item.get("done")
            cv.create_text(xs["task"] + 10, cy, text=self._fit(item["text"],
                                                                xs["done"] - xs["task"] - 20),
                           anchor="w", fill=C.MUTED if muted else C.TEXT, font=self.f["cell"],
                           tags=tag)
            cv.create_text(xs["report"] + 10, cy,
                           text=self._fit(item.get("report", ""),
                                          xs["check"] - xs["report"] - 20),
                           anchor="w", fill=C.TEXT, font=self.f["cell"], tags=tag)
            self._box(xs["done"] + COL_DONE / 2, cy, bool(item.get("done")), bg, tag,
                      enabled=self.editable)
            self._box(xs["check"] + COL_CHECK / 2, cy, bool(item.get("check")), bg, tag,
                      enabled=self.admin is not None, color=C.ON)
        elif self.editable and i == len(self.groups.get(key, [])):
            cv.create_text(xs["task"] + 10, cy, text="+ Ketik tugas baru…", anchor="w",
                           fill=C.LOCKED, font=self.f["cell"], tags=tag)

    def _box(self, x, y, on, bg, tag, enabled=True, color=None):
        """Kotak centang antialias (pill + ikon centang), redup kalau tidak bisa diklik."""
        d = 18
        fill = (color or C.ACCENT) if on else bg
        border = None if on else ("#6d6a62" if enabled else "#4a4945")
        self._img(I.pill(d, d, fill, bg, r=4, border=border), x - d / 2, y - d / 2, tag)
        if on:
            ic = I.icon("check_bold", "#ffffff", fill, 14)
            if ic is not None:
                self._imgs.append(ic)
                self.cv.create_image(x, y, image=ic, tags=tag)

    def _fit(self, text, px):
        f = self.f["cell"]
        if f.measure(text) <= px:
            return text
        while text and f.measure(text + "…") > px:
            text = text[:-1]
        return text + "…"

    # --- interaksi ----------------------------------------------------------------------
    def _hit(self, x, y):
        """(indeks baris, kolom) atau None."""
        for idx, (key, _i, ry, _item) in enumerate(self.rows):
            if ry <= y < ry + ROW_H:
                xs = self._cols()
                for col in ("check", "report", "done", "task", "no"):
                    if x >= xs[col]:
                        return idx, col
        return None

    def _motion(self, e):
        hit = self._hit(e.x, e.y)
        self._set_hov(hit[0] if hit else None)
        cur = ""
        if hit:
            _k, _i, _y, item = self.rows[hit[0]]
            col = hit[1]
            if (col in ("task", "report") and self.editable) or \
                    (item is not None and ((col == "done" and self.editable)
                                           or (col == "check" and self.admin is not None))):
                cur = "hand2" if col in ("done", "check") else "xterm"
        self.cv.configure(cursor=cur)

    def _set_hov(self, idx):
        if idx == self._hov:
            return
        old, self._hov = self._hov, idx
        for i in (old, idx):
            if i is not None and i < len(self.rows):
                self._draw_row(i)

    def _click(self, e):
        hit = self._hit(e.x, e.y)
        self._commit()
        if hit is None:
            return
        idx, col = hit
        if idx >= len(self.rows):
            return
        key, i, _y, item = self.rows[idx]
        try:
            if col == "done" and item is not None and self.editable:
                TS.set_done(item["id"], not item.get("done"))   # otomatis pindah bagian
                self.reload()
            elif col == "check" and item is not None and self.admin is not None:
                TS.set_check(item["id"], not item.get("check"), self.admin.get("id", ""))
                self.reload()
            elif col in ("task", "report") and self.editable:
                if key == "done" and item is None:
                    return
                self._begin(key, i, col)
        except (ValueError, OSError) as exc:
            self.note.config(text=str(exc) if isinstance(exc, ValueError) else
                             "Gagal menyimpan (folder data?).")

    def _row_index(self, key, i):
        return next((n for n, r in enumerate(self.rows) if r[0] == key and r[1] == i), None)

    def _begin(self, key, i, col):
        idx = self._row_index(key, i)
        if idx is None:
            return
        _k, _i, y, item = self.rows[idx]
        if item is None and col == "report":
            col = "task"                       # baris baru: tugasnya dulu
        xs = self._cols()
        x0, x1 = xs[col], self._end(xs, col)
        var = tk.StringVar(value=(item or {}).get("text" if col == "task" else "report", ""))
        ent = tk.Entry(self.cv, textvariable=var, font=self.f["cell"], bg=C.BG, fg=C.TEXT,
                       insertbackground=C.TEXT, relief="flat", highlightthickness=1,
                       highlightbackground=C.ACCENT, highlightcolor=C.ACCENT)
        win = self.cv.create_window(x0 + 2, y + 2, anchor="nw", window=ent, width=x1 - x0 - 4,
                                    height=ROW_H - 4)
        self._edit = (key, i, col, var, ent, win)
        ent.bind("<Return>", lambda e: self._commit(move=(0, 1)) or "break")
        ent.bind("<Tab>", lambda e: self._commit(move=(1, 0)) or "break")
        ent.bind("<Shift-Tab>", lambda e: self._commit(move=(-1, 0)) or "break")
        ent.bind("<Escape>", lambda e: self._cancel() or "break")
        ent.bind("<FocusOut>", lambda e: self.after_idle(self._commit))
        ent.focus_set()
        ent.icursor("end")

    def _cancel(self):
        ed, self._edit = self._edit, None
        if ed is not None:
            try:
                self.cv.delete(ed[5])
                ed[4].destroy()
            except tk.TclError:
                pass

    def _commit(self, move=None):
        """Simpan sel yang sedang diisi. move=(dx, dy): pindah ke sel berikutnya."""
        ed = self._edit
        if ed is None:
            return
        key, i, col, var, _ent, _win = ed
        self._edit = None
        idx = self._row_index(key, i)
        item = self.rows[idx][3] if idx is not None else None
        text = var.get()
        try:
            if item is None:
                if text.strip():
                    TS.add(self.teacher_id(), self.month, key, text)
            elif col == "task":
                if " ".join(text.split()) != item["text"]:
                    TS.set_text(item["id"], text)          # kosong = tugas dihapus
            elif " ".join(text.split()) != item.get("report", ""):
                TS.set_report(item["id"], text)
        except (ValueError, OSError) as exc:
            self._edit = ed                            # salah: sel tetap terbuka
            self.note.config(text=str(exc) if isinstance(exc, ValueError) else
                             "Gagal menyimpan (folder data?).")
            return
        try:
            self.cv.delete(ed[5])
            ed[4].destroy()
        except tk.TclError:
            pass
        nxt = None
        if move is not None:
            cols = ("task", "report")
            c = cols.index(col) + move[0]
            r = i + move[1] + (1 if c > 1 else -1 if c < 0 else 0)
            c %= 2
            n_items = len(TS.grouped(self.teacher_id(), self.month).get(key, []))
            if 0 <= r <= n_items:
                nxt = (key, r, cols[c])
        self.reload(keep_edit=nxt or ())
        if not nxt:
            self._edit = None

    def destroy(self):
        self._commit()
        super().destroy()


class TaskSheetPanel(tk.Frame):
    """Menu "Laporan Kerja" guru: judul + TaskSheet yang bisa digulir."""

    def __init__(self, master, teacher):
        from elearning.ui.widgets import ScrollFrame
        super().__init__(master, bg=C.BG, padx=32, pady=24)
        tk.Label(self, text="Klik sel untuk mengisi (Enter = simpan, Tab = sel berikutnya). "
                            "Centang DONE = tugas pindah ke Sudah selesai. CHECK diisi admin.",
                 bg=C.BG, fg=C.MUTED, font=(C.FONT, 10), anchor="w").pack(fill="x",
                                                                         pady=(2, 14))
        sf = ScrollFrame(self, bg=C.BG)
        sf.pack(fill="both", expand=True)
        self.sheet = TaskSheet(sf.inner, teacher=teacher)
        self.sheet.pack(fill="x", padx=(0, 12))
