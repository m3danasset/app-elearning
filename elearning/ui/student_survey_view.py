"""Popup survey murid setelah BASIC 2 selesai (layar murid = English). Gaya sama dengan
survey trial (signup_view.SurveyDialog): kartu modal, pilihan sekali klik, kolom isian bulat.
Data & aturan kapan muncul: elearning/student_survey.py."""

import tkinter as tk

from elearning import config as C
from elearning import student_survey as SS
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
        from elearning.ui.survey_form import QuestionForm
        self.form = QuestionForm(self.body, SS.questions(), width=self.W - 56)
        self.form.pack(fill="x")
        self.entries = self.form.entries          # pertanyaan dari admin (Panel Survey)
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

    def _next(self, n):
        if n + 1 < len(self.entries):
            self.entries[n + 1].focus_set()
        else:
            self._submit()
        return "break"

    def _submit(self):
        answers = self.form.values()
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
