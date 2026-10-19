"""Dialog halaman Akun di jendela Dev (gaya Settings Claude, tanpa animasi):

- NewAccount     : akun baru murid dewasa / SUPERKIDS / guru / admin (ID otomatis, PIN acak,
                   tanggal lahir, kursus dibuka, "langsung masuk").
- StudentEditor  : nama, ID, kategori, status, tanggal lahir, kursus tampil / buka.
- AccountEditor  : nama + PIN guru / admin.
- DeleteConfirm  : hapus akun (fokus awal Batal).
- ResetProgress  : pilih murid (banyak) + bagian yang di-reset (klik Reset dua kali).

Semua memakai Card: kartu bersudut bulat tanpa bilah judul, tingginya mengikuti isi.
"""

import os
import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning.ui import dev_panel as DP
from elearning.ui import ui_icons as I

PANEL, FG, MUTED, LINE = DP.PANEL, DP.FG, DP.MUTED, DP.LINE
LABEL_W = 150
TYPES = (("adult", "Dewasa (PB)"), ("kids", "SUPERKIDS (SK)"), ("teacher", "Guru"),
         ("admin", "Admin"))


def random_pin(n=6):
    """PIN angka acak (os.urandom: tanpa modul random)."""
    return str(int.from_bytes(os.urandom(4), "big") % 10 ** n).zfill(n)


class Card(tk.Toplevel):
    """Kartu dialog bersudut bulat, selalu di atas, di tengah panel; tinggi = isi (fit)."""

    def __init__(self, panel, w):
        super().__init__(panel)
        self.panel, self.W = panel, w
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self._rounded = True
        try:
            self.attributes("-transparentcolor", DP.KEY)
        except tk.TclError:
            self._rounded = False
        outer = DP.KEY if self._rounded else PANEL
        self.configure(bg=outer)
        self.cv = tk.Canvas(self, width=w, height=100, bg=outer, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self._bg_item = self.cv.create_image(0, 0, anchor="nw")
        self._bg = None
        self.body = tk.Frame(self.cv, bg=PANEL)
        self.cv.create_window(6, 6, window=self.body, anchor="nw", width=w - 12)
        self._pos = None
        self.bind("<Escape>", lambda e: self.destroy())

    def fit(self):
        """Ukuran kartu mengikuti isi (dipanggil lagi kalau baris muncul / hilang)."""
        self.update_idletasks()
        h = self.body.winfo_reqheight() + 12
        self.cv.configure(height=h)
        self._bg = DP._pill(self.W, h, PANEL, DP.KEY if self._rounded else PANEL,
                            r=DP.RADIUS, border=LINE)
        self.cv.itemconfigure(self._bg_item, image=self._bg)
        if self._pos is None:
            p = self.panel
            self._pos = (p.winfo_rootx() + (p.winfo_width() - self.W) // 2,
                         p.winfo_rooty() + max(20, (p.winfo_height() - h) // 2 - 40))
        self.geometry(f"{self.W}x{h}+{self._pos[0]}+{self._pos[1]}")

    def show(self, focus):
        self.fit()
        self.deiconify()
        self.lift()
        self.after(10, lambda: self._focus(focus))

    def _focus(self, w):
        try:
            self.focus_force()
            w.focus_set()
        except tk.TclError:
            pass

    # --- bagian umum -----------------------------------------------------------------------
    def head(self, title, desc=""):
        b = tk.Frame(self.body, bg=PANEL)
        b.pack(fill="x", padx=22, pady=(18, 4))
        DP._draggable(self, b)
        tk.Label(b, text=title, bg=PANEL, fg=FG, font=(C.FONT, 14, "bold"),
                 anchor="w").pack(fill="x")
        if desc:
            tk.Label(b, text=desc, bg=PANEL, fg=MUTED, font=(C.FONT, 9), anchor="w",
                     justify="left", wraplength=self.W - 60).pack(fill="x", pady=(2, 0))
        grid = tk.Frame(self.body, bg=PANEL)
        grid.pack(fill="x", padx=22, pady=(10, 0))
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(0, minsize=LABEL_W)
        return grid

    def footer(self, ok_text, ok, kind="primary", note=""):
        self.msg = tk.Label(self.body, text=note, bg=PANEL, fg=MUTED, font=(C.FONT, 9),
                            anchor="w", justify="left", wraplength=self.W - 60)
        self.msg.pack(fill="x", padx=22, pady=(10, 0))
        btns = tk.Frame(self.body, bg=PANEL)
        btns.pack(fill="x", padx=22, pady=(14, 18))
        ok_btn = DP._btn(btns, ok_text, ok, kind)
        ok_btn.pack(side="right")
        cancel = DP._btn(btns, "Batal", self.destroy)
        cancel.pack(side="right", padx=(0, 8))
        return ok_btn, cancel

    def error(self, text):
        self.msg.config(text=text, fg=C.ERROR)
        self.fit()

    @staticmethod
    def label(grid, r, text, hint=""):
        """Label kolom (kiri) + keterangan kecil di bawahnya supaya tidak salah paham."""
        box = tk.Frame(grid, bg=PANEL)
        box.grid(row=r, column=0, sticky="nw", padx=(0, 12), pady=(9, 5))
        tk.Label(box, text=text, bg=PANEL, fg=FG, font=(C.FONT, 10), anchor="w").pack(fill="x")
        if hint:
            tk.Label(box, text=hint, bg=PANEL, fg=MUTED, font=(C.FONT, 8), anchor="w",
                     justify="left", wraplength=LABEL_W - 8).pack(fill="x")
        return box

    def entry(self, parent, var, placeholder="", width=24, on_enter=None):
        from elearning.ui.controls import RoundEntry
        e = RoundEntry(parent, var, placeholder=placeholder, width_chars=width,
                       font=(C.FONT, 10), height=34, fill=DP.SEG_BG, radius=8)
        if on_enter is not None:
            e.entry.bind("<Return>", lambda ev: on_enter())
        return e

    def pin_box(self, grid, var, on_enter):
        """Kolom PIN + tombol Acak (PIN angka 6 digit)."""
        f = tk.Frame(grid, bg=PANEL)
        self.entry(f, var, "4-10 karakter", 14, on_enter).pack(side="left", fill="x",
                                                                expand=True)
        DP._btn(f, "Buat PIN acak", lambda: var.set(random_pin())).pack(side="left",
                                                                        padx=(8, 0))
        return f


class Chips(tk.Canvas):
    """Pilihan banyak (kursus dibuka): kapsul bisa dinyalakan / dimatikan, turun baris."""

    H, GAP = 30, 6

    def __init__(self, master, options, selected, width=330):
        super().__init__(master, width=width, height=self.H, bg=PANEL, highlightthickness=0,
                         bd=0, cursor="hand2")
        self.f = tkfont.Font(family=C.FONT, size=9)
        self.opts, self.sel, self.Wd = list(options), set(selected), width
        self._imgs, self._boxes = [], []
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        self.delete("all")
        self._imgs, self._boxes = [], []
        x = y = 0
        for key, label, color in self.opts:
            w = self.f.measure(label) + 34
            if x and x + w > self.Wd:
                x, y = 0, y + self.H + self.GAP
            on = key in self.sel
            img = DP._pill(w, self.H, DP.SEG_ON if on else PANEL, PANEL, r=self.H / 2,
                           border="#5a5953" if on else DP.SEG_LINE)
            self._imgs.append(img)
            self.create_image(x, y, anchor="nw", image=img)
            d = I.dot(color if on else "#4a4945", DP.SEG_ON if on else PANEL, 8, 3.6)
            self._imgs.append(d)
            self.create_image(x + 14, y + self.H / 2, image=d)
            self.create_text(x + 24, y + self.H / 2, text=label, anchor="w", font=self.f,
                             fill=FG if on else MUTED)
            self._boxes.append((x, y, x + w, y + self.H, key))
            x += w + self.GAP
        self.configure(height=y + self.H)

    def _click(self, e):
        for x0, y0, x1, y1, key in self._boxes:
            if x0 <= e.x < x1 and y0 <= e.y < y1:
                self.sel ^= {key}
                self._draw()
                return

    def selected(self):
        return [k for k, _l, _c in self.opts if k in self.sel]


# --- akun baru ---------------------------------------------------------------------------------
class NewAccount(Card):
    def __init__(self, panel, kind="adult"):
        from elearning.ui.widgets import Switch
        super().__init__(panel, 600)
        self.kind = kind if kind in dict(TYPES) else "adult"
        g = self.grid = self.head("Buat akun baru",
                                  "Murid masuk dengan ID saja. Guru & admin masuk dengan ID + PIN.")
        self.v = {k: tk.StringVar() for k in ("name", "id", "pin", "birth")}
        self.v["pin"].set(random_pin())
        self.label(g, 0, "Jenis akun")
        self.seg = DP.Seg(g, TYPES, self.kind, self._set_kind)
        self.seg.grid(row=0, column=1, sticky="w", pady=4)
        self.label(g, 1, "Nama")
        self.name_e = self.entry(g, self.v["name"], "Nama lengkap", on_enter=self._save)
        self.name_e.grid(row=1, column=1, sticky="we", pady=4)
        self.label(g, 2, "ID login", "Diketik saat masuk")
        self.id_e = self.entry(g, self.v["id"], "otomatis", 14, self._save)
        self.id_auto = tk.Label(g, text="", bg=PANEL, fg=FG, font=("Consolas", 10), anchor="w")
        self.rows = {}
        self.rows["pin"] = (self.label(g, 3, "PIN login", "4-10 karakter"),
                            self.pin_box(g, self.v["pin"], self._save))
        self.rows["birth"] = (self.label(g, 4, "Tanggal lahir", "Opsional, untuk umur"),
                              self.entry(g, self.v["birth"], "YYYY-MM-DD (boleh kosong)", 24,
                                         self._save))
        self.rows["courses"] = (self.label(g, 5, "Kursus terbuka",
                                           "Klik untuk pilih. Yang tidak dipilih terkunci."),
                                tk.Frame(g, bg=PANEL))
        self.label(g, 6, "Masuk sebagai akun ini",
                   "Setelah dibuat, Dev langsung login ke akun baru (untuk mencoba)")
        self.login_after = False
        Switch(g, False, command=lambda v: setattr(self, "login_after", v),
               bg=PANEL).grid(row=6, column=1, sticky="w", pady=4)
        self.footer("Buat akun", self._save)
        self._set_kind(self.kind, first=True)
        self.show(self.name_e.entry)

    def _set_kind(self, kind, first=False):
        from elearning import admins as A
        from elearning import students as ST
        from elearning import teachers as T
        self.kind = kind
        self.seg.set(kind)
        student = kind in ("adult", "kids")
        for key, (lbl, w) in self.rows.items():
            show = student if key in ("birth", "courses") else not student
            if show:
                lbl.grid()
                w.grid(row=lbl.grid_info()["row"], column=1, sticky="we" if key != "courses"
                       else "w", pady=4)
            else:
                lbl.grid_remove()
                w.grid_remove()
        if student:
            self.id_auto.grid_remove()
            self.id_e.grid(row=2, column=1, sticky="w", pady=4)
            if not self.v["id"].get() or self._auto_id:
                self.v["id"].set(ST.next_student_id(kind))
            self._courses(kind)
        else:
            self.id_e.grid_remove()
            nid = T.next_teacher_id() if kind == "teacher" else A.next_admin_id()
            self.id_auto.config(text=f"{nid}   (dibuat otomatis)")
            self.id_auto.grid(row=2, column=1, sticky="w", pady=4)
        self._auto_id = True
        if not first:
            self.fit()

    def _courses(self, prog):
        from elearning.courses import courses_for
        box = self.rows["courses"][1]
        for w in box.winfo_children():
            w.destroy()
        opts = [(c["id"], c["title"], c["color"]) for c in courses_for(prog)]
        self.chips = Chips(box, opts, [o[0] for o in opts[:1]], width=self.W - 60 - LABEL_W)
        self.chips.pack(anchor="w")

    def _save(self):
        from elearning import admins as A
        from elearning import students as ST
        from elearning import teachers as T
        name = self.v["name"].get()
        try:
            if self.kind in ("adult", "kids"):
                birth = self.v["birth"].get().strip()
                if birth and not ST._birth_ok(birth):
                    raise ValueError("Tanggal lahir harus YYYY-MM-DD, mis. 2012-05-31.")
                st = ST.add_student(name, self.kind, self.v["id"].get().strip() or None)
                uid = st["id"]
                if birth:
                    ST.set_birth(uid, birth)
                if self.chips.selected():
                    ST.bulk_access({uid: (self.chips.selected(), [])})
            elif self.kind == "teacher":
                uid = T.add_teacher(name, self.v["pin"].get())["id"]
            else:
                uid = A.add_admin(name, self.v["pin"].get())["id"]
        except ValueError as exc:
            self.error(str(exc))
            return
        except OSError as exc:
            C.log(f"Dev: akun baru gagal disimpan: {exc!r}")
            self.error("Gagal menyimpan (folder data?).")
            return
        C.log(f"Dev: akun baru {uid} ({self.kind})")
        panel, login = self.panel, self.login_after
        self.destroy()
        panel.account_created(uid, login)


# --- edit murid ---------------------------------------------------------------------------------
class StudentEditor(Card):
    """Nama, ID, kategori, status, tanggal lahir, kursus tampil / buka. ID diganti PALING
    AKHIR beserta semua datanya (students.change_id)."""

    def __init__(self, panel, sid):
        from elearning import students as ST
        super().__init__(panel, 560)
        self.ST = ST
        self.st = ST.lookup_student(sid)
        g = self.head(f"Edit murid {sid}", "Perubahan disimpan saat klik Simpan.")
        self.v = {"name": tk.StringVar(value=self.st["name"]),
                  "id": tk.StringVar(value=self.st["id"]),
                  "birth": tk.StringVar(value=self.st.get("birth") or "")}
        self.prog, self.status = self.st["program"], self.st["status"]
        self.label(g, 0, "Nama")
        first = self.entry(g, self.v["name"], on_enter=self._save)
        first.grid(row=0, column=1, sticky="we", pady=4)
        self.label(g, 1, "ID login", "Ganti = semua data ikut pindah")
        self.entry(g, self.v["id"], width=14, on_enter=self._save).grid(row=1, column=1,
                                                                        sticky="w", pady=4)
        self.label(g, 2, "Program", "Dewasa = ID PB, anak = ID SK")
        DP.Seg(g, (("adult", "Dewasa"), ("kids", "SUPERKIDS")), self.prog,
               self._set_prog).grid(row=2, column=1, sticky="w", pady=4)
        self.label(g, 3, "Status akun")
        DP.Seg(g, (("active", "Aktif"), ("expired", "Nonaktif (tidak bisa login)")),
               self.status, lambda v: setattr(self, "status", v)).grid(row=3, column=1,
                                                                        sticky="w", pady=4)
        self.label(g, 4, "Tanggal lahir", "Opsional, untuk umur")
        self.entry(g, self.v["birth"], "YYYY-MM-DD (boleh kosong)", on_enter=self._save).grid(
            row=4, column=1, sticky="we", pady=4)
        self.cbox = tk.Frame(self.body, bg=PANEL)
        self.cbox.pack(fill="x", padx=22, pady=(12, 0))
        self._courses()
        self.footer("Simpan", self._save)
        self.show(first.entry)

    def _set_prog(self, prog):
        self.prog = prog
        self._courses()
        self.fit()

    def _courses(self):
        from elearning.courses import courses_for
        from elearning.ui.widgets import Switch
        for w in self.cbox.winfo_children():
            w.destroy()
        same = self.prog == self.st["program"]
        opened = set(self.st["courses"]) if same else set()
        hidden = set(self.st.get("hidden") or ()) if same else set()
        head = tk.Frame(self.cbox, bg=PANEL)
        head.pack(fill="x")
        tk.Label(head, text="Kursus", bg=PANEL, fg=FG, font=(C.FONT, 11, "bold"),
                 anchor="w").pack(side="left")
        for t in ("Terbuka", "Terlihat"):
            tk.Label(head, text=t, bg=PANEL, fg=MUTED, font=(C.FONT, 9), width=8).pack(
                side="right")
        tk.Label(self.cbox, text="Terlihat = kartu muncul di halaman murid.  Terbuka = bisa "
                             "dipelajari (mati = kartu terkunci).", bg=PANEL, fg=MUTED,
                 font=(C.FONT, 8), anchor="w").pack(fill="x")
        tk.Frame(self.cbox, bg=LINE, height=1).pack(fill="x", pady=(4, 0))
        self.cv_rows = []
        self._dots = []
        for n, c in enumerate(courses_for(self.prog)):
            row = tk.Frame(self.cbox, bg=PANEL)
            row.pack(fill="x", pady=1)
            d = I.dot(c["color"], PANEL, 10, 4.5)
            self._dots.append(d)
            tk.Label(row, image=d, bg=PANEL).pack(side="left", padx=(0, 8))
            tk.Label(row, text=c["title"], bg=PANEL, fg=FG, font=(C.FONT, 10),
                     anchor="w").pack(side="left")
            state = {"open": c["id"] in opened or (not same and n == 0),
                     "show": c["id"] not in hidden}
            for key in ("open", "show"):            # dipasang kanan -> kiri: Buka, Tampil
                Switch(row, state[key], bg=PANEL,
                       command=lambda v, s=state, k=key: s.__setitem__(k, v)).pack(
                    side="right", padx=4, pady=2)
            self.cv_rows.append((c["id"], state))

    def _save(self):
        ST, sid = self.ST, self.st["id"]
        try:
            birth = self.v["birth"].get().strip()
            if birth and not ST._birth_ok(birth):
                raise ValueError("Tanggal lahir harus YYYY-MM-DD, mis. 2012-05-31.")
            if self.prog != self.st["program"]:
                ST.set_program(sid, self.prog)
            ST.bulk_access({sid: ([cid for cid, s in self.cv_rows if s["open"]],
                                  [cid for cid, s in self.cv_rows if not s["show"]])})
            if " ".join(self.v["name"].get().split()) != self.st["name"]:
                ST.rename_student(sid, self.v["name"].get())
            if self.status != self.st["status"]:
                ST.set_status(sid, self.status)
            if birth != (self.st.get("birth") or ""):
                ST.set_birth(sid, birth or None)
            new_id = self.v["id"].get().strip().upper()
            if new_id and new_id != sid:
                ST.change_id(sid, new_id)       # paling akhir: pindahkan semua data
                sid = new_id
        except (ValueError, KeyError) as exc:
            self.error(str(exc).strip("'"))
            return
        except OSError as exc:
            C.log(f"Dev edit murid {sid}: {exc!r}")
            self.error("Gagal menyimpan (folder data?).")
            return
        C.log(f"Dev: murid {self.st['id']} diedit -> {sid}")
        panel, old = self.panel, self.st["id"]
        self.destroy()
        panel.reload_accounts(sid)
        panel._note(f"Tersimpan: {sid}")
        try:
            panel._student_changed(old, sid)         # perubahan langsung terlihat
        except Exception as exc:
            C.log(f"Dev: layar tidak dibangun ulang: {exc!r}")


# --- edit guru / admin ----------------------------------------------------------------------------
class AccountEditor(Card):
    """Nama & PIN guru / admin. Dua-duanya diperiksa dulu; salah satu salah = tidak disimpan."""

    def __init__(self, panel, kind, uid, name):
        super().__init__(panel, 500)
        self.kind, self.uid = kind, uid
        if kind == "admin":
            from elearning import admins
            pin = admins.get_pin(uid)
            name = admins.get_name(uid) or name
        else:
            from elearning import teachers
            pin = teachers.get_pin(uid)
            name = (teachers.get_teacher(uid) or {}).get("name", name)
        self._old = (name, pin or "")
        g = self.head(f"Edit {'admin' if kind == 'admin' else 'guru'} {uid}",
                      "Masuk dengan ID + PIN ini.")
        self.name_var, self.var = tk.StringVar(value=name), tk.StringVar(value=pin or "")
        self.label(g, 0, "Nama")
        first = self.entry(g, self.name_var, on_enter=self._save)
        first.grid(row=0, column=1, sticky="we", pady=4)
        self.label(g, 1, "PIN login", "4-10 karakter, tanpa spasi")
        self.pin_box(g, self.var, self._save).grid(row=1, column=1, sticky="we", pady=4)
        self.footer("Simpan", self._save)
        self.show(first.entry)
        first.entry.select_range(0, "end")

    def _save(self):
        name, pin = " ".join(self.name_var.get().split()), self.var.get()
        if (name, pin) == self._old:
            self.destroy()
            return
        try:
            if self.kind == "admin":
                from elearning import admins
                admins.check_pin_text(pin)                  # periksa dulu, baru simpan
                if not name:
                    raise ValueError("Nama admin belum diisi.")
                if len(name) > admins.NAME_MAX:
                    raise ValueError(f"Nama terlalu panjang (maksimal {admins.NAME_MAX} huruf).")
                if name != self._old[0]:
                    admins.set_name(self.uid, name)
                if pin != self._old[1]:
                    admins.set_pin(self.uid, pin)
            else:
                from elearning import teachers
                teachers._clean_pin(pin)        # kosong = salah, bukan "tetap"
                if teachers.get_teacher(self.uid) is None:
                    raise ValueError(f"Guru {self.uid} tidak ditemukan.")
                teachers.update_teacher(self.uid, name, pin)
        except ValueError as exc:
            self.error(str(exc))
            return
        except OSError as exc:
            C.log(f"Dev: akun {self.uid} gagal disimpan: {exc!r}")
            self.error("Gagal menyimpan (folder data?).")
            return
        C.log(f"Dev: akun {self.uid} diubah (nama / PIN)")
        panel, kind, uid = self.panel, self.kind, self.uid
        self.destroy()
        try:
            panel.reload_accounts(uid)
            panel._note(f"{uid} disimpan.")
            panel.app.dev_account_changed(kind, uid)
        except Exception as exc:
            C.log(f"Dev: setelah ubah {uid}: {exc!r}")


# --- hapus ------------------------------------------------------------------------------------------
class DeleteConfirm(Card):
    """Konfirmasi hapus akun. Tidak bisa dibatalkan setelah Hapus (fokus awal di Batal)."""

    WHAT = {
        "adult": "Akun, foto, progres video, badge, portfolio & assignment, riwayat login, "
                 "jadwal, kuis, dan sertifikat murid ini ikut terhapus.",
        "kids": "Akun, foto, progres video, badge, portfolio & assignment, riwayat login, "
                "jadwal, kuis, dan sertifikat murid ini ikut terhapus.",
        "teacher": "Akun, foto, dan riwayat masuk/keluar guru ini ikut terhapus. Laporan "
                   "kerjanya tetap tersimpan.",
        "admin": "Akun admin ini tidak bisa dipakai login lagi.",
    }

    def __init__(self, panel, kind, uid, name):
        super().__init__(panel, 460)
        self.kind, self.uid = kind, uid
        self.head(f"Hapus akun {uid} ({name})?", self.WHAT.get(kind, "") + " Tidak bisa dikembalikan.")
        _ok, cancel = self.footer("Hapus permanen", self._do, "danger")
        self.show(cancel)                       # Enter tidak langsung menghapus

    def _do(self):
        try:
            if self.kind == "admin":
                from elearning import admins
                admins.delete_admin(self.uid)
            elif self.kind == "teacher":
                from elearning import teachers
                teachers.delete_teacher(self.uid)
            else:
                from elearning import students
                students.delete_student(self.uid)
        except ValueError as exc:
            self.error(str(exc))
            return
        except OSError as exc:
            C.log(f"Dev: hapus {self.uid} gagal: {exc!r}")
            self.error("Gagal menghapus (folder data?).")
            return
        C.log(f"Dev: akun {self.uid} dihapus")
        panel, uid = self.panel, self.uid
        self.destroy()
        try:
            panel.reload_accounts()
            panel._note(f"{uid} dihapus.")
            panel.app.dev_account_deleted(uid)
        except Exception as exc:
            C.log(f"Dev: setelah hapus {uid}: {exc!r}")


# --- reset progres murid ------------------------------------------------------------------------
class StudentPicker(tk.Canvas):
    """Daftar murid bercentang (satu kanvas, digulir roda mouse): klik baris = centang."""

    ROW, ROWS = 30, 8

    def __init__(self, master, students, selected, width, on_change):
        super().__init__(master, width=width, height=self.ROW * self.ROWS, bg=PANEL,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.all = students
        self.sel = set(selected)
        self.Wd, self.on_change = width, on_change
        self.shown, self.top = list(students), 0
        self.f = tkfont.Font(family=C.FONT, size=10)
        self.fm = tkfont.Font(family="Consolas", size=9)
        self._imgs = []
        self.bind("<Button-1>", self._click)
        self.bind("<MouseWheel>", self._wheel)
        self._draw()

    def filter(self, query):
        words = query.lower().split()
        self.shown = [s for s in self.all
                      if all(w in f"{s['id']} {s['name']}".lower() for w in words)]
        self.top = 0
        self._draw()

    def set_shown(self, on):
        ids = {s["id"] for s in self.shown}
        self.sel = (self.sel | ids) if on else (self.sel - ids)
        self._draw()
        self.on_change()

    def _wheel(self, e):
        top = self.top + (-3 if e.delta > 0 else 3)
        self.top = max(0, min(top, len(self.shown) - self.ROWS))
        self._draw()
        return "break"

    def _click(self, e):
        i = self.top + int(e.y // self.ROW)
        if 0 <= i < len(self.shown):
            self.sel ^= {self.shown[i]["id"]}
            self._draw()
            self.on_change()

    def _draw(self):
        self.delete("all")
        self._imgs = []
        bg, R = DP.SEG_BG, self.ROW
        box = I.pill(self.Wd, R * self.ROWS, bg, PANEL, r=8)     # latar daftar bersudut bulat
        if box is not None:
            self._imgs.append(box)
            self.create_image(0, 0, image=box, anchor="nw")
        if not self.shown:
            self.create_text(self.Wd / 2, R * self.ROWS / 2, text="Tidak ada murid yang cocok",
                             fill=MUTED, font=self.f)
        for row, s in enumerate(self.shown[self.top:self.top + self.ROWS]):
            y = row * R + R / 2
            on = s["id"] in self.sel
            fill = C.ACCENT if on else bg
            img = I.pill(18, 18, fill, bg, r=4, border=None if on else "#6d6a62")
            if img is not None:
                self._imgs.append(img)
                self.create_image(12, y - 9, image=img, anchor="nw")
            if on:
                ic = I.icon("check_bold", "#ffffff", fill, 14)
                if ic is not None:
                    self._imgs.append(ic)
                    self.create_image(21, y, image=ic)
            self.create_text(42, y, text=s["id"], anchor="w", fill=MUTED, font=self.fm)
            self.create_text(124, y, text=s["name"], anchor="w", fill=FG if on else "#c9c6bd",
                             font=self.f)
            prog = "SUPERKIDS" if s["program"] == "kids" else "Dewasa"
            if s.get("status") == "expired":
                prog += " · Nonaktif"
            self.create_text(self.Wd - 14, y, text=prog, anchor="e", fill=MUTED, font=self.fm)
        n = len(self.shown)
        if n > self.ROWS:                     # bilah gulir tipis (posisi saja)
            h = R * self.ROWS
            bar = max(24, h * self.ROWS / n)
            y0 = (h - bar) * self.top / max(1, n - self.ROWS)
            img = I.pill(4, bar, "#5a5953", bg, r=2)
            if img is not None:
                self._imgs.append(img)
                self.create_image(self.Wd - 6, y0, image=img, anchor="nw")

    def selected(self):
        return [s["id"] for s in self.all if s["id"] in self.sel]


class ResetProgress(Card):
    """Pilih murid (satu / banyak) + bagian yang di-reset. Tombol Reset harus diklik DUA kali
    (klik pertama = konfirmasi); fokus awal di Batal."""

    def __init__(self, panel, selected=()):
        from elearning import students as ST
        super().__init__(panel, 660)
        self.students = ST.list_students()
        inner = self.W - 44 - LABEL_W - 12
        g = self.head("Reset progres murid",
                      "Akun, ID, kategori, akses kursus, foto, jadwal, dan riwayat login TIDAK "
                      "berubah. Yang di-reset tidak bisa dikembalikan.")
        self.label(g, 0, "Murid", "centang satu atau banyak; cari nama / ID")
        box = tk.Frame(g, bg=PANEL)
        box.grid(row=0, column=1, sticky="we", pady=(6, 4))
        self.q = tk.StringVar()
        self.entry(box, self.q, "Cari murid…", 30).pack(fill="x")
        self.pick = StudentPicker(box, self.students, selected, inner, self._changed)
        self.pick.pack(fill="x", pady=(8, 6))
        row = tk.Frame(box, bg=PANEL)
        row.pack(fill="x")
        self.count = tk.Label(row, text="", bg=PANEL, fg=MUTED, font=(C.FONT, 9), anchor="w")
        self.count.pack(side="left")
        DP._btn(row, "Kosongkan", lambda: self.pick.set_shown(False)).pack(side="right")
        DP._btn(row, "Centang yang tampil", lambda: self.pick.set_shown(True)).pack(
            side="right", padx=(0, 8))
        self.q.trace_add("write", lambda *a: self.pick.filter(self.q.get()))
        self.label(g, 1, "Yang di-reset", "klik untuk menyalakan / mematikan")
        colors = {"video": "#5b9cf5", "badges": "#e8b04a", "certificates": "#4cc38a",
                  "survey": "#a78bfa", "work": "#ff6b6b"}
        self.parts = Chips(g, [(k, lb, colors[k]) for k, lb, _d in ST.RESET_PARTS],
                           [k for k, _l, _d in ST.RESET_PARTS if k != "work"], width=inner)
        self.parts.grid(row=1, column=1, sticky="w", pady=(9, 2))
        self.parts.bind("<Button-1>", lambda e: self.after_idle(self._changed), add="+")
        self.what = tk.Label(g, text="", bg=PANEL, fg=MUTED, font=(C.FONT, 8), anchor="w",
                             justify="left", wraplength=inner)
        self.what.grid(row=2, column=1, sticky="we", pady=(4, 0))
        self.ok, cancel = self.footer("Reset progres", self._do, "danger")
        self._armed = False
        self._changed()
        self.show(cancel)

    def _changed(self):
        from elearning import students as ST
        n = len(self.pick.selected())
        self.count.config(text=f"{n} murid dicentang" if n else "Belum ada murid dicentang")
        parts = self.parts.selected()
        labels = {k: (lb, d) for k, lb, d in ST.RESET_PARTS}
        self.what.config(text="\n".join(f"• {labels[k][0]}: {labels[k][1]}" for k in parts)
                         or "Pilih minimal satu bagian.",
                         fg="#ff8a8a" if "work" in parts else MUTED)
        self._armed = False
        self.ok.config(text=f"Reset {n} murid" if n else "Reset progres")
        if hasattr(self, "msg"):
            self.msg.config(text="", fg=MUTED)
            self.fit()

    def _do(self):
        from elearning import students as ST
        ids, parts = self.pick.selected(), self.parts.selected()
        if not ids:
            self.error("Centang minimal satu murid.")
            return
        if not parts:
            self.error("Pilih minimal satu bagian yang di-reset.")
            return
        if not self._armed:                     # klik pertama = minta konfirmasi
            self._armed = True
            self.ok.config(text=f"Ya, reset {len(ids)} murid")
            self.msg.config(text=f"Klik sekali lagi untuk me-reset {len(ids)} murid. "
                                 "Tidak bisa dikembalikan.", fg="#ff8a8a")
            self.fit()
            return
        done, failed = [], []
        for sid in ids:
            try:
                ST.reset_student(sid, parts)
                done.append(sid)
            except (ValueError, OSError) as exc:
                C.log(f"Dev: reset {sid} gagal: {exc!r}")
                failed.append(sid)
        if done:
            C.log(f"Dev: reset progres {', '.join(done)} ({', '.join(parts)})")
        panel = self.panel
        if failed:
            self._armed = False
            self.error(f"{len(done)} murid di-reset, {len(failed)} gagal: "
                       f"{', '.join(failed[:6])} (folder data bisa ditulis?).")
            return
        self.destroy()
        try:
            panel.reload_accounts()
            panel._note(f"Progres {len(done)} murid di-reset.")
            cur = getattr(panel.app, "_student", None)
            if cur is not None and cur.get("id") in done:       # murid yang sedang login
                panel._student_changed(cur["id"], cur["id"])
        except Exception as exc:
            C.log(f"Dev: setelah reset: {exc!r}")
