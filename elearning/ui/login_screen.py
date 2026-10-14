"""Layar login siswa, dengan video sebagai latar."""

import tkinter as tk

from elearning import config as C
from elearning.students import lookup_student
from elearning.teachers import check_teacher, is_teacher_id
from elearning.ui.video_background import VideoBackground, find_video
from elearning.ui.widgets import add_hover


class LoginScreen(tk.Frame):
    def __init__(self, master, on_success, on_teacher=None):
        super().__init__(master, bg=C.BG)
        self.on_success = on_success
        self.on_teacher = on_teacher
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

        tk.Label(card, text="B", bg=C.ACCENT, fg="white",
                 font=(C.FONT, 26, "bold"), width=2).pack(pady=(0, 14))
        tk.Label(card, text=C.APP_NAME, bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 20, "bold")).pack()
        tk.Label(card, text="Masuk untuk mulai belajar", bg=C.CARD,
                 fg=C.MUTED, font=(C.FONT, 11)).pack(pady=(4, 22))

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

        # Kolom PIN: hanya muncul kalau yang diketik adalah ID guru (GURU...)
        self.pin_box = tk.Frame(card, bg=C.CARD)
        tk.Label(self.pin_box, text="PIN Guru", bg=C.CARD, fg=C.MUTED,
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

    def _toggle_pin(self, *_):
        if is_teacher_id(self.id_var.get()):
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

        if is_teacher_id(sid):
            if not self.pin_var.get():
                self.error_lbl.config(text="Masukkan PIN guru.")
                self.pin_entry.focus_set()
                return
            teacher = check_teacher(sid, self.pin_var.get())
            if teacher is None:
                self.error_lbl.config(text="ID atau PIN salah.")
                self.pin_var.set("")
                return
            if self.on_teacher is not None:
                self.on_teacher(teacher)
            return

        student = lookup_student(sid)
        if student is None:
            self.error_lbl.config(
                text="ID tidak ditemukan. Cek lagi atau tanya guru.")
            return
        self.on_success(student)
