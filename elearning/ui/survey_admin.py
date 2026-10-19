"""Panel Admin > Survey: buat & ubah pertanyaan survey (English) + lihat hasilnya.

SurveyBoard    : tombol pilih survey (murid setelah BASIC 2 | trial), daftar pertanyaan di SATU
                 canvas (kartu bulat: nomor, pertanyaan, jenis, pilihan sebagai chip, ikon naik /
                 turun / ubah / hapus), lalu Hasil (batang per pilihan, jawaban isian terbaru).
QuestionDialog : pertanyaan (English), jenis (pilih satu / pilih banyak / isian teks), pilihan
                 (maks. 8, satu kolom per pilihan), wajib.
Data: elearning/survey_questions.py. Teks admin = Indonesia, isi pertanyaan = English (murid).
"""

import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import survey_questions as SQ
from elearning.ui import ui_icons as I
from elearning.ui.controls import RoundButton, RoundEntry
from elearning.ui.signup_view import _button, _center_modal, _dialog_base

KIND_LABEL = dict(SQ.KINDS)
INFO = {
    "student": "Muncul di Dashboard murid setelah semua video BASIC 2 ditonton (sekali). "
               "Tulis pertanyaan & pilihan dalam English: layar murid berbahasa English.",
    "trial": "Isian tetap (nama, telepon / WA, umur, email, sekolah, ...) selalu ada karena "
             "dipakai saat menyetujui pendaftar. Pertanyaan di bawah ditambahkan setelahnya "
             "(English).",
}
BAR = "#b39af0"


class SurveyBoard(tk.Frame):
    def __init__(self, master, by=""):
        super().__init__(master, bg=C.BG)
        self.by = by
        self.which = "student"
        self.f = {"q": tkfont.Font(family=C.FONT, size=11, weight="bold"),
                  "meta": tkfont.Font(family=C.FONT, size=9),
                  "chip": tkfont.Font(family=C.FONT, size=9),
                  "h": tkfont.Font(family=C.FONT, size=13, weight="bold"),
                  "t": tkfont.Font(family=C.FONT, size=10)}
        bar = tk.Frame(self, bg=C.BG)
        bar.pack(fill="x", pady=(0, 8))
        self._tabs = {}
        for key, label in SQ.SURVEYS:
            b = RoundButton(bar, text=label, command=lambda k=key: self._set(k),
                            font=(C.FONT, 10), padx=14, pady=6)
            b.pack(side="left", padx=(0, 6))
            self._tabs[key] = b
        RoundButton(bar, text="Pertanyaan baru", command=lambda: QuestionDialog(self, None),
                    bg=C.ACCENT, fg="white", activebackground=C.ACCENT_HOVER,
                    activeforeground="white", font=(C.FONT, 10, "bold"), padx=14, pady=6,
                    icon="plus").pack(side="right")
        self.reset_btn = RoundButton(bar, text="Kembalikan bawaan", command=self._reset,
                                     bg=C.CARD, font=(C.FONT, 10), padx=12, pady=6)
        self.reset_btn.pack(side="right", padx=(0, 8))
        self.info = tk.Label(self, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 10),
                             anchor="w", justify="left", wraplength=900)
        self.info.pack(fill="x", pady=(0, 10))
        self.msg = tk.Label(self, text="", bg=C.BG, fg=C.ACCENT, font=(C.FONT, 10), anchor="w")
        self.cv = tk.Canvas(self, bg=C.BG, highlightthickness=0, bd=0, height=200)
        self.cv.pack(fill="x")
        self.cv.bind("<Configure>", lambda e: self._width != e.width and self.draw())
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Motion>", self._motion)
        self._width = None
        self._hits = []
        self.reload()

    # --- data -----------------------------------------------------------------------------
    def _set(self, which):
        self.which = which
        self.reload()

    def reload(self):
        self.qs = SQ.load(self.which)
        for k, b in self._tabs.items():
            on = k == self.which
            b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
                     activebackground=C.SEG_ON if on else C.CARD_HOVER, activeforeground=C.TEXT)
        self.info.config(text=INFO[self.which])
        self.reset_btn.config(state="normal" if SQ.customized(self.which) else "disabled")
        self._results()
        self.draw()

    def _results(self):
        """(jumlah, [(pertanyaan, [(pilihan, n)], penjawab)], {qid: [jawaban isian]})."""
        if self.which == "student":
            from elearning import student_survey as SS
            recs = SS.records()
            get = SS.answers_of
        else:
            from elearning import signups as SU
            recs = [r for r in SU.list_all() if r.get("extra")]
            get = lambda r: r.get("extra") or {}          # noqa: E731
        texts = {}
        for q in self.qs:
            if q["kind"] == "text":
                texts[q["id"]] = [(r.get("name", ""), get(r).get(q["id"]))
                                  for r in recs if get(r).get(q["id"])][:5]
        self.res = (len(recs), SQ.tally(self.qs, recs, get), texts)

    def save(self, qs, note):
        try:
            SQ.save(self.which, qs)
        except (ValueError, OSError) as exc:
            self._note(str(exc) if isinstance(exc, ValueError) else "Gagal menyimpan (folder data?).")
            return False
        C.log(f"Survey {self.which}: pertanyaan diubah ({note})")
        self.reload()
        self._note(note)
        return True

    def _note(self, text):
        self.msg.config(text=text)
        if not self.msg.winfo_manager():
            self.msg.pack(fill="x", pady=(0, 8), before=self.cv)
        self.after(5000, lambda: self.msg.winfo_exists() and self.msg.pack_forget())

    def _reset(self):
        SQ.reset(self.which)
        self.reload()
        self._note("Pertanyaan kembali ke bawaan.")

    # --- gambar -------------------------------------------------------------------------
    def _chips(self, x, y, w, options, draw=True):
        """Chip pilihan (turun baris). Kembalikan tinggi yang dipakai."""
        cx, cy = x, y
        for o in options:
            cw = self.f["chip"].measure(o) + 22
            if cx > x and cx + cw > x + w:
                cx, cy = x, cy + 30
            if draw:
                img = I.pill(cw, 24, C.BG, C.CARD, r=12, border=C.BORDER)
                self._imgs.append(img)
                self.cv.create_image(cx, cy, image=img, anchor="nw")
                self.cv.create_text(cx + cw / 2, cy + 12, text=o, fill=C.TEXT,
                                    font=self.f["chip"])
            cx += cw + 6
        return (cy - y) + 24 if options else 0

    def draw(self):
        cv = self.cv
        cv.delete("all")
        self._imgs, self._hits = [], []
        W = max(500, cv.winfo_width())
        self._width = cv.winfo_width()
        y = 0
        n = len(self.qs)
        for i, q in enumerate(self.qs):
            tw = W - 64 - 150
            lines = self._wrap(q["text"], tw)
            ch = self._chips(64, 0, tw, q["options"], draw=False)
            h = 20 + 20 * len(lines) + 20 + (ch + 10 if ch else 0) + 12
            self._card(0, y, W, h)
            d = I.dot(C.SEG_ON, C.CARD, 30, 14.5)
            self._imgs.append(d)
            cv.create_image(32, y + 30, image=d)
            cv.create_text(32, y + 30, text=str(i + 1), fill=C.TEXT, font=self.f["q"])
            ty = y + 18
            for ln in lines:
                cv.create_text(64, ty, text=ln, anchor="nw", fill=C.TEXT, font=self.f["q"])
                ty += 20
            meta = KIND_LABEL[q["kind"]] + ("  ·  wajib" if q["required"] else "  ·  boleh kosong")
            cv.create_text(64, ty + 2, text=meta, anchor="nw", fill=C.MUTED, font=self.f["meta"])
            if ch:
                self._chips(64, ty + 24, tw, q["options"])
            bx = W - 18
            for icon, act, ok in (("trash", "del", True), ("pen", "edit", True),
                                  ("chev_down", "down", i < n - 1), ("chev_up", "up", i > 0)):
                bx -= 32
                ic = I.icon(icon, C.ERROR if icon == "trash" else
                            (C.TEXT if ok else "#4a4945"), C.CARD, 18)
                if ic is not None:
                    self._imgs.append(ic)
                    cv.create_image(bx + 15, y + 30, image=ic)
                if ok:
                    self._hits.append((bx, y + 15, bx + 30, y + 45, act, i))
            y += h + 10
        if not self.qs:
            self._card(0, y, W, 60)
            cv.create_text(20, y + 30, text="Belum ada pertanyaan. Klik \"Pertanyaan baru\".",
                           anchor="w", fill=C.MUTED, font=self.f["t"])
            y += 70
        y = self._draw_results(y + 16, W)
        cv.configure(height=y + 4)

    def _draw_results(self, y, W):
        cv = self.cv
        count, tally, texts = self.res
        cv.create_text(0, y, text="Hasil", anchor="nw", fill=C.TEXT, font=self.f["h"])
        cv.create_text(70, y + 4, text=f"{count} jawaban", anchor="nw", fill=C.MUTED,
                       font=self.f["t"])
        y += 34
        cols = 2 if W >= 900 else 1
        cw = (W - 10 * (cols - 1)) / cols
        items = [("tally", t) for t in tally] + [("text", q) for q in self.qs
                                                 if q["kind"] == "text"]
        if not items:
            cv.create_text(0, y, text="Belum ada pertanyaan.", anchor="nw", fill=C.MUTED,
                           font=self.f["t"])
            return y + 24
        row_h = 0
        for k, (kind, it) in enumerate(items):
            x = (k % cols) * (cw + 10)
            if k % cols == 0 and k:
                y += row_h + 10
                row_h = 0
            if kind == "tally":
                q, counts, answered = it
                h = 52 + len(counts) * 26
                self._card(x, y, cw, h)
                cv.create_text(x + 16, y + 14, text=self._fit(q["text"], cw - 120), anchor="nw",
                               fill=C.TEXT, font=self.f["q"])
                cv.create_text(x + cw - 16, y + 16, text=f"{answered} menjawab", anchor="ne",
                               fill=C.MUTED, font=self.f["meta"])
                top = max([c for _o, c in counts] + [1])
                for j, (opt, c) in enumerate(counts):
                    yy = y + 44 + j * 26
                    cv.create_text(x + 16, yy + 5, text=self._fit(opt, 130), anchor="w",
                                   fill=C.TEXT, font=self.f["meta"])
                    bx, bw = x + 156, cw - 156 - 70
                    self._bar(bx, yy, bw, c / top if c else 0)
                    cv.create_text(x + cw - 16, yy + 5, text=f"{c}", anchor="e", fill=C.MUTED,
                                   font=self.f["meta"])
            else:
                rows = texts.get(it["id"], [])
                h = 52 + max(1, len(rows)) * 22
                self._card(x, y, cw, h)
                cv.create_text(x + 16, y + 14, text=self._fit(it["text"], cw - 32), anchor="nw",
                               fill=C.TEXT, font=self.f["q"])
                for j, (name, ans) in enumerate(rows):
                    cv.create_text(x + 16, y + 44 + j * 22, anchor="nw", fill=C.MUTED,
                                   font=self.f["meta"],
                                   text=self._fit(f"{name}: {ans}", cw - 32))
                if not rows:
                    cv.create_text(x + 16, y + 44, text="Belum ada jawaban.", anchor="nw",
                                   fill=C.MUTED, font=self.f["meta"])
            row_h = max(row_h, h)
        return y + row_h

    def _card(self, x, y, w, h):
        img = I.pill(int(w), int(h), C.CARD, C.BG, r=12, border=C.BORDER)
        if img is not None:
            self._imgs.append(img)
            self.cv.create_image(x, y, image=img, anchor="nw")

    def _bar(self, x, y, w, frac):
        bg = I.pill(int(w), 10, C.SIDEBAR_ACTIVE, C.CARD, r=5)
        self._imgs.append(bg)
        self.cv.create_image(x, y, image=bg, anchor="nw")
        fw = int(w * frac)
        if fw >= 6:
            fg = I.pill(fw, 10, BAR, C.SIDEBAR_ACTIVE, r=5)
            self._imgs.append(fg)
            self.cv.create_image(x, y, image=fg, anchor="nw")

    def _wrap(self, text, px):
        f, lines, cur = self.f["q"], [], ""
        for w in text.split():
            t = f"{cur} {w}".strip()
            if cur and f.measure(t) > px:
                lines.append(cur)
                cur = w
            else:
                cur = t
        return lines + [cur] if cur else lines or [""]

    def _fit(self, text, px):
        f = self.f["meta"]
        text = str(text)
        if f.measure(text) <= px:
            return text
        while text and f.measure(text + "…") > px:
            text = text[:-1]
        return text + "…"

    # --- aksi ---------------------------------------------------------------------------
    def _motion(self, e):
        hit = any(x0 <= e.x < x1 and y0 <= e.y < y1 for x0, y0, x1, y1, _a, _i in self._hits)
        self.cv.configure(cursor="hand2" if hit else "")

    def _click(self, e):
        for x0, y0, x1, y1, act, i in self._hits:
            if x0 <= e.x < x1 and y0 <= e.y < y1:
                qs = list(self.qs)
                if act == "edit":
                    QuestionDialog(self, i)
                elif act == "del":
                    from elearning.ui.dialogs import ConfirmDialog

                    def do(i=i, qs=qs):
                        del qs[i]
                        self.save(qs, "Pertanyaan dihapus.")
                    ConfirmDialog(self, "Hapus pertanyaan?",
                                  f"\"{qs[i]['text']}\"\nJawaban lama tetap tersimpan.", do)
                else:
                    j = i - 1 if act == "up" else i + 1
                    qs[i], qs[j] = qs[j], qs[i]
                    self.save(qs, "Urutan pertanyaan diubah.")
                return


class QuestionDialog(tk.Toplevel):
    """Pertanyaan baru (index None) atau ubah pertanyaan ke-index."""

    def __init__(self, board, index):
        super().__init__(board, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        _dialog_base(self, board, "Pertanyaan survey")
        self.board, self.index = board, index
        q = board.qs[index] if index is not None else {"text": "", "kind": "single",
                                                       "options": ["", ""], "required": False}
        self.kind = q["kind"]
        self.required = q["required"]
        body = self.body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="Pertanyaan baru" if index is None else "Ubah pertanyaan",
                 bg=C.CARD, fg=C.TEXT, font=(C.FONT, 15, "bold"), anchor="w").pack(fill="x")
        tk.Label(body, text="Tulis dalam English (dibaca murid / calon murid).", bg=C.CARD,
                 fg=C.MUTED, font=(C.FONT, 10), anchor="w").pack(fill="x", pady=(2, 12))
        tk.Label(body, text="Pertanyaan", bg=C.CARD, fg=C.TEXT, font=(C.FONT, 10),
                 anchor="w").pack(fill="x")
        self.text = tk.StringVar(value=q["text"])
        box = RoundEntry(body, self.text, placeholder="e.g. Which software do you use at home?",
                         width_chars=52, font=(C.FONT, 11), height=38, fill=C.BG, radius=9)
        box.pack(fill="x", pady=(4, 12))
        tk.Label(body, text="Jenis jawaban", bg=C.CARD, fg=C.TEXT, font=(C.FONT, 10),
                 anchor="w").pack(fill="x")
        row = tk.Frame(body, bg=C.CARD)
        row.pack(fill="x", pady=(4, 12))
        self._kbtn = {}
        for k, label in SQ.KINDS:
            b = RoundButton(row, text=label, command=lambda k=k: self._set_kind(k),
                            font=(C.FONT, 10, "bold"), padx=16, pady=7, cursor="hand2")
            b.pack(side="left", padx=(0, 8))
            self._kbtn[k] = b
        self.opt_box = tk.Frame(body, bg=C.CARD)
        tk.Label(self.opt_box, text="Pilihan jawaban (min. 2, maks. 8; kosong = tidak dipakai)",
                 bg=C.CARD, fg=C.TEXT, font=(C.FONT, 10), anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.opts = []
        for n in range(SQ.OPTS_MAX):
            var = tk.StringVar(value=q["options"][n] if n < len(q["options"]) else "")
            RoundEntry(self.opt_box, var, placeholder=f"Option {n + 1}", width_chars=22,
                       font=(C.FONT, 10), height=34, fill=C.BG, radius=8).grid(
                row=1 + n // 2, column=n % 2, sticky="we", padx=(0, 8 if n % 2 == 0 else 0),
                pady=3)
            self.opts.append(var)
        self.opt_box.columnconfigure(0, weight=1)
        self.opt_box.columnconfigure(1, weight=1)
        self.req_row = tk.Frame(body, bg=C.CARD)
        self.req_row.pack(fill="x", pady=(12, 0))
        from elearning.ui.widgets import Switch
        Switch(self.req_row, self.required, command=lambda v: setattr(self, "required", v),
               bg=C.CARD).pack(side="left")
        tk.Label(self.req_row, text="Wajib dijawab", bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 10)).pack(side="left", padx=(10, 0))
        self.error = tk.Label(body, text="", bg=C.CARD, fg=C.ERROR, font=(C.FONT, 10),
                              anchor="w", wraplength=520, justify="left")
        self.error.pack(fill="x", pady=(8, 0))
        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(8, 0))
        _button(btns, "Simpan", self._save, primary=True).pack(side="right")
        _button(btns, "Batal", self.destroy).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda e: self.destroy())
        self._set_kind(self.kind)
        _center_modal(self, board)
        self.attributes("-topmost", True)
        box.entry.focus_set()

    def _set_kind(self, kind):
        self.kind = kind
        for k, b in self._kbtn.items():
            on = k == kind
            b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
                     activebackground=C.SEG_ON if on else C.CARD_HOVER, activeforeground=C.TEXT)
        if kind == "text":
            self.opt_box.pack_forget()
        elif not self.opt_box.winfo_manager():
            self.opt_box.pack(fill="x", before=self.req_row)

    def _save(self):
        qs = list(self.board.qs)
        old = qs[self.index] if self.index is not None else {}
        others = [q for n, q in enumerate(qs) if n != self.index]
        try:
            q = SQ.check({"id": old.get("id"), "text": self.text.get(), "kind": self.kind,
                          "options": [v.get() for v in self.opts],
                          "required": self.required}, others)
        except ValueError as exc:
            self.error.config(text=str(exc))
            return
        if self.index is None:
            qs.append(q)
        else:
            qs[self.index] = q
        if self.board.save(qs, "Pertanyaan disimpan."):
            self.destroy()

    def destroy(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        super().destroy()
