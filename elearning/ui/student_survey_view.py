"""Popup survey murid setelah BASIC 2 selesai (layar murid = English). Gaya sama dengan
survey trial (signup_view.SurveyDialog): kartu modal, pilihan sekali klik, kolom isian bulat.
Data & aturan kapan muncul: elearning/student_survey.py."""

import tkinter as tk

from elearning import config as C
from elearning import student_survey as SS
from elearning.ui.controls import RoundButton, RoundEntry
from elearning.ui.signup_view import _button, _center_again, _center_modal, _dialog_base


def maybe_show(app, student):
    """Dipanggil setelah Dashboard murid tampil: popup kalau survey sudah waktunya."""
    try:
        if SS.due(student):
            StudentSurveyDialog(app, student)
    except Exception as exc:
        C.log(f"Survey murid tidak ditampilkan: {exc!r}")


class StudentSurveyDialog(tk.Toplevel):
    W = 560

    def __init__(self, master, student):
        super().__init__(master, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        _dialog_base(self, master, "Quick survey")
        self.student = student
        self.done = False
        self.level = tk.StringVar()
        self.picked = set()
        self.vars = {k: tk.StringVar() for k in ("hardest", "favorite", "note")}
        self.body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        self.body.pack(fill="both", expand=True)
        name = (student.get("name") or "").split(" ")[0]
        tk.Label(self.body, text=f"Great job finishing BASIC 2, {name}!" if name else
                 "Great job finishing BASIC 2!", bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 15, "bold"), anchor="w").pack(fill="x")
        tk.Label(self.body, text="Tell us a little about your class so far. It takes one "
                                 "minute and helps your teacher plan what's next. "
                                 "Questions marked * are required.", bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 10), anchor="w", justify="left",
                 wraplength=self.W - 56).pack(fill="x", pady=(4, 14))
        self._label("How did BASIC 1 & 2 feel? *")
        self._single(self.level, [(k, e) for k, e, _i in SS.LEVELS])
        self._label("What do you want to make next? (pick any) *")
        self._multi([(k, e) for k, e, _i in SS.INTERESTS])
        self.entries = []
        for key, text in (("hardest", "What was the hardest part?"),
                          ("favorite", "What did you enjoy the most?"),
                          ("note", "Anything else you'd like to tell us?")):
            self._label(text)
            box = RoundEntry(self.body, self.vars[key], width_chars=52, font=(C.FONT, 11),
                             height=38, fill=C.BG, radius=9)
            box.pack(fill="x", pady=(4, 10))
            self.entries.append(box.entry)
        for n, e in enumerate(self.entries):
            e.bind("<Return>", lambda ev, n=n: self._next(n))
        self.error = tk.Label(self.body, text="", bg=C.CARD, fg=C.ERROR, font=(C.FONT, 10),
                              anchor="w", wraplength=self.W - 56, justify="left")
        self.error.pack(fill="x")
        btns = tk.Frame(self.body, bg=C.CARD)
        btns.pack(fill="x", pady=(8, 0))
        _button(btns, "Submit", self._submit, primary=True).pack(side="right")
        _button(btns, "Maybe later", self._skip).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda e: self._skip())
        self.protocol("WM_DELETE_WINDOW", self._skip)
        _center_modal(self, master)
        self.attributes("-topmost", True)
        self.focus_set()

    def _label(self, text):
        tk.Label(self.body, text=text, bg=C.CARD, fg=C.TEXT, font=(C.FONT, 10),
                 anchor="w").pack(fill="x")

    @staticmethod
    def _paint(b, on):
        b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
                 activebackground=C.SEG_ON if on else C.CARD_HOVER, activeforeground=C.TEXT)

    def _single(self, var, options):
        row = tk.Frame(self.body, bg=C.CARD)
        row.pack(fill="x", pady=(4, 12))
        btns = {}

        def pick(v):
            var.set("" if var.get() == v else v)
            for k, b in btns.items():
                self._paint(b, var.get() == k)
        for key, text in options:
            b = RoundButton(row, text=text, command=lambda v=key: pick(v), cursor="hand2",
                            font=(C.FONT, 10, "bold"), padx=16, pady=7)
            b.pack(side="left", padx=(0, 8))
            btns[key] = b
            self._paint(b, False)

    def _multi(self, options):
        row = tk.Frame(self.body, bg=C.CARD)
        row.pack(fill="x", pady=(4, 12))

        def toggle(k, b):
            self.picked ^= {k}
            self._paint(b, k in self.picked)
        for key, text in options:
            b = RoundButton(row, text=text, cursor="hand2", font=(C.FONT, 10, "bold"),
                            padx=16, pady=7)
            b.config(command=lambda k=key, b=b: toggle(k, b))
            b.pack(side="left", padx=(0, 8))
            self._paint(b, False)

    def _next(self, n):
        if n + 1 < len(self.entries):
            self.entries[n + 1].focus_set()
        else:
            self._submit()
        return "break"

    def _submit(self):
        answers = {k: v.get() for k, v in self.vars.items()}
        answers.update(level=self.level.get(), interests=sorted(self.picked))
        try:
            SS.add(self.student, answers)
        except ValueError as exc:
            self.error.config(text=str(exc))
            return
        except OSError as exc:
            C.log(f"Survey murid gagal disimpan: {exc!r}")
            self.error.config(text="Sorry, your answers couldn't be saved. Please tell your "
                                   "teacher.")
            return
        self.done = True
        for w in self.body.winfo_children():
            w.destroy()
        tk.Label(self.body, text="Thank you!", bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 15, "bold"), anchor="w").pack(fill="x")
        tk.Label(self.body, text="Your answers were sent to your teacher. Keep creating!",
                 bg=C.CARD, fg=C.MUTED, font=(C.FONT, 11), anchor="w", justify="left",
                 wraplength=420).pack(fill="x", pady=(6, 16))
        _button(self.body, "Done", self.destroy, primary=True).pack(side="right")
        self.bind("<Return>", lambda e: self.destroy())
        self.update_idletasks()
        _center_again(self)

    def _skip(self):
        if not self.done:
            SS.skip(self.student)          # tanya lagi saat app dibuka berikutnya
        self.destroy()

    def destroy(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        super().destroy()
