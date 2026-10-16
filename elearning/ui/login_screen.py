"""Layar login gaya claude.ai: dua kolom.

Kiri  : logo brand versi full, judul besar (huruf serif), tagline, lalu kartu login
        bersudut bulat: tombol "Coba kelas trial", kolom ID, kolom PIN (muncul otomatis
        untuk ID guru / admin), dan tombol Masuk.
Kanan : slideshow otomatis karya murid dari portfolio (lihat showcase.py).
        Di jendela sempit panel kanan disembunyikan.

Logo diambil dari assets\\logo.png (lihat brand.py).
"""

import tkinter as tk

from elearning import brand
from elearning import config as C
from elearning.admins import check_admin, is_admin_id
from elearning.students import STATUS_EXPIRED, lookup_student
from elearning.teachers import check_teacher, is_teacher_id
from elearning.trial import is_trial_id, trial_student
from elearning.ui.controls import RoundButton, RoundCard, RoundEntry
from elearning.ui.showcase import Showcase

GAP = 28              # jarak kolom login ke slideshow
CARD_W = 420


class LoginScreen(tk.Frame):
    def __init__(self, master, on_success, on_teacher=None, on_admin=None):
        super().__init__(master, bg=C.LOGIN_BG)
        self.on_success = on_success
        self.on_teacher = on_teacher
        self.on_admin = on_admin
        self._build()
        self.winfo_toplevel().bind("<Return>", lambda e: self.do_login())

    def destroy(self):
        self.winfo_toplevel().unbind("<Return>")
        super().destroy()  # ikut menghentikan slideshow / video

    def _build(self):
        bg = C.LOGIN_BG

        # --- kiri: brand + kartu login ---------------------------------------------
        self.left = tk.Frame(self, bg=bg)
        col = self.col = tk.Frame(self.left, bg=bg)
        col.place(relx=0.5, rely=0.5, anchor="center")

        # Logo brand full, agak besar, sedikit turun mendekati kartu login
        brand.pack_lockup(col, bg, logo_size=(360, 110), mark_size=80, font_size=18,
                          side="top", serif=True).pack(pady=(40, 40))

        card = RoundCard(col, width=CARD_W, radius=24, pad=28)
        card.pack()
        box = card.inner

        self.id_var = tk.StringVar()
        self.id_box = RoundEntry(box, self.id_var, placeholder="Masukkan ID kamu",
                                 font=(C.FONT, 11), height=44, fill=C.LOGIN_BG)
        self.id_box.pack(fill="x")
        self.id_box.entry.focus_set()

        # Kolom PIN: hanya muncul kalau yang diketik adalah ID guru (GURU...) atau admin (ADMIN...)
        self.pin_var = tk.StringVar()
        self.pin_box = RoundEntry(box, self.pin_var, show="•", placeholder="PIN",
                                  font=(C.FONT, 11), height=44, fill=C.LOGIN_BG)
        self.pin_entry = self.pin_box.entry
        self.id_var.trace_add("write", self._toggle_pin)

        self.error_lbl = tk.Label(box, text="", bg=bg, fg=C.ERROR, font=(C.FONT, 10),
                                  wraplength=CARD_W - 60, justify="left", anchor="w")
        self.error_lbl.pack(fill="x", pady=(8, 0))

        self.login_btn = RoundButton(box, text="Masuk", command=self.do_login,
                                     bg="#f0eee6", fg="#1a1918", activebackground="#ffffff",
                                     font=(C.FONT, 11, "bold"), pady=10, radius=10,
                                     border=None)
        self.login_btn.pack(fill="x", pady=(6, 0))

        # --- kanan: slideshow karya murid ---------------------------------------------
        self.right = tk.Frame(self, bg=bg)
        Showcase(self.right, bg=bg).pack(fill="both", expand=True)

        self.bind("<Configure>", lambda e: self._layout() if e.widget is self else None)
        col.bind("<Configure>", lambda e: self._layout())
        self.update_idletasks()
        self._min_h = col.winfo_reqheight() + 54   # ruang untuk kolom PIN: tinggi tidak melompat

    def _layout(self, _event=None):
        """Kolom login dan slideshow SAMA BESAR (ukuran tetap = ukuran blok login),
        berdampingan di tengah jendela. Tampilan sama persis di mode jendela & layar penuh."""
        W, H = self.winfo_width(), self.winfo_height()
        bw = max(self.col.winfo_reqwidth(), CARD_W)
        bh = max(self.col.winfo_reqheight(), self._min_h) + 8   # +8: tepi bawah kartu tidak terpotong
        if W < bw + GAP + bw + 56:   # jendela sempit: hanya login, di tengah
            self.right.place_forget()
            self.left.place(x=0, y=0, relwidth=1, relheight=1, width=0, height=0)
            return
        # Slideshow rasio tetap 10:13 (lebar:tinggi), selebar blok login; boleh lebih tinggi.
        # Kalau layar kurang tinggi, slideshow mengecil (tetap 10:13).
        pw = bw
        ph = pw * 13 / 10
        if ph > H - 56:
            ph = max(bh, H - 56)
            pw = ph * 10 / 13
        x0 = (W - (bw + GAP + pw)) / 2
        cy = H / 2
        # Slideshow di KIRI, login di KANAN
        self.right.place(x=x0, y=max(0, cy - ph / 2), width=pw, height=ph)
        self.left.place(x=x0 + pw + GAP, y=max(0, cy - bh / 2), width=bw, height=bh,
                        relwidth=0, relheight=0)

    def _toggle_pin(self, *_):
        typed = self.id_var.get()
        if is_teacher_id(typed) or is_admin_id(typed):
            if not self.pin_box.winfo_ismapped():
                self.pin_box.pack(fill="x", pady=(10, 0), before=self.error_lbl)
        else:
            self.pin_box.pack_forget()
            self.pin_var.set("")

    def _login_trial(self):
        self.error_lbl.config(text="")
        self.on_success(trial_student())

    def do_login(self):
        sid = self.id_var.get().strip()
        if not sid:
            self.error_lbl.config(text="ID belum diisi.")
            self.id_box.entry.focus_set()
            return

        if is_admin_id(sid) or is_teacher_id(sid):
            if not self.pin_var.get():
                self.error_lbl.config(text="Masukkan PIN.")
                self.pin_entry.focus_set()
                return
            if is_admin_id(sid):
                account, handler = check_admin(sid, self.pin_var.get()), self.on_admin
            else:
                account, handler = check_teacher(sid, self.pin_var.get()), self.on_teacher
            if account is None:
                self.error_lbl.config(text="ID atau PIN salah.")
                self.pin_var.set("")
                return
            if handler is not None:
                handler(account)
            return

        if is_trial_id(sid):   # calon murid: tanpa PIN, langsung pilih ANIMATION / MODELING
            self._login_trial()
            return

        student = lookup_student(sid)
        if student is None:
            self.error_lbl.config(
                text="ID tidak ditemukan. Cek lagi atau tanya guru.")
            return
        if student.get("status") == STATUS_EXPIRED:
            self.error_lbl.config(
                text="Akun kamu sudah expired. Hubungi guru untuk mengaktifkan kembali.")
            return
        self.error_lbl.config(text="")
        self.on_success(student)
