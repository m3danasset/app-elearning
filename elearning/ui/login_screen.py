"""Layar login siswa, dengan video sebagai latar."""

import tkinter as tk

from elearning import config as C
from elearning.admins import check_admin, is_admin_id
from elearning.students import STATUS_EXPIRED, lookup_student
from elearning.teachers import check_teacher, is_teacher_id
from elearning.ui.video_background import VideoBackground, find_video
from elearning.ui.widgets import add_hover


class LoginScreen(tk.Frame):
    def __init__(self, master, on_success, on_teacher=None, on_admin=None):
        super().__init__(master, bg=C.BG)
        self.on_success = on_success
        self.on_teacher = on_teacher
        self.on_admin = on_admin
        self._build()
        self.winfo_toplevel().bind("<Return>", lambda e: self.do_login())

    def destroy(self):
        self.winfo_toplevel().unbind("<Return>")
        super().destroy()  # ikut menghentikan video

    def _build(self):
        # Lapisan bawah: video
        bg = VideoBackground(self, find_video(C.VIDEO_DIR),
                             dim=C.VIDEO_DIM, fallback_bg=C.BG)
        bg.place(x=0, y=0, relwidth=1, relheight=1)

        # Lapisan atas: kartu login
        card = tk.Frame(self, bg=C.CARD, highlightthickness=1,
                        highlightbackground=C.BORDER, padx=40, pady=34)
        card.place(relx=0.5, rely=0.5, anchor="center")

        self._logo_img = self._load_logo(width=270)
        if self._logo_img is not None:
            tk.Label(card, image=self._logo_img, bg=C.CARD, bd=0).pack(pady=(0, 14))
        else:  # logo tidak ada / gagal dibuka: pakai teks nama aplikasi
            tk.Label(card, text=C.APP_NAME, bg=C.CARD, fg=C.TEXT,
                     font=(C.FONT, 20, "bold")).pack(pady=(0, 4))
        tk.Label(card, text="Masuk untuk mulai belajar", bg=C.CARD,
                 fg=C.MUTED, font=(C.FONT, 11)).pack(pady=(0, 22))

        tk.Label(card, text="ID Siswa / Guru", bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(anchor="w")

        border = tk.Frame(card, bg=C.BORDER, padx=1, pady=1)
        border.pack(fill="x", pady=(6, 0))
        self.id_var = tk.StringVar()
        entry = tk.Entry(border, textvariable=self.id_var, width=28,
                         bg=C.BG, fg=C.TEXT, insertbackground=C.TEXT,
                         relief="flat", font=(C.FONT, 13))
        entry.pack(fill="x", ipady=9, padx=1, pady=1)
        entry.bind("<FocusIn>", lambda e: border.config(bg=C.ACCENT))
        entry.bind("<FocusOut>", lambda e: border.config(bg=C.BORDER))
        entry.focus_set()

        # Kolom PIN: hanya muncul kalau yang diketik adalah ID guru (GURU...) atau admin (ADMIN...)
        self.pin_box = tk.Frame(card, bg=C.CARD)
        tk.Label(self.pin_box, text="PIN", bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(anchor="w")
        pin_border = tk.Frame(self.pin_box, bg=C.BORDER, padx=1, pady=1)
        pin_border.pack(fill="x", pady=(6, 0))
        self.pin_var = tk.StringVar()
        self.pin_entry = tk.Entry(pin_border, textvariable=self.pin_var, show="•",
                                  width=28, bg=C.BG, fg=C.TEXT,
                                  insertbackground=C.TEXT, relief="flat",
                                  font=(C.FONT, 13))
        self.pin_entry.pack(fill="x", ipady=9, padx=1, pady=1)
        self.pin_entry.bind("<FocusIn>", lambda e: pin_border.config(bg=C.ACCENT))
        self.pin_entry.bind("<FocusOut>", lambda e: pin_border.config(bg=C.BORDER))
        self.id_var.trace_add("write", self._toggle_pin)

        self.error_lbl = tk.Label(card, text="", bg=C.CARD, fg=C.ERROR,
                                  font=(C.FONT, 10), wraplength=300,
                                  justify="left", anchor="w")
        self.error_lbl.pack(fill="x", pady=(10, 0))

        btn = tk.Button(card, text="Masuk", command=self.do_login,
                        bg=C.ACCENT, fg="white",
                        activebackground=C.ACCENT_HOVER,
                        activeforeground="white", relief="flat", bd=0, highlightthickness=0,
                        font=(C.FONT, 12, "bold"), cursor="hand2")
        btn.pack(fill="x", pady=(14, 0), ipady=9)
        add_hover(btn, C.ACCENT, C.ACCENT_HOVER)

    def _load_logo(self, width):
        """Muat assets\\logo.png (PNG transparan) dan kecilkan ke lebar tertentu."""
        try:
            from PIL import Image, ImageTk
            img = Image.open(C.resource_path("assets", "logo.png")).convert("RGBA")
            height = round(img.height * width / img.width)
            img = img.resize((width, height), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            C.log(f"Logo login tidak bisa dimuat: {e}")
            return None

    def _toggle_pin(self, *_):
        typed = self.id_var.get()
        if is_teacher_id(typed) or is_admin_id(typed):
            if not self.pin_box.winfo_ismapped():
                self.pin_box.pack(fill="x", pady=(14, 0), before=self.error_lbl)
        else:
            self.pin_box.pack_forget()
            self.pin_var.set("")

    def do_login(self):
        sid = self.id_var.get().strip()
        if not sid:
            self.error_lbl.config(text="ID belum diisi.")
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
