"""Popup dev: pilih akun untuk masuk tanpa ID / PIN (Ctrl kanan + Shift kanan + Backspace
di layar login).

Gaya sama dengan MiniConfirm: kartu bersudut bulat tanpa bilah judul Windows, semua digambar
di SATU canvas (teks cari = teks canvas, bukan Entry). Ketik = saring nama / ID, panah atas /
bawah = pilih, Enter / klik = masuk, Esc / klik di luar = tutup.
"""

import tkinter as tk

from elearning import config as C
from elearning import students as S
from elearning import teachers as T
from elearning.admins import ADMINS
from elearning.trial import trial_student
from elearning.ui import ui_icons as I

KEY = "#010203"            # warna kunci transparan (sudut kartu)
W, R = 420, 14
ROW_H, ROWS = 34, 10       # tinggi baris, jumlah baris yang terlihat
HEAD = 92                  # judul + kolom cari
FOOT = 34
H = HEAD + ROW_H * ROWS + FOOT
KIND = {"admin": ("Admin", C.ACCENT), "teacher": ("Guru", "#4f8f6f"),
        "adult": ("Dewasa", "#4f6f9a"), "kids": ("SUPERKIDS", "#a8507a"),
        "trial": ("Trial", "#6f6f6f")}


def accounts():
    """[(jenis, id, nama, akun)] semua akun yang bisa dipilih."""
    out = [("admin", uid, a["name"], {"id": uid, "name": a["name"]}) for uid, a in ADMINS.items()]
    out += [("teacher", t["id"], t["name"], t) for t in T.list_teachers()]
    studs = sorted(S.list_students(), key=lambda s: s["name"].lower())
    out += [("kids" if s["program"] == "kids" else "adult", s["id"], s["name"], s) for s in studs]
    out.append(("trial", "TRIAL", "Calon murid (trial)", None))
    return out


class DevLoginPicker(tk.Toplevel):
    def __init__(self, master, on_pick):
        """on_pick(jenis, akun) dipanggil setelah popup tertutup."""
        top = master.winfo_toplevel()
        super().__init__(top, bg=KEY)
        self.withdraw()
        self.overrideredirect(True)
        self.transient(top)
        self.on_pick = on_pick
        self.items = accounts()
        self.query = ""
        self.shown = list(self.items)
        self.sel = 0
        self.first = 0             # baris pertama yang terlihat
        self._imgs = []
        rounded = True
        try:
            self.attributes("-transparentcolor", KEY)
        except tk.TclError:
            rounded = False
        self.outer = KEY if rounded else C.CARD
        self.cv = tk.Canvas(self, width=W, height=H, bg=self.outer, highlightthickness=0, bd=0)
        self.cv.pack()
        self.f_title = (C.FONT, 12, "bold")
        self.f_row = (C.FONT, 10)
        self.f_sub = (C.FONT, 8)
        self.f_kind = (C.FONT, 8, "bold")
        self._static()
        self._draw()

        self.bind("<Key>", self._on_key)
        self.cv.bind("<Button-1>", self._on_click)
        self.cv.bind("<MouseWheel>", self._on_wheel)
        self.cv.bind("<Motion>", self._on_motion)

        self.update_idletasks()
        x = top.winfo_rootx() + (top.winfo_width() - W) // 2
        y = top.winfo_rooty() + (top.winfo_height() - H) // 2
        self.geometry(f"{W}x{H}+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.lift()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()

    # --- gambar ------------------------------------------------------------------------
    def _static(self):
        cv = self.cv
        card = I.pill(W, H, C.CARD, self.outer, r=R, border=C.BORDER)
        if card is not None:
            self._card = card
            cv.create_image(0, 0, image=card, anchor="nw")
        cv.create_text(20, 26, text="Masuk sebagai (dev)", anchor="w", fill=C.TEXT,
                       font=self.f_title)
        field = I.pill(W - 32, 34, C.BG, C.CARD, r=10, border=C.BORDER)
        if field is not None:
            self._field = field
            cv.create_image(16, 46, image=field, anchor="nw")
        self.t_query = cv.create_text(30, 63, text="", anchor="w", font=self.f_row)
        cv.create_text(20, H - FOOT / 2, anchor="w", fill=C.LOCKED, font=self.f_sub,
                       text="ketik = cari   ·   ↑ ↓ = pilih   ·   Enter = masuk   ·   Esc = tutup")

    def _draw(self):
        cv = self.cv
        cv.delete("row")
        self._imgs = []
        cv.itemconfigure(self.t_query, text=self.query or "Cari nama atau ID...",
                         fill=C.TEXT if self.query else C.MUTED)
        if not self.shown:
            cv.create_text(W / 2, HEAD + ROW_H * 2, text="Tidak ada akun yang cocok.",
                           fill=C.MUTED, font=self.f_row, tags="row")
            return
        for n in range(ROWS):
            i = self.first + n
            if i >= len(self.shown):
                break
            kind, uid, name, _acc = self.shown[i]
            y = HEAD + n * ROW_H
            if i == self.sel:
                p = I.pill(W - 24, ROW_H - 4, C.CARD_HOVER, C.CARD, r=8)
                if p is not None:
                    self._imgs.append(p)
                    cv.create_image(12, y + 2, image=p, anchor="nw", tags="row")
            label, color = KIND[kind]
            tag = I.pill(78, 20, color, C.CARD_HOVER if i == self.sel else C.CARD, r=10)
            if tag is not None:
                self._imgs.append(tag)
                cv.create_image(22, y + ROW_H / 2 - 10, image=tag, anchor="nw", tags="row")
            cv.create_text(61, y + ROW_H / 2, text=label, fill="#ffffff", font=self.f_kind,
                           tags="row")
            cv.create_text(112, y + ROW_H / 2, text=name, anchor="w", fill=C.TEXT,
                           font=self.f_row, tags="row")
            cv.create_text(W - 24, y + ROW_H / 2, text=uid, anchor="e", fill=C.MUTED,
                           font=self.f_sub, tags="row")
        if len(self.shown) > ROWS:       # penanda posisi gulir (kapsul tipis di kanan)
            track = ROW_H * ROWS
            th = max(24, track * ROWS / len(self.shown))
            ty = HEAD + (track - th) * self.first / max(1, len(self.shown) - ROWS)
            p = I.pill(4, int(th), C.BORDER, C.CARD, r=2)
            if p is not None:
                self._imgs.append(p)
                cv.create_image(W - 9, ty, image=p, anchor="nw", tags="row")

    # --- interaksi ---------------------------------------------------------------------
    def _filter(self):
        q = self.query.strip().lower()
        self.shown = [it for it in self.items
                      if not q or q in it[2].lower() or q in it[1].lower()
                      or q in KIND[it[0]][0].lower()]
        self.sel = self.first = 0
        self._draw()

    def _select(self, i):
        if not self.shown:
            return
        self.sel = max(0, min(len(self.shown) - 1, i))
        if self.sel < self.first:
            self.first = self.sel
        elif self.sel >= self.first + ROWS:
            self.first = self.sel - ROWS + 1
        self._draw()

    def _on_key(self, e):
        ks = e.keysym
        if ks == "Escape":
            self._close()
        elif ks in ("Return", "KP_Enter"):
            self._pick(self.sel)
        elif ks == "Down":
            self._select(self.sel + 1)
        elif ks == "Up":
            self._select(self.sel - 1)
        elif ks == "Next":
            self._select(self.sel + ROWS)
        elif ks == "Prior":
            self._select(self.sel - ROWS)
        elif ks == "BackSpace":
            if self.query:
                self.query = "" if e.state & 0x4 else self.query[:-1]
                self._filter()
        elif e.char and e.char.isprintable() and not e.state & 0x4 and len(self.query) < 40:
            self.query += e.char
            self._filter()
        return "break"

    def _row_at(self, x, y):
        if not (0 <= x < W and HEAD <= y < HEAD + ROWS * ROW_H):
            return None
        i = self.first + int((y - HEAD) // ROW_H)
        return i if i < len(self.shown) else None

    def _on_click(self, e):
        if not (0 <= e.x < W and 0 <= e.y < H):
            self._close()          # klik di luar kartu (grab: event tetap sampai ke sini)
            return
        i = self._row_at(e.x, e.y)
        if i is not None:
            self._pick(i)

    def _on_motion(self, e):
        i = self._row_at(e.x, e.y)
        self.cv.config(cursor="hand2" if i is not None else "")
        if i is not None and i != self.sel:
            self.sel = i
            self._draw()

    def _on_wheel(self, e):
        if len(self.shown) <= ROWS:
            return
        step = -1 if e.delta > 0 else 1
        self.first = max(0, min(len(self.shown) - ROWS, self.first + step * 3))
        self.sel = max(self.first, min(self.first + ROWS - 1, self.sel))
        self._draw()

    def _pick(self, i):
        if not self.shown or i is None:
            return
        kind, _uid, _name, acc = self.shown[i]
        if kind == "trial":
            acc = trial_student()
        self._close()
        self.on_pick(kind, acc)

    def _close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        top = self.master
        self.destroy()
        try:
            top.focus_force()      # fokus kembali ke layar login (bisa langsung ketik ID)
        except tk.TclError:
            pass
