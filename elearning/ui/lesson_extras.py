"""Isi baris di bawah video, di antara tombol Sebelumnya / Selanjutnya, plus popup kuis.

NoteBox   : catatan singkat murid dewasa (maks. 30 kata, tersimpan otomatis per video).
EmoteBar  : review SUPERKIDS: satu emote per video (satu canvas); pilihan lain abu-abu.
            Semua emote TERSEMBUNYI; muncul halus saat kursor mendekat (NEAR px).
QuizPopup : kuis isian dari guru, muncul setelah video selesai (hanya saat aplikasi di
            depan, bukan saat murid sedang di Blender).

Semua digambar dengan widget yang sudah dipakai di aplikasi (RoundEntry, RoundButton,
canvas tunggal) supaya tidak ada potongan / blok hitam saat jendela berubah ukuran.
"""

import time
import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import progress, quizzes
from elearning.ui import ui_icons as I
from elearning.ui.controls import RoundButton, RoundEntry, dark_titlebar

EMOTE_STYLE = {   # kode -> (warna gambar, warna lingkaran)
    "seru": ("#3b2a05", "#f5c542"),
    "paham": ("#ffffff", "#4a90e2"),
    "bingung": ("#ffffff", "#ea7600"),
    "keren": ("#3b2a05", "#f5c542"),
    "capek": ("#1f2937", "#9aa5b1"),
    "bosan": ("#1f2937", "#9aa5b1"),
}
USED_FG, USED_DISC = "#2c2b28", "#4a4945"


def fmt_time(sec):
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# --- catatan singkat (murid dewasa) --------------------------------------------------------
class NoteBox(tk.Frame):
    SAVE_MS = 900

    def __init__(self, master):
        super().__init__(master, bg=C.BG)
        self.key = None             # (murid, kursus, judul) video yang sedang dibuka
        self._job = None
        self._loading = False
        self.var = tk.StringVar()
        self.entry = RoundEntry(self, textvariable=self.var, width_chars=10, height=38,
                                fill=C.CARD, font=(C.FONT, 10), right_pad=130,
                                placeholder="Short note for this video (your teacher can read it)")
        self.entry.pack(fill="x", expand=True)
        self.var.trace_add("write", lambda *a: self._changed())
        self.entry.entry.bind("<FocusOut>", lambda e: self.save_now(), add="+")
        self.entry.entry.bind("<Return>", lambda e: (self.save_now(), self.focus_set()))
        self._paint(saved=True)

    def set_lesson(self, key):
        """Pindah video: simpan catatan lama, tampilkan catatan video ini."""
        self.save_now()
        self.key = key
        text = progress.record(*key).get("note", "") if key else ""
        self._loading = True
        self.var.set(text)
        self._loading = False
        self._paint(saved=True)

    def _changed(self):
        if self._loading:
            return
        words = self.var.get().split()
        if len(words) > progress.NOTE_WORDS:    # batas 30 kata: kata berikutnya ditolak
            self._loading = True
            self.var.set(" ".join(words[:progress.NOTE_WORDS]))
            self._loading = False
            self.entry.entry.icursor("end")
            self.bell()
        self._paint(saved=False)
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(self.SAVE_MS, self.save_now)

    def save_now(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self.key is None:
            return
        try:
            progress.set_note(*self.key, self.var.get())
            self._paint(saved=True)
        except Exception as exc:
            C.log(f"Catatan tidak tersimpan: {exc!r}")

    def _paint(self, saved):
        n = progress.count_words(self.var.get())
        state = "Saved  ·  " if saved and n else ""
        self.entry.set_right_text(f"{state}{n}/{progress.NOTE_WORDS} words",
                                  C.ERROR if n >= progress.NOTE_WORDS else C.MUTED)

    def destroy(self):
        try:
            self.save_now()
        except Exception:
            pass
        super().destroy()


# --- emote (SUPERKIDS) ----------------------------------------------------------------------
def _mix(color, t):
    """Warna color dicampur ke latar C.BG sebanyak t (0 = latar, 1 = warna asli)."""
    a, b = I._rgb(C.BG), I._rgb(color)
    return "#%02x%02x%02x" % tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


class EmoteBar(tk.Canvas):
    """Review satu emote per video. Yang dipilih berwarna, sisanya abu-abu.
    Klik emote lain = ganti pilihan (tetap satu).

    Semua emote TERSEMBUNYI sampai kursor mendekat (dalam NEAR px dari baris emote), lalu
    muncul memudar (FADE_MS, maks. 30 fps, berbasis waktu) dan hilang lagi saat kursor menjauh.
    Posisi kursor dibaca langsung (winfo_pointerxy) karena video mpv menelan event mouse.
    Mode ringan: langsung muncul / hilang tanpa animasi."""
    SIZE = 32
    GAP = 34
    NEAR = 70          # px: jarak kursor ke baris emote supaya emote muncul
    FADE_MS = 160
    STEPS = 8          # tingkat pudar (gambar ikon di-cache per tingkat)
    IDLE_MS = 90       # periksa posisi kursor saat tidak beranimasi

    def __init__(self, master, get_pos=None):
        super().__init__(master, bg=C.BG, highlightthickness=0, bd=0, height=56)
        self.key = None
        self.chosen = None
        self._hover = None
        self._msg = ""
        self._imgs = []
        self._font = tkfont.Font(family=C.FONT, size=9)
        self._vis = 0.0            # 0 = tersembunyi, 1 = tampil penuh
        self._from = self._to = 0.0
        self._t0 = 0.0
        self._job = None
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._click)
        self.bind("<Destroy>", lambda e: self._stop_job(), add="+")
        self._job = self.after(self.IDLE_MS, self._watch)

    # --- muncul saat kursor mendekat ---------------------------------------------------------
    def _near(self):
        try:
            if not self.winfo_viewable():
                return False
            px, py = self.winfo_pointerxy()
            x0, y0 = self.winfo_rootx(), self.winfo_rooty()
            x1, y1 = x0 + self.winfo_width(), y0 + self.winfo_height()
        except tk.TclError:
            return False
        dx = max(x0 - px, 0, px - x1)
        dy = max(y0 - py, 0, py - y1)
        return dx * dx + dy * dy <= self.NEAR * self.NEAR

    def _watch(self):
        self._job = None
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        want = 1.0 if self._near() else 0.0
        now = time.perf_counter()
        if want != self._to:                       # arah berubah: mulai dari posisi sekarang
            self._from, self._to, self._t0 = self._vis, want, now
        if self._vis != self._to:
            if C.lite():
                self._vis = self._to
            else:
                t = min(1.0, (now - self._t0) * 1000 / self.FADE_MS)
                self._vis = self._from + (self._to - self._from) * (1 - (1 - t) ** 2)
                if t >= 1.0:
                    self._vis = self._to
            self._draw()
        busy = self._vis != self._to
        self._job = self.after(C.UI_FRAME_MS if busy else self.IDLE_MS, self._watch)

    def _stop_job(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def set_lesson(self, key):
        self.key = key
        self.chosen = progress.emote_of(progress.record(*key)) if key else None
        self._msg = ""
        self._draw()

    def _slots(self):
        n = len(progress.EMOTES)
        total = n * self.SIZE + (n - 1) * self.GAP
        x0 = (self.winfo_width() - total) / 2
        return [(x0 + i * (self.SIZE + self.GAP), k) for i, (k, _l) in enumerate(progress.EMOTES)]

    def _draw(self):
        self.delete("all")
        self._imgs = []
        w = self.winfo_width()
        a = round(self._vis * self.STEPS) / self.STEPS     # tingkat pudar (gambar di-cache)
        if w < 60 or a <= 0:
            return                                          # tersembunyi
        y = 3
        for x, k in self._slots():
            on = self.chosen is None or k == self.chosen or k == self._hover
            fg, disc = EMOTE_STYLE[k] if on else (USED_FG, USED_DISC)
            big = k == self._hover or k == self.chosen
            size = self.SIZE + 4 if big else self.SIZE
            ph = I.icon("emo_" + k, _mix(fg, a), C.BG, size, disc=_mix(disc, a))
            if ph is not None:
                self._imgs.append(ph)
                self.create_image(x + self.SIZE / 2, y + self.SIZE / 2, image=ph)
        for x, k in self._slots():   # nama reaksi tepat di bawah tiap emote
            on = k == self.chosen or k == self._hover
            self.create_text(x + self.SIZE / 2, y + self.SIZE + 11,
                             text=progress.EMOTE_LABEL_EN[k], font=self._font,
                             fill=_mix(C.TEXT if on else C.MUTED, a))

    def _at(self, x, y):
        for sx, k in self._slots():
            if sx - 4 <= x <= sx + self.SIZE + 4 and 2 <= y <= 6 + self.SIZE + 4:
                return k
        return None

    def _set_hover(self, k):
        if k != self._hover:
            self._hover = k
            self.config(cursor="hand2" if k and k != self.chosen else "")
            self._draw()

    def _motion(self, e):
        self._set_hover(self._at(e.x, e.y))

    def _click(self, e):
        k = self._at(e.x, e.y)
        if k is None or self.key is None or k == self.chosen or self._vis < 0.5:
            return
        try:
            if progress.set_emote(*self.key, k):
                self.chosen = k
        except Exception as exc:
            C.log(f"Emote tidak tersimpan: {exc!r}")
        self.config(cursor="")
        self._draw()

    def _clear_msg(self):
        if self.winfo_exists():
            self._msg = ""
            self._draw()


# --- popup kuis ----------------------------------------------------------------------------
class QuizPopup(tk.Toplevel):
    W = 400

    def __init__(self, master, student_id, items, lesson_title, on_close=None):
        super().__init__(master, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        self.title("Quick quiz")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        dark_titlebar(self)
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self.sid, self.items, self.i = student_id, items, 0
        self.on_close = on_close
        self._answered = False

        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        top = tk.Frame(body, bg=C.CARD)
        top.pack(fill="x")
        tk.Label(top, text="Quick quiz", bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 14, "bold"), anchor="w").pack(side="left")
        self.step = tk.Label(top, text="", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10))
        self.step.pack(side="right")
        tk.Label(body, text=f"Video: {lesson_title}", bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 9), anchor="w", wraplength=self.W).pack(fill="x", pady=(2, 12))
        self.q = tk.Label(body, text="", bg=C.CARD, fg=C.TEXT, font=(C.FONT, 12),
                          anchor="w", justify="left", wraplength=self.W)
        self.q.pack(fill="x")
        self.var = tk.StringVar()
        self.entry = RoundEntry(body, textvariable=self.var, width_chars=30, height=40,
                                fill=C.BG, placeholder="Type your answer here")
        self.entry.pack(fill="x", pady=(14, 0))
        self.result = tk.Label(body, text="", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                               anchor="nw", justify="left", wraplength=self.W, height=2)
        self.result.pack(fill="x", pady=(10, 0))
        self.btns = tk.Frame(body, bg=C.CARD)
        self.btns.pack(fill="x", pady=(8, 0))
        self.ok = RoundButton(self.btns, text="Submit answer", command=self._submit,
                              bg=C.ACCENT, fg="white", activebackground=C.ACCENT_HOVER,
                              activeforeground="white", font=(C.FONT, 11, "bold"),
                              padx=22, pady=7)
        self.ok.pack(side="right")
        self.later = RoundButton(self.btns, text="Maybe later", command=self._close,
                                 bg=C.BORDER, fg=C.TEXT, activebackground=C.CARD_HOVER,
                                 font=(C.FONT, 11), padx=18, pady=7)
        self.later.pack(side="right", padx=(0, 8))
        self.entry.entry.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self._close())
        self.bind("<Return>", lambda e: self._submit() if self._answered else None)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._show()
        self._center(master)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.entry.entry.focus_set()

    def _center(self, master):
        self.update_idletasks()
        parent = master.winfo_toplevel()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.lift()

    def _show(self):
        q = self.items[self.i]
        self._answered = False
        n = len(self.items)
        self.step.config(text=f"Question {self.i + 1} / {n}" if n > 1 else "")
        self.q.config(text=q["question"])
        self.var.set("")
        self.entry.entry.config(state="normal")
        self.result.config(text="", fg=C.MUTED)
        self.ok.config(text="Submit answer")
        self.later.config(text="Maybe later")

    def _submit(self):
        if self._answered:          # tombol jadi "Lanjut" / "Selesai"
            if self.i + 1 < len(self.items):
                self.i += 1
                self._show()
                self.entry.entry.focus_set()
            else:
                self._close()
            return
        answer = " ".join(self.var.get().split())
        if not answer:
            self.result.config(text="Please type an answer first.", fg=C.ERROR)
            return
        q = self.items[self.i]
        correct = quizzes.check(answer, q.get("answer"))
        if not progress.save_answer(self.sid, q, answer, correct):
            self.result.config(text="Could not save your answer. Try again.", fg=C.ERROR)
            return
        self._answered = True
        self.entry.entry.config(state="disabled")
        if correct is True:
            self.result.config(text="Correct! Great job.", fg=C.ON)
        elif correct is False:
            key = q["answer"].split(";")[0].strip()
            self.result.config(text=f"Not quite. The correct answer: {key}", fg=C.ACCENT)
        else:
            self.result.config(text="Answer sent. Your teacher will check it.", fg=C.ON)
        last = self.i + 1 >= len(self.items)
        self.ok.config(text="Done" if last else "Next question")
        self.later.config(text="Close")

    def _close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        cb, self.on_close = self.on_close, None
        self.destroy()
        if cb is not None:
            cb()
