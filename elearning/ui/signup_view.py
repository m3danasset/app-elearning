"""Survey calon murid (setelah trial) + daftar pendaftar untuk admin.

SurveyDialog   : popup English saat akun trial keluar / menutup aplikasi. Kolom isian
                 (nama, telepon, umur, email, sekolah, minat, orang tua, alamat, ...).
                 Submit -> data\\trial_signups.json (signups.add); Skip -> lanjut keluar.
SignupBoard    : Panel Admin > Pendaftar. Satu canvas, digambar ulang utuh (seperti
                 daftar sertifikat). Detail / Tolak / Setujui per pendaftar.
ApproveDialog  : admin memilih kategori (dewasa / SUPERKIDS), ID, dan kursus yang dibuka ->
                 akun murid dibuat (students.add_student + set_course_access).
"""

import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import signups as SU
from elearning.ui import ui_icons as I
from elearning.ui.controls import RoundButton, RoundEntry, RoundPanel, dark_titlebar
from elearning.ui.widgets import add_hover

KIDS_MAX_AGE = 12      # umur <= ini: saran kategori SUPERKIDS saat disetujui


def _dialog_base(win, master, title):
    win.title(title)
    win.resizable(False, False)
    win.transient(master.winfo_toplevel())
    dark_titlebar(win)
    try:
        win.iconbitmap(C.ICON_PATH)
    except Exception:
        pass


def _center_modal(win, master):
    win.update_idletasks()
    top = master.winfo_toplevel()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    x = top.winfo_rootx() + (top.winfo_width() - w) // 2
    y = top.winfo_rooty() + (top.winfo_height() - h) // 2
    win.geometry(f"+{max(0, x)}+{max(0, y)}")
    try:
        win.wait_visibility()
        win.grab_set()            # modal: layar di belakang tidak bisa diklik
    except tk.TclError:
        pass


def _button(parent, text, command, primary=False, danger=False):
    if primary:
        b = RoundButton(parent, text=text, command=command, bg=C.ACCENT, fg="white",
                        activebackground=C.ACCENT_HOVER, activeforeground="white",
                        font=(C.FONT, 11, "bold"), padx=22, pady=7)
        add_hover(b, C.ACCENT, C.ACCENT_HOVER)
    else:
        b = RoundButton(parent, text=text, command=command, bg=C.CARD,
                        fg=C.ERROR if danger else C.MUTED, activebackground=C.BORDER,
                        activeforeground=C.TEXT, font=(C.FONT, 11), padx=18, pady=7)
        add_hover(b, C.CARD, C.BORDER)
    return b


# --- survey (layar trial, English) -------------------------------------------------------
class SurveyDialog(tk.Toplevel):
    """Popup survey setelah trial. on_done() dipanggil SEKALI saat ditutup (submit / skip)."""

    def __init__(self, master, on_done=None):
        super().__init__(master, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        _dialog_base(self, master, "Start learning with us")
        self.on_done = on_done
        self.submitted = False
        self.vars = {}
        self.body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        self.body.pack(fill="both", expand=True)
        tk.Label(self.body, text="Thanks for trying our class!", bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 15, "bold"), anchor="w").pack(fill="x")
        tk.Label(self.body, text="Leave your details and our team will contact you to "
                                 "start learning. Fields marked * are required.",
                 bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10), anchor="w", justify="left",
                 wraplength=540).pack(fill="x", pady=(4, 12))
        grid = tk.Frame(self.body, bg=C.CARD)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1, uniform="c")
        grid.columnconfigure(1, weight=1, uniform="c")
        self.entries = []
        r = c = 0
        for key, label, _id_label, required, wide in SU.FIELDS:
            if wide and c == 1:            # kolom lebar selalu mulai di baris baru
                r, c = r + 1, 0
            cell = tk.Frame(grid, bg=C.CARD)
            cell.grid(row=r, column=c, columnspan=2 if wide else 1, sticky="ew",
                      padx=(0 if c == 0 else 6, 0 if (wide or c == 1) else 6), pady=(0, 10))
            tk.Label(cell, text=label + (" *" if required else ""), bg=C.CARD,
                     fg=C.TEXT if required else C.MUTED, font=(C.FONT, 10),
                     anchor="w").pack(fill="x")
            var = tk.StringVar()
            self.vars[key] = var
            if key in SU.CHOICES:              # pilihan sekali klik (bukan kolom ketik)
                self._choice_row(cell, key, var)
            else:
                box = RoundEntry(cell, var, width_chars=48 if wide else 22, font=(C.FONT, 11),
                                 height=38, fill=C.BG, radius=9)
                box.pack(fill="x", pady=(4, 0))
                self.entries.append(box.entry)
            if wide:
                r, c = r + 1, 0
            else:
                r, c = (r + 1, 0) if c == 1 else (r, 1)
        # pertanyaan tambahan dari admin (Panel Admin > Survey > Survey trial)
        from elearning import survey_questions as SQ
        self.extra_q = SQ.load("trial")
        self.extra = None
        if self.extra_q:
            from elearning.ui.survey_form import QuestionForm
            self.extra = QuestionForm(self.body, self.extra_q, width=540)
            self.extra.pack(fill="x", pady=(4, 0))
            self.entries += self.extra.entries
        for n, e in enumerate(self.entries):      # Enter = kolom berikutnya; terakhir = kirim
            e.bind("<Return>", lambda ev, n=n: self._next(n))
        self.error = tk.Label(self.body, text="", bg=C.CARD, fg=C.ERROR, font=(C.FONT, 10),
                              anchor="w", wraplength=540, justify="left")
        self.error.pack(fill="x")
        btns = tk.Frame(self.body, bg=C.CARD)
        btns.pack(fill="x", pady=(8, 0))
        _button(btns, "Submit", self._submit, primary=True).pack(side="right")
        _button(btns, "Skip", self.destroy).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        _center_modal(self, master)
        self.attributes("-topmost", True)        # tetap di atas layar penuh
        self.entries[0].focus_set()

    def _choice_row(self, cell, key, var):
        """Tombol pilihan bergaya segmen (sama dengan pilihan kategori di dialog lain)."""
        row = tk.Frame(cell, bg=C.CARD)
        row.pack(fill="x", pady=(4, 0))
        btns = {}

        def paint():
            for value, b in btns.items():
                on = var.get() == value
                b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
                         activebackground=C.SEG_ON if on else C.CARD_HOVER,
                         activeforeground=C.TEXT)

        def pick(value):
            var.set("" if var.get() == value else value)   # klik lagi = batal pilih
            paint()
        for value, label, _admin in SU.CHOICES[key]:
            b = RoundButton(row, text=label, command=lambda v=value: pick(v), relief="flat",
                            bd=0, highlightthickness=0, cursor="hand2",
                            font=(C.FONT, 10, "bold"), padx=16, pady=7)
            b.pack(side="left", padx=(0, 8))
            btns[value] = b
        paint()

    def _next(self, n):
        if n + 1 < len(self.entries):
            self.entries[n + 1].focus_set()
        else:
            self._submit()
        return "break"

    def _submit(self):
        try:
            values = {k: v.get() for k, v in self.vars.items()}
            if self.extra is not None:
                from elearning import survey_questions as SQ
                values["extra"] = SQ.clean_answers(self.extra_q, self.extra.values())
            SU.add(values)
        except ValueError as exc:
            self.error.config(text=str(exc))
            return
        except OSError as exc:
            C.log(f"Survey trial gagal disimpan: {exc!r}")
            self.error.config(text="Sorry, your answers couldn't be saved. Please tell our staff.")
            return
        self.submitted = True
        self._thanks()

    def _thanks(self):
        for w in self.body.winfo_children():
            w.destroy()
        tk.Label(self.body, text="Thank you!", bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 15, "bold"), anchor="w").pack(fill="x")
        tk.Label(self.body, text="We've received your details. Our team will contact you "
                                 "soon to set up your classes.", bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 11), anchor="w", justify="left", wraplength=420).pack(
            fill="x", pady=(6, 16))
        done = _button(self.body, "Done", self.destroy, primary=True)
        done.pack(side="right")
        self.bind("<Return>", lambda e: self.destroy())
        self.update_idletasks()
        _center_again(self)
        self.focus_set()

    def destroy(self):
        cb, self.on_done = self.on_done, None
        try:
            self.grab_release()
        except tk.TclError:
            pass
        super().destroy()
        if cb is not None:
            cb()


def _center_again(win):
    top = win.master.winfo_toplevel()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    x = top.winfo_rootx() + (top.winfo_width() - w) // 2
    y = top.winfo_rooty() + (top.winfo_height() - h) // 2
    win.geometry(f"+{max(0, x)}+{max(0, y)}")


# --- Panel Admin: daftar pendaftar ---------------------------------------------------------
STATUS_TEXT = {SU.PENDING: ("●  Menunggu", "accent"), SU.APPROVED: ("●  Jadi murid", "on"),
               SU.REJECTED: ("●  Ditolak", "muted")}


class SignupBoard(tk.Canvas):
    """Daftar pendaftar dari trial di SATU canvas (gambar ulang utuh, tanpa kedip)."""

    ROW_H, GAP = 60, 6

    def __init__(self, master, by="", on_change=None):
        super().__init__(master, bg=C.BG, highlightthickness=0, bd=0, height=60)
        self.by, self.on_change = by, on_change
        self._imgs = []
        self._width = 0
        self.rows = []
        self.f = {"name": tkfont.Font(font=(C.FONT, 11, "bold")),
                  "sub": tkfont.Font(font=(C.FONT, 9)),
                  "cell": tkfont.Font(font=(C.FONT, 10)),
                  "btn": tkfont.Font(font=(C.FONT, 9)),
                  "head": tkfont.Font(font=(C.FONT, 9, "bold"))}
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, e):
        if e.width != self._width:
            self._width = e.width
            self.redraw()

    def show(self, rows):
        self.rows = rows
        self.redraw()

    def _fit(self, text, font, px):
        if font.measure(text) <= px:
            return text
        while text and font.measure(text + "…") > px:
            text = text[:-1]
        return text + "…"

    def redraw(self):
        self.delete("all")
        self._imgs = []
        W = self.winfo_width()
        if W < 300:
            return
        x2, x3 = int(W * 0.34), int(W * 0.56)
        for x, t in ((14, "Pendaftar"), (x2, "Sekolah / minat"), (x3, "Masuk")):
            self.create_text(x, 12, text=t, anchor="w", font=self.f["head"], fill=C.MUTED)
        y = 24
        if not self.rows:
            self.create_text(W / 2, y + 40, text="Belum ada pendaftar dari trial.",
                             fill=C.MUTED, font=self.f["cell"])
            self.configure(height=y + 80)
            return
        card = I.pill(int(W), self.ROW_H, C.CARD, C.BG, r=12, border=C.BORDER)
        colors = {"accent": C.ACCENT, "on": C.ON, "muted": C.MUTED}
        for n, r in enumerate(self.rows):
            if card is not None:
                self._imgs.append(card)
                self.create_image(0, y, image=card, anchor="nw")
            cy = y + self.ROW_H / 2
            st = r.get("status", SU.PENDING)
            sub = "  ·  ".join(t for t in (f"{r.get('age')} th" if r.get("age") else "",
                                            r.get("phone", "")) if t)
            self.create_text(14, cy - 9, text=self._fit(r.get("name", ""), self.f["name"],
                                                        x2 - 28),
                             anchor="w", font=self.f["name"], fill=C.TEXT)
            self.create_text(14, cy + 10, text=self._fit(sub, self.f["sub"], x2 - 28),
                             anchor="w", font=self.f["sub"], fill=C.MUTED)
            self.create_text(x2, cy - 9, text=self._fit(r.get("school", "") or "-",
                                                        self.f["cell"], x3 - x2 - 14),
                             anchor="w", font=self.f["cell"], fill=C.TEXT)
            self.create_text(x2, cy + 10, text=self._fit(r.get("interest", ""), self.f["sub"],
                                                         x3 - x2 - 14),
                             anchor="w", font=self.f["sub"], fill=C.MUTED)
            self.create_text(x3, cy, text=r.get("at", "")[:16], anchor="w",
                             font=self.f["cell"], fill=C.TEXT)
            # tombol dari kanan ke kiri
            if st == SU.PENDING:
                buttons = (("Setujui", "approve", True), ("Tolak", "reject", False),
                           ("Detail", "detail", False))
            elif st == SU.REJECTED:
                buttons = (("Hapus", "delete", False), ("Buka lagi", "reopen", False),
                           ("Detail", "detail", False))
            else:
                buttons = (("Detail", "detail", False),)
            bx = W - 14
            for label, act, primary in buttons:
                bw = self.f["btn"].measure(label) + 22
                bx -= bw
                self._button(bx, cy, bw, label, n, act, primary)
                bx -= 6
            text, col = STATUS_TEXT.get(st, STATUS_TEXT[SU.PENDING])
            if st == SU.APPROVED and r.get("student"):
                text = f"{text} {r['student']}"
            self.create_text(bx - 8, cy, text=text, anchor="e", font=self.f["cell"],
                             fill=colors[col])
            y += self.ROW_H + self.GAP
        self.configure(height=y)

    def _button(self, x, cy, w, text, n, act, primary):
        tag = f"sb{n}{act}"
        fill, hov, fg = (C.ACCENT, C.ACCENT_HOVER, "white") if primary else \
            (C.BG, C.BORDER, C.TEXT)
        normal = I.pill(w, 24, fill, C.CARD, r=8)
        hover = I.pill(w, 24, hov, C.CARD, r=8)
        self._imgs += [normal, hover]
        img = self.create_image(x, cy - 12, image=normal, anchor="nw", tags=(tag,))
        self.create_text(x + w / 2, cy, text=text, font=self.f["btn"], fill=fg, tags=(tag,))
        self.tag_bind(tag, "<Enter>", lambda e: (self.itemconfigure(img, image=hover),
                                                 self.config(cursor="hand2")))
        self.tag_bind(tag, "<Leave>", lambda e: (self.itemconfigure(img, image=normal),
                                                 self.config(cursor="")))
        self.tag_bind(tag, "<Button-1>", lambda e: self._act(n, act))

    def _act(self, n, act):
        r = self.rows[n]
        try:
            if act == "detail":
                SignupDetail(self, r)
                return
            if act == "approve":
                ApproveDialog(self, r, by=self.by, on_done=self._changed)
                return
            if act == "reject":
                SU.reject(r["id"], by=self.by)
            elif act == "reopen":
                SU.reopen(r["id"])
            elif act == "delete":
                SU.delete(r["id"])
        except (ValueError, OSError) as exc:
            C.log(f"Pendaftar {r.get('id')} ({act}): {exc!r}")
        self._changed()

    def _changed(self):
        if self.on_change is not None:
            self.on_change()
        else:
            self.show(SU.list_all())


class SignupDetail(tk.Toplevel):
    """Isi survey satu pendaftar (hanya lihat)."""

    def __init__(self, master, rec):
        super().__init__(master, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        _dialog_base(self, master, "Pendaftar")
        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=rec.get("name", ""), bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 14, "bold"), anchor="w").pack(fill="x")
        st = STATUS_TEXT.get(rec.get("status"), STATUS_TEXT[SU.PENDING])[0].replace("●  ", "")
        extra = f" {rec['student']}" if rec.get("student") else ""
        tk.Label(body, text=f"{rec['id']}  ·  masuk {rec.get('at', '')[:16]}  ·  {st}{extra}",
                 bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10), anchor="w").pack(fill="x",
                                                                            pady=(2, 12))
        grid = tk.Frame(body, bg=C.CARD)
        grid.pack(fill="x")
        for r, (key, _en, label, _req, _wide) in enumerate(SU.FIELDS):
            tk.Label(grid, text=label, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                     anchor="nw").grid(row=r, column=0, sticky="nw", padx=(0, 16), pady=3)
            tk.Label(grid, text=SU.display(key, rec.get(key)) or "-", bg=C.CARD, fg=C.TEXT,
                     font=(C.FONT, 10),
                     anchor="w", justify="left", wraplength=360).grid(row=r, column=1,
                                                                      sticky="w", pady=3)
        extra = rec.get("extra") or {}
        if extra:                               # jawaban pertanyaan tambahan (English)
            from elearning import survey_questions as SQ
            texts = {q["id"]: q["text"] for q in SQ.load("trial")}
            r = len(SU.FIELDS)
            for qid, ans in extra.items():
                ans = ", ".join(ans) if isinstance(ans, list) else ans
                tk.Label(grid, text=texts.get(qid, qid), bg=C.CARD, fg=C.MUTED,
                         font=(C.FONT, 10), anchor="nw", justify="left",
                         wraplength=180).grid(row=r, column=0, sticky="nw", padx=(0, 16),
                                              pady=3)
                tk.Label(grid, text=ans or "-", bg=C.CARD, fg=C.TEXT, font=(C.FONT, 10),
                         anchor="w", justify="left", wraplength=360).grid(
                    row=r, column=1, sticky="w", pady=3)
                r += 1
        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(14, 0))
        _button(btns, "Tutup", self.destroy, primary=True).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.destroy())
        _center_modal(self, master)


class ApproveDialog(tk.Toplevel):
    """Setujui pendaftar: pilih kategori, ID, dan kursus yang dibuka -> akun murid dibuat."""

    def __init__(self, master, rec, by="", on_done=None):
        from elearning import students as ST
        super().__init__(master, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        _dialog_base(self, master, "Setujui pendaftar")
        self.ST, self.rec, self.by, self.on_done = ST, rec, by, on_done
        self._imgs = []
        self._auto_id = ""
        age = int(rec["age"]) if str(rec.get("age", "")).isdigit() else 99
        self.program = "kids" if age <= KIDS_MAX_AGE else "adult"
        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="Jadikan murid", bg=C.CARD, fg=C.TEXT, font=(C.FONT, 14, "bold"),
                 anchor="w").pack(fill="x")
        sub = "  ·  ".join(t for t in (f"{rec.get('age')} th" if rec.get("age") else "",
                                        rec.get("phone", ""), rec.get("interest", "")) if t)
        tk.Label(body, text=sub, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x", pady=(2, 12))
        tk.Frame(body, bg=C.CARD, width=460, height=1).pack()   # lebar tetap
        self.name_var = tk.StringVar(value=rec.get("name", ""))
        self._field(body, "Nama murid", self.name_var)
        tk.Label(body, text="Kategori", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x", pady=(12, 0))
        row = tk.Frame(body, bg=C.CARD)
        row.pack(fill="x", pady=(6, 0))
        self._prog_btns = {}
        for key, label in (("adult", "Murid dewasa"), ("kids", "SUPERKIDS")):
            b = RoundButton(row, text=label, font=(C.FONT, 10, "bold"), padx=16, pady=6,
                            command=lambda k=key: self._set_program(k))
            b.pack(side="left", padx=(0, 8))
            self._prog_btns[key] = b
        self.id_var = tk.StringVar()
        self._field(body, "ID murid (dipakai untuk login)", self.id_var, pady=12)
        tk.Label(body, text="Kursus yang dibuka", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x", pady=(12, 4))
        self.course_box = tk.Frame(body, bg=C.CARD)
        self.course_box.pack(fill="x")
        self.error = tk.Label(body, text="", bg=C.CARD, fg=C.ERROR, font=(C.FONT, 10),
                              anchor="w", wraplength=460, justify="left")
        self.error.pack(fill="x", pady=(8, 0))
        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(8, 0))
        _button(btns, "Buat akun murid", self._submit, primary=True).pack(side="right")
        _button(btns, "Batal", self.destroy).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda e: self.destroy())
        self._set_program(self.program)
        _center_modal(self, master)

    @staticmethod
    def _field(parent, label, var, pady=0):
        wrap = tk.Frame(parent, bg=C.CARD)
        wrap.pack(fill="x", pady=(pady, 0))
        tk.Label(wrap, text=label, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x")
        box = RoundEntry(wrap, var, width_chars=30, font=(C.FONT, 12), height=40, fill=C.BG,
                         radius=9)
        box.pack(fill="x", pady=(6, 0))
        return box.entry

    def _set_program(self, key):
        from elearning.courses import courses_for
        from elearning.ui.widgets import Switch
        self.program = key
        for k, b in self._prog_btns.items():
            on = k == key
            b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
                     activebackground=C.SEG_ON if on else C.CARD_HOVER, activeforeground=C.TEXT)
        if self.id_var.get().strip() in ("", self._auto_id):   # ID saran ikut berganti
            try:
                self._auto_id = self.ST.next_student_id(key)
                self.id_var.set(self._auto_id)
            except Exception:
                pass
        for w in self.course_box.winfo_children():
            w.destroy()
        self._imgs = []
        self.open = {}
        for n, course in enumerate(courses_for(key)):
            panel = RoundPanel(self.course_box, padx=4, pady=1)
            panel.pack(fill="x", pady=3)
            line = panel.inner
            sw = Switch(line, value=n == 0, bg=C.CARD,
                        command=lambda v, cid=course["id"]: self.open.__setitem__(cid, v))
            sw.pack(side="right", padx=(0, 10), pady=4)
            self.open[course["id"]] = n == 0        # bawaan: kursus pertama dibuka
            dot = I.dot(course["color"], C.CARD, 10)
            if dot is not None:
                self._imgs.append(dot)
                tk.Label(line, image=dot, bg=C.CARD, bd=0).pack(side="left", padx=(12, 8))
            tk.Label(line, text=course["title"], bg=C.CARD, fg=C.TEXT,
                     font=(C.FONT, 11, "bold"), anchor="w").pack(side="left")
        self.update_idletasks()

    def _submit(self):
        ST = self.ST
        sid = self.id_var.get().strip().upper()
        try:
            st = ST.add_student(self.name_var.get(), self.program, sid or None)
        except ValueError as exc:
            self.error.config(text=str(exc))
            return
        except OSError as exc:
            C.log(f"Pendaftar {self.rec['id']}: akun gagal dibuat: {exc!r}")
            self.error.config(text="Gagal menyimpan. Pastikan folder data bisa ditulis.")
            return
        sid = st["id"]
        for cid, on in self.open.items():
            if on:
                try:
                    ST.set_course_access(sid, cid, True)
                except Exception as exc:
                    C.log(f"Pendaftar -> {sid}: kursus {cid} tidak terbuka: {exc!r}")
        try:
            SU.approve(self.rec["id"], sid, by=self.by)
        except (ValueError, OSError) as exc:
            C.log(f"Pendaftar {self.rec['id']} tidak ditandai disetujui: {exc!r}")
        C.log(f"Pendaftar {self.rec['id']} disetujui -> murid {sid}")
        cb = self.on_done
        self.destroy()
        if cb is not None:
            cb()
