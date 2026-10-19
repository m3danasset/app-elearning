"""Form pertanyaan survey (English) dari survey_questions: dipakai popup survey murid & survey
trial. Pilih satu / pilih banyak = tombol segmen sekali klik (klik lagi = batal), isian teks =
kolom bulat. QuestionForm.values() -> {id: str | [str]}."""

import tkinter as tk

from elearning import config as C
from elearning.ui.controls import RoundButton, RoundEntry


def paint(b, on):
    b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
             activebackground=C.SEG_ON if on else C.CARD_HOVER, activeforeground=C.TEXT)


class QuestionForm(tk.Frame):
    def __init__(self, master, questions, width=500, bg=C.CARD):
        super().__init__(master, bg=bg)
        self.questions = questions
        self.bg = bg
        self.width = width
        self._vals = {}
        self.entries = []
        import tkinter.font as tkfont
        self._font = tkfont.Font(family=C.FONT, size=10, weight="bold")
        for q in questions:
            tk.Label(self, text=q["text"] + (" *" if q["required"] else ""), bg=bg,
                     fg=C.TEXT, font=(C.FONT, 10), anchor="w", justify="left",
                     wraplength=width).pack(fill="x")
            if q["kind"] == "text":
                var = tk.StringVar()
                box = RoundEntry(self, var, width_chars=52, font=(C.FONT, 11), height=38,
                                 fill=C.BG, radius=9)
                box.pack(fill="x", pady=(4, 10))
                self.entries.append(box.entry)
                self._vals[q["id"]] = var
            else:
                self._vals[q["id"]] = self._choices(q)

    def _choices(self, q):
        """Tombol pilihan; turun baris kalau tidak muat. Kembalikan set / StringVar."""
        multi = q["kind"] == "multi"
        state = set() if multi else tk.StringVar()
        wrap = tk.Frame(self, bg=self.bg)
        wrap.pack(fill="x", pady=(4, 12))
        row, used = None, self.width + 1
        btns = {}

        def pick(opt):
            if multi:
                state.symmetric_difference_update({opt})
            else:
                state.set("" if state.get() == opt else opt)
            for o, b in btns.items():
                paint(b, (o in state) if multi else state.get() == o)
        for opt in q["options"]:
            b_w = self._font.measure(opt) + 2 * 16 + 8   # lebar tombol + jarak
            if used + b_w > self.width:
                row = tk.Frame(wrap, bg=self.bg)
                row.pack(fill="x", pady=(0, 6))
                used = 0
            b = RoundButton(row, text=opt, command=lambda o=opt: pick(o), cursor="hand2",
                            font=(C.FONT, 10, "bold"), padx=16, pady=7)
            b.pack(side="left", padx=(0, 8))
            paint(b, False)
            btns[opt] = b
            used += b_w
        return state

    def values(self):
        out = {}
        for q in self.questions:
            v = self._vals[q["id"]]
            if isinstance(v, set):                  # urutan pilihan tetap seperti pertanyaan
                out[q["id"]] = [o for o in q["options"] if o in v]
            else:
                out[q["id"]] = v.get()
        return out
