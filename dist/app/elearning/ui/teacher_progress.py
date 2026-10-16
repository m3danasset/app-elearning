"""Panel guru: progres belajar murid dan kuis singkat.

ProgressBoard : tab "Progres Belajar" di detail murid. Per kursus: video selesai, posisi
                terakhir ("Video 4 — 12:30 / 20:00"), lalu tiap video dengan catatan murid
                (dewasa), emote review (SUPERKIDS, satu per video) dan jawaban kuis.
QuizPanel     : menu "Kuis": daftar kuis + hasil tiap murid, tombol Buat / Ubah / Hapus.
QuizDialog    : membuat / mengubah kuis (kursus, video, pertanyaan, kunci, murid).

Tabel digambar di SATU canvas (seperti Panel Admin), jadi tidak ada tombol terpotong
atau blok hitam saat pindah tab atau jendela berubah ukuran.
"""

import tkinter as tk
from datetime import datetime

from elearning import config as C
from elearning import progress, quizzes
from elearning.courses import COURSES, courses_for, has_video
from elearning.students import list_students, lookup_student
from elearning.ui import ui_icons as I
from elearning.ui.admin_board import _Board
from elearning.ui.controls import (RoundButton, RoundCheck, RoundEntry, RoundSelect,
                                   dark_titlebar)
from elearning.ui.lesson_extras import EMOTE_STYLE, fmt_time
from elearning.ui.widgets import ScrollFrame, add_hover

MONTHS = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
COURSE = {c["id"]: c for c in COURSES}
VERDICT = {True: ("Benar", C.ON), False: ("Salah", C.ACCENT), None: ("Dijawab", "#7cc8ff")}


def _when(text):
    try:
        d = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return ""
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}, {d:%H:%M}"


def _lines(font, text, width):
    """Bungkus teks per kata supaya muat di lebar tertentu (untuk menghitung tinggi)."""
    out, cur = [], ""
    for word in str(text).split():
        trial = f"{cur} {word}".strip()
        if cur and font.measure(trial) > width:
            out.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        out.append(cur)
    return out or [""]


# --- progres belajar satu murid ----------------------------------------------------------
class ProgressBoard(_Board):
    ROW = 30

    REFRESH_MS = 20_000   # murid sedang belajar: progres di layar guru ikut diperbarui

    def __init__(self, master, student):
        super().__init__(master)
        self.student = student
        self._sig = (progress._docs.get(student["id"], {}).get("key"), quizzes._cache.get("key"))
        self._job = self.after(self.REFRESH_MS, self._auto)

    def _auto(self):
        """Gambar ulang hanya kalau file progres murid / kuis berubah."""
        try:
            sid = self.student["id"]
            progress.load(sid)
            quizzes.list_quizzes()
            sig = (progress._docs.get(sid, {}).get("key"), quizzes._cache.get("key"))
            if sig != self._sig:
                self._sig = sig
                self.redraw()
        except Exception as exc:
            C.log(f"Progres guru: {exc!r}")
        self._job = self.after(self.REFRESH_MS, self._auto)

    def destroy(self):
        try:
            self.after_cancel(self._job)
        except Exception:
            pass
        super().destroy()

    def _courses(self):
        sid = self.student["id"]
        recs = progress.load(sid)["courses"]
        allowed = set(self.student["courses"])
        return [c for c in courses_for(self.student["program"])
                if has_video(c) and (c["id"] in allowed or recs.get(c["id"]))]

    def _draw(self, w):
        sid = self.student["id"]
        doc = progress.load(sid)
        answers = doc.get("quiz", {})
        given = quizzes.for_student(sid)
        courses = self._courses()
        if not courses:
            self._text(4, 20, "Belum ada kursus video yang dibuka untuk murid ini.",
                       fill=C.MUTED)
            return 44
        y = 0
        for c in courses:
            y = self._course(c, doc["courses"].get(c["id"], {}), answers, given, w, y) + 14
        return y

    def _course(self, c, recs, answers, given, w, y0):
        titles = progress.lesson_titles(c)
        titles += sorted((t for t in recs if t not in titles),
                         key=lambda t: recs[t].get("first", ""))
        done = sum(1 for t in titles if recs.get(t, {}).get("done"))
        total = len(titles)
        last = max((t for t in titles if recs.get(t, {}).get("views")),
                   key=lambda t: recs[t].get("last", ""), default=None)
        # tinggi kartu dihitung dulu (catatan dibungkus beberapa baris)
        inner = w - 48
        rows = []
        for i, t in enumerate(titles):
            rec = recs.get(t, {})
            extra = []
            if rec.get("note"):
                for k, line in enumerate(_lines(self.f["sub"], "Catatan: " + rec["note"],
                                                inner - 40)):
                    extra.append(("note", line))
            for q in given:
                if q["course"] == c["id"] and q["lesson"] == t:
                    extra.append(("quiz", (q, answers.get(q["id"]))))
            for qid, a in answers.items():   # jawaban kuis yang sudah dihapus guru
                if (a.get("course") == c["id"] and a.get("lesson") == t
                        and not any(q["id"] == qid for q in given)):
                    extra.append(("quiz", ({"question": a.get("question", ""), "answer": ""}, a)))
            rows.append((i, t, rec, extra))
        h = 86 + sum(self.ROW + 20 * len(e) for *_x, e in rows) + (24 if not titles else 0)
        self._img(I.pill(w, int(h), C.CARD, C.BG, r=14), 0, y0)

        x, y = 22, y0 + 24
        self._img(I.dot(c["color"], C.CARD, 10), x, y, anchor="w")
        self._text(x + 18, y, c["title"], font="title")
        pct = round(done * 100 / total) if total else 0
        self._text(x + 18 + self.f["title"].measure(c["title"]) + 14, y + 1,
                   f"{done} / {total} video selesai  ·  {pct}%", font="sub", fill=C.MUTED)
        if last is not None:
            rec = recs[last]
            no = titles.index(last) + 1
            pos = rec.get("pos", 0) if rec.get("pos") else (rec.get("dur", 0) if rec.get("done") else 0)
            txt = f"Terakhir: Video {no} — {fmt_time(pos)} / {fmt_time(rec.get('dur', 0))}"
            self._text(w - 22, y - 7, txt, font="cellb", anchor="e")
            self._text(w - 22, y + 11, _when(rec.get("last")), font="small", fill=C.MUTED,
                       anchor="e")
        else:
            self._text(w - 22, y, "Belum menonton", font="sub", fill=C.MUTED, anchor="e")
        # bar keseluruhan
        y += 26
        bw = w - 44
        self._img(I.pill(bw, 6, C.TRACK_OFF, C.CARD, r=3), x, y)
        if done:
            self._img(I.pill(max(6, int(bw * done / max(1, total))), 6, c["color"],
                             C.TRACK_OFF, r=3), x, y)
        y += 22
        if not titles:
            self._text(x, y + 6, "Belum ada video di folder kursus ini.", fill=C.MUTED)
            return y0 + h
        for i, t, rec, extra in rows:
            cy = y + self.ROW / 2
            self._text(x, cy, f"{i + 1:02d}", font="sub", fill=C.MUTED)
            opened = bool(rec.get("views"))
            self._text(x + 30, cy, t, fill=C.TEXT if opened else C.MUTED,
                       width=inner * 0.42)
            bx, bwid = x + inner * 0.48, inner * 0.2
            self._img(I.pill(int(bwid), 6, C.TRACK_OFF, C.CARD, r=3), bx, cy - 3)
            dur = rec.get("dur", 0)
            far = rec.get("pct", 0)
            if far:
                col = C.ON if rec.get("done") else c["color"]
                self._img(I.pill(max(6, int(bwid * far / 100)), 6, col, C.TRACK_OFF, r=3),
                          bx, cy - 3)
            if opened:
                pos = rec.get("pos", 0) if rec.get("pos") else (dur if rec.get("done") else 0)
                self._text(bx + bwid + 14, cy, f"{fmt_time(pos)} / {fmt_time(dur)}",
                           font="sub", fill=C.TEXT)
            if rec.get("done"):
                status, col = "Selesai", C.ON
            elif opened:
                status, col = f"Ditonton {far}%", C.TEXT
            else:
                status, col = "Belum dibuka", C.LOCKED
            self._text(x + inner, cy, status, font="sub", fill=col, anchor="e")
            emote = progress.emote_of(rec)
            if emote:     # review murid SUPERKIDS: satu emote per video
                ex = x + inner - self.f["sub"].measure(status) - 14
                label = progress.EMOTE_LABEL.get(emote, emote)
                self._text(ex, cy, label, font="sub", fill="#d9d6cd", anchor="e")
                fg, disc = EMOTE_STYLE.get(emote, (C.TEXT, C.BORDER))
                self._img(I.icon("emo_" + emote, fg, C.CARD, 20, disc=disc),
                          ex - self.f["sub"].measure(label) - 6, cy, anchor="e")
            y += self.ROW
            for kind, data in extra:
                ly = y + 10
                if kind == "note":
                    self._text(x + 30, ly, data, font="sub", fill="#d9d6cd")
                else:
                    q, a = data
                    if a is None:
                        tail, col = "belum dijawab", C.MUTED
                    else:
                        verdict, col = VERDICT[a.get("correct")]
                        tail = f"“{a.get('answer', '')}”  ·  {verdict}"
                    head = f"Kuis: {q['question']}  →  "
                    hw = min(self.f["sub"].measure(head), inner * 0.6)
                    self._text(x + 30, ly, head, font="sub", fill=C.MUTED, width=inner * 0.6)
                    self._text(x + 30 + hw + 4, ly, tail, font="sub", fill=col,
                               width=inner - hw - 40)
                y += 20
        return y0 + h


# --- daftar kuis -----------------------------------------------------------------------------
class QuizBoard(_Board):
    def __init__(self, master, on_edit, on_delete):
        super().__init__(master)
        self.on_edit, self.on_delete = on_edit, on_delete

    def _draw(self, w):
        items = quizzes.list_quizzes()
        if not items:
            self._text(4, 20, "Belum ada kuis. Klik “Buat kuis” untuk membuat soal "
                       "isian yang muncul setelah murid selesai menonton video.", fill=C.MUTED)
            return 44
        names = {s["id"]: s["name"] for s in list_students()}
        y = 0
        for q in items:
            y = self._card(q, names, w, y) + 12
        return y

    def _card(self, q, names, w, y0):
        inner = w - 44
        qlines = _lines(self.f["name"], q["question"], inner)
        studs = q.get("students", [])
        h = 74 + 22 * len(qlines) + 26 * len(studs) + 10
        self._img(I.pill(w, int(h), C.CARD, C.BG, r=14), 0, y0)
        x, y = 22, y0 + 22
        course = COURSE.get(q["course"], {"title": q["course"], "color": C.MUTED})
        self._img(I.dot(course["color"], C.CARD, 8), x, y, anchor="w")
        head = f"{course['title']}  ·  Video: {q['lesson']}"
        self._text(x + 16, y, head, font="kind", fill=C.MUTED, width=inner - 190)
        bx = w - 22 - 150
        bx = self._button(bx + 10, y, "Ubah", lambda: self.on_edit(q)) + 8
        self._button(bx, y, "Hapus", lambda: self.on_delete(q), fg=C.ERROR)
        y += 24
        for line in qlines:
            self._text(x, y, line, font="name")
            y += 22
        key = q.get("answer") or ""
        answers = {sid: progress.answers(sid).get(q["id"]) for sid in studs}
        n = sum(1 for a in answers.values() if a)
        self._text(x, y + 2, (f"Kunci: {key}" if key else "Tanpa kunci: jawaban dinilai guru")
                   + f"   ·   {n} / {len(studs)} murid sudah menjawab", font="sub",
                   fill=C.MUTED, width=inner)
        y += 26
        for sid in studs:
            a = answers.get(sid)
            cy = y + 11
            self._text(x, cy, f"{names.get(sid, '(murid dihapus)')}  ({sid})",
                       width=inner * 0.4)
            if a is None:
                self._text(x + inner * 0.42, cy, "Belum menjawab", font="sub", fill=C.LOCKED)
            else:
                verdict, col = VERDICT[a.get("correct")]
                tail = f"{verdict}  ·  {_when(a.get('t'))}"
                ax = x + inner * 0.42
                room = x + inner - self.f["sub"].measure(tail) - 16 - ax
                self._text(ax, cy, f"“{a.get('answer', '')}”", width=max(30, room))
                self._text(x + inner, cy, tail, font="sub", fill=col, anchor="e")
            y += 26
        return y0 + h


class QuizPanel(tk.Frame):
    """Menu Kuis di layar guru."""

    def __init__(self, master, teacher):
        super().__init__(master, bg=C.BG, padx=32, pady=20)
        self.teacher = teacher
        bar = tk.Frame(self, bg=C.BG)
        bar.pack(fill="x", pady=(0, 14))
        b = RoundButton(bar, text="+  Buat kuis", command=self._new, bg=C.ACCENT, fg="white",
                        activebackground=C.ACCENT_HOVER, activeforeground="white",
                        font=(C.FONT, 10, "bold"), padx=16, pady=6)
        b.pack(side="left")
        tk.Label(bar, text="Muncul di aplikasi murid setelah video selesai ditonton "
                 "(tidak saat murid di Blender).", bg=C.BG, fg=C.MUTED, anchor="w",
                 font=(C.FONT, 10)).pack(side="left", fill="x", expand=True, padx=(14, 0))
        self.msg = tk.Label(self, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 10), anchor="w")
        self.msg.pack(side="bottom", fill="x", pady=(8, 0))
        self.scroll = ScrollFrame(self, bg=C.BG)
        self.scroll.pack(fill="both", expand=True)
        self.board = QuizBoard(self.scroll.inner, self._edit, self._delete)
        self.board.pack(fill="x")

    def refresh(self):
        self.board.redraw()

    def _new(self):
        QuizDialog(self, self.teacher, None, on_saved=self._saved)

    def _edit(self, q):
        QuizDialog(self, self.teacher, q, on_saved=self._saved)

    def _saved(self, text):
        self.msg.config(text=text, fg=C.MUTED)
        self.refresh()

    def _delete(self, q):
        from elearning.ui.dialogs import ConfirmDialog

        def confirm():
            try:
                quizzes.delete(q["id"])
            except Exception as exc:
                C.log(f"Gagal menghapus kuis: {exc!r}")
                return "Gagal menghapus. Pastikan folder data bisa ditulis."
            self._saved("Kuis dihapus. Jawaban yang sudah masuk tetap terlihat di progres murid.")
            return None
        ConfirmDialog(self, "Hapus kuis?", f"“{q['question']}”\n\nKuis tidak akan "
                      "muncul lagi untuk murid.", confirm)


# --- dialog buat / ubah kuis ------------------------------------------------------------------
class QuizDialog(tk.Toplevel):
    W = 560

    def __init__(self, master, teacher, quiz=None, on_saved=None):
        super().__init__(master, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        self.title("Ubah kuis" if quiz else "Buat kuis")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        dark_titlebar(self)
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self.teacher, self.quiz, self.on_saved = teacher, quiz, on_saved
        self.courses = [c for c in COURSES if c["program"] in ("adult", "kids") and has_video(c)]
        self._titles = {c["title"]: c for c in self.courses}

        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="Ubah kuis" if quiz else "Buat kuis", bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 14, "bold"), anchor="w").pack(fill="x")
        tk.Label(body, text="Muncul sebagai popup kecil setelah murid selesai menonton video "
                 "yang dipilih.", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10), anchor="w",
                 justify="left", wraplength=self.W).pack(fill="x", pady=(4, 12))

        grid = tk.Frame(body, bg=C.CARD)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)

        def label(r, text):
            tk.Label(grid, text=text, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                     anchor="w").grid(row=r, column=0, sticky="w", padx=(0, 14), pady=5)

        first = COURSE.get(quiz["course"]) if quiz else self.courses[0]
        label(0, "Kursus")
        self.course_var = tk.StringVar(value=first["title"])
        RoundSelect(grid, self.course_var, *self._titles, bg=C.BORDER,
                    command=lambda v: self._course_changed()).grid(row=0, column=1,
                                                                   sticky="w", pady=5)
        label(1, "Video")
        self.video_var = tk.StringVar(value="")
        self.video_sel = RoundSelect(grid, self.video_var, "", bg=C.BORDER)
        self.video_sel.grid(row=1, column=1, sticky="w", pady=5)
        label(2, "Pertanyaan")
        self.q_var = tk.StringVar(value=quiz["question"] if quiz else "")
        RoundEntry(grid, textvariable=self.q_var, width_chars=34, height=38, fill=C.BG,
                   font=(C.FONT, 10), placeholder="mis. Tombol untuk menambah objek?").grid(
            row=2, column=1, sticky="we", pady=5)
        label(3, "Kunci jawaban")
        self.a_var = tk.StringVar(value=quiz.get("answer", "") if quiz else "")
        RoundEntry(grid, textvariable=self.a_var, width_chars=34, height=38, fill=C.BG,
                   font=(C.FONT, 10), placeholder="boleh kosong  ·  pisahkan dengan ;").grid(
            row=3, column=1, sticky="we", pady=5)
        tk.Label(grid, text="Kosong = jawaban dinilai guru sendiri. Beberapa jawaban benar: "
                 "pisahkan dengan titik koma, mis. shift a; shift+a", bg=C.CARD, fg=C.LOCKED,
                 font=(C.FONT, 8), anchor="w", justify="left", wraplength=self.W - 110).grid(
            row=4, column=1, sticky="w")

        head = tk.Frame(body, bg=C.CARD)
        head.pack(fill="x", pady=(14, 4))
        tk.Label(head, text="Murid yang mendapat kuis", bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 10), anchor="w").pack(side="left")
        self.all_lbl = tk.Label(head, text="Pilih semua", bg=C.CARD, fg=C.ACCENT,
                                cursor="hand2", font=(C.FONT, 10))
        self.all_lbl.pack(side="right")
        self.all_lbl.bind("<Button-1>", lambda e: self._toggle_all())
        self.box = tk.Frame(body, bg=C.CARD)
        self.box.pack(fill="x")
        self.checks = {}

        self.err = tk.Label(body, text="", bg=C.CARD, fg=C.ERROR, font=(C.FONT, 10),
                            anchor="w", justify="left", wraplength=self.W)
        self.err.pack(fill="x", pady=(10, 0))
        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(8, 0))
        ok = RoundButton(btns, text="Simpan kuis", command=self._save, bg=C.ACCENT, fg="white",
                         activebackground=C.ACCENT_HOVER, activeforeground="white",
                         font=(C.FONT, 11, "bold"), padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, C.ACCENT, C.ACCENT_HOVER)
        cancel = RoundButton(btns, text="Batal", command=self.destroy, bg=C.BORDER, fg=C.TEXT,
                             activebackground=C.CARD_HOVER, font=(C.FONT, 11), padx=18, pady=7)
        cancel.pack(side="right", padx=(0, 8))
        add_hover(cancel, C.BORDER, C.CARD_HOVER)
        self.bind("<Escape>", lambda e: self.destroy())

        self._course_changed(initial=True)
        self._center(master)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def _center(self, master):
        self.update_idletasks()
        parent = master.winfo_toplevel()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - h) // 2)
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _course(self):
        return self._titles[self.course_var.get()]

    def _course_changed(self, initial=False):
        course = self._course()
        titles = progress.lesson_titles(course)
        menu = self.video_sel.menu
        menu.delete(0, "end")
        for t in titles:
            menu.add_command(label=t, command=lambda v=t: self.video_sel._choose(v))
        want = self.quiz["lesson"] if (initial and self.quiz) else None
        if want and want not in titles:
            titles.insert(0, want)
            menu.insert_command(0, label=want, command=lambda v=want: self.video_sel._choose(v))
        self.video_var.set(want or (titles[0] if titles else "(belum ada video)"))
        # murid: hanya program kursus ini
        chosen = set(self.quiz["students"]) if (initial and self.quiz) else {
            k for k, cb in self.checks.items() if cb.value}
        for w in self.box.winfo_children():
            w.destroy()
        self.checks = {}
        studs = [s for s in list_students() if s["program"] == course["program"]]
        if not studs:
            tk.Label(self.box, text="Belum ada murid di program ini.", bg=C.CARD, fg=C.MUTED,
                     font=(C.FONT, 10)).pack(anchor="w")
        for i, s in enumerate(studs):
            locked = course["id"] not in s["courses"]
            cb = RoundCheck(self.box, f"{s['name']} ({s['id']})", s["id"] in chosen,
                            command=self._paint_all, font=(C.FONT, 9),
                            sub="terkunci" if locked else None)
            cb.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 14), pady=1)
            self.checks[s["id"]] = cb
        self._paint_all()
        if not initial:
            self.update_idletasks()

    def _paint_all(self):
        every = self.checks and all(cb.value for cb in self.checks.values())
        self.all_lbl.config(text="Kosongkan" if every else "Pilih semua")

    def _toggle_all(self):
        every = self.checks and all(cb.value for cb in self.checks.values())
        for cb in self.checks.values():
            cb.set(not every)
        self._paint_all()

    def _save(self):
        course = self._course()
        lesson = self.video_var.get()
        if lesson.startswith("(belum"):
            self.err.config(text="Kursus ini belum punya video. Taruh video di folder kursus dulu.")
            return
        students = [k for k, cb in self.checks.items() if cb.value]
        try:
            if self.quiz:
                quizzes.update(self.quiz["id"], course["id"], lesson, self.q_var.get(),
                               self.a_var.get(), students)
                msg = "Kuis diperbarui."
            else:
                quizzes.add(self.teacher["id"], course["id"], lesson, self.q_var.get(),
                            self.a_var.get(), students)
                msg = f"Kuis dibuat untuk {len(students)} murid."
        except ValueError as exc:
            self.err.config(text=str(exc))
            return
        except Exception as exc:
            C.log(f"Kuis gagal disimpan: {exc!r}")
            self.err.config(text="Gagal menyimpan. Pastikan folder data bisa ditulis.")
            return
        self.destroy()
        if self.on_saved is not None:
            self.on_saved(msg)
