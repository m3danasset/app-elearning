"""Layar login: logo brand besar di tengah, kolom login di bawahnya, dan carousel 3D
karya murid yang terus berputar di belakangnya (carousel3d.py).

- Tidak ada tombol Masuk: ketik ID lalu tekan Enter.
- ID guru (GURU...) / admin (ADMIN...): kolom PIN tambahan muncul di bawah kolom ID.
  Enter / Tab / panah bawah = pindah ke PIN; klik kolom untuk memilih; Esc = kembali ke ID.
- Kolom login digambar sebagai gambar transparan + teks canvas (bukan widget Entry),
  jadi kartu carousel tetap terlihat samar di belakangnya, tanpa kotak / bayangan.

Logo diambil dari assets\\logo.png.
"""

import tkinter as tk

from elearning import brand
from elearning import config as C
from elearning import photos
from elearning.admins import check_admin, is_admin_id
from elearning.students import STATUS_EXPIRED, lookup_student
from elearning.teachers import check_teacher, is_teacher_id
from elearning.trial import is_trial_id, trial_student
from elearning.ui import ui_icons as I
from elearning.ui.carousel3d import Carousel3D
from elearning.ui.login_bg import LoginBackground

MAX_LEN = 10          # maks. huruf + angka di kolom ID / PIN (cegah spam tombol)
LOGO_ALPHA = 0.92
FIELD_FILL = 200          # kegelapan isi kolom (0-255)
TEXT = "#f3f1ea"
MUTED = "#aaa79e"
BLINK_MS = 530


class LoginScreen(tk.Frame):
    def __init__(self, master, on_success, on_teacher=None, on_admin=None):
        super().__init__(master, bg=C.LOGIN_BG)
        self.on_success = on_success
        self.on_teacher = on_teacher
        self.on_admin = on_admin
        self.mode = "id"
        self.value = {"id": "", "pin": ""}
        self.message = ""
        self._msg_error = False
        self._imgs = {}
        self._field = None          # kolom aktif (x0, y0, x1, y1)
        self._fields = {}           # "id" / "pin" -> (x0, y0, x1, y1)
        self._pin_shown = False
        self._caret_on = True
        self._blink = None
        self._build()

    # --- susunan ---------------------------------------------------------------------------
    def _build(self):
        self.bgv = LoginBackground(self)
        self.bgv.place(x=0, y=0, relwidth=1, relheight=1)
        cv = self.bgv
        self._t_brand = cv.create_text(0, 0, text="", fill=TEXT, anchor="center")
        # bayangan lembut di bawah teks ID & PIN (gambar RGBA, dibuat sebelum teksnya)
        self._sh = {}
        for name in ("value", "pin", "msg"):
            self._sh[name] = {"item": cv.create_image(0, 0, anchor="center"), "key": None,
                              "img": None}
        self._t_value = cv.create_text(0, 0, text="", fill=MUTED, anchor="center")
        self._t_pin = cv.create_text(0, 0, text="", fill=MUTED, anchor="center")
        self._t_caret = cv.create_line(0, 0, 0, 0, fill=TEXT, width=2)
        self._t_msg_sh = self._sh["msg"]["item"]
        self._t_msg = cv.create_text(0, 0, text="", fill=MUTED, anchor="n", justify="center")

        self.carousel = Carousel3D(cv)
        self.carousel.start()

        top = self.winfo_toplevel()
        top.bind("<Key>", self._on_key)
        top.bind("<KeyRelease>", self._on_key_up)
        self._mods = set()          # Ctrl / Shift yang sedang ditekan (kiri & kanan terpisah)
        cv.bind("<Button-1>", self._on_click)
        cv.bind("<Motion>", self._on_motion)
        cv.focus_set()
        # Dari logout: dialog konfirmasi baru ditutup SETELAH layar ini dibuat, sehingga fokus
        # keyboard hilang (ID tidak bisa diketik). Ambil fokus lagi setelah dialog tertutup.
        for ms in (1, 120, 400):
            self.after(ms, self._grab_focus)
        self._layout_job = None
        self._layout_size = None
        self.bind("<Configure>", self._on_configure)
        self._blink_tick()

    def _on_configure(self, e):
        """Windowed <-> fullscreen memicu banyak <Configure> beruntun: tata letak (render pita,
        reset video) baru dijalankan setelah ukuran stabil, supaya tidak berkedip/patah."""
        if e.widget is not self:
            return
        if self._layout_job is not None:
            self.after_cancel(self._layout_job)
        first = self._layout_size is None
        self._layout_job = self.after(1 if first else 80, self._layout_settled)

    def _layout_settled(self):
        self._layout_job = None
        size = (self.winfo_width(), self.winfo_height())
        if size == self._layout_size:
            return
        self._layout_size = size
        self._layout()

    def _layout(self, _event=None):
        W, H = self.winfo_width(), self.winfo_height()
        if W < 50 or H < 50:
            return
        cv = self.bgv
        cy = H * 0.5
        ch = int(max(200, min(H * 0.49, W * 0.276, 640)))

        # logo besar di tengah (sedikit di atas tengah kartu)
        ly = cy - H * 0.065
        logo = self._logo(int(W * 0.64), int(H * 0.17))
        overlays, extra = [], []
        if logo is not None:
            lx, lt = int(W / 2 - logo.width / 2), int(ly - logo.height / 2)
            overlays.append((logo, lx, lt))
            extra.append((lt, lt + logo.height))
            cv.itemconfigure(self._t_brand, text="")
        else:      # tanpa assets\logo.png: nama brand sebagai teks besar
            cv.itemconfigure(self._t_brand, text=brand.BRAND_NAME,
                             font=(C.SERIF, -int(H * 0.085), "bold"))
            cv.coords(self._t_brand, W / 2, ly)

        # kolom login di bawah logo
        fw = int(min(620, max(320, W * 0.36)))
        fh = int(max(52, min(66, H * 0.064)))
        fx, fy = int(W / 2 - fw / 2), int(cy + H * 0.11 - fh / 2)
        gap = int(fh * 0.22)
        py = fy + fh + gap                       # kolom PIN (khusus guru / admin)
        self._pin_shown = self._needs_pin()
        overlays.append((self._field_img(fw, fh), fx, fy))
        extra.append((fy, py + fh))              # ruang PIN selalu disiapkan: tidak melompat
        self._fields = {"id": (fx, fy, fx + fw, fy + fh), "pin": (fx, py, fx + fw, py + fh)}
        font = (C.FONT, -int(fh * 0.34))
        cv.itemconfigure(self._t_value, font=font)
        cv.coords(self._t_value, W / 2, fy + fh / 2)
        cv.itemconfigure(self._t_pin, font=font)
        cv.coords(self._t_pin, W / 2, py + fh / 2)
        if self._pin_shown:
            overlays.append((self._field_img(fw, fh), fx, py))
        else:
            self.mode = "id"
        self._field = self._fields[self.mode]
        last = py + fh if self._pin_shown else fy + fh
        cv.itemconfigure(self._t_msg, font=(C.FONT, -max(13, int(fh * 0.23))), width=fw)
        cv.coords(self._t_msg, W / 2, last + int(fh * 0.25))

        self.carousel.configure(W, H, cy, ch, overlays, extra)
        self._refresh()
        cv.tag_raise(self._t_brand)
        cv.tag_raise(self._sh["value"]["item"])
        cv.tag_raise(self._sh["pin"]["item"])
        cv.tag_raise(self._t_value)
        cv.tag_raise(self._t_pin)
        cv.tag_raise(self._t_caret)
        cv.tag_raise(self._t_msg_sh)
        cv.tag_raise(self._t_msg)

    def _logo(self, max_w, max_h):
        key = ("logo", max_w, max_h)
        if key in self._imgs:
            return self._imgs[key]
        img = None
        try:
            from PIL import Image
            with Image.open(C.resource_path("assets", "logo.png")) as f:
                src = f.convert("RGBA")
            img = _fit(src, max_w, max_h)
            a = img.getchannel("A").point(lambda v: int(v * LOGO_ALPHA))
            img.putalpha(a)
            img = _soft_shadow(img)
        except Exception:
            img = None
        self._imgs = {k: v for k, v in self._imgs.items() if k[0] != "logo"}
        self._imgs[key] = img
        return img

    def _field_img(self, w, h):
        key = ("field", w, h)
        img = self._imgs.get(key)
        if img is None:
            Image = photos.Image
            r = h // 2 - 2 if h < 60 else 18
            img = Image.new("RGBA", (w, h), (236, 234, 226, 0))
            img.putalpha(I.round_mask(w, h, r).point(lambda v: v * 70 // 255))   # garis tepi
            body = Image.new("RGBA", (w - 2, h - 2), I._rgb(C.LOGIN_BG) + (0,))
            body.putalpha(I.round_mask(w - 2, h - 2, r - 1)
                          .point(lambda v: v * FIELD_FILL // 255))
            img.alpha_composite(body, (1, 1))
            self._imgs = {k: v for k, v in self._imgs.items() if k[0] != "field"}
            self._imgs[key] = img
        return img

    # --- isi kolom ---------------------------------------------------------------------------
    def _refresh(self):
        cv = self.bgv
        if self._fields and self._needs_pin() != self._pin_shown:   # kolom PIN muncul / hilang
            self._layout()
            return
        for name, item, hint in (("id", self._t_value, "Enter Your ID"),
                                 ("pin", self._t_pin, "Enter Your PIN")):
            val = self.value[name]
            if name == "pin" and not self._pin_shown:
                cv.itemconfigure(item, text="")
            elif val:
                cv.itemconfigure(item, text="•" * len(val) if name == "pin" else val, fill=TEXT)
            else:
                cv.itemconfigure(item, text=hint, fill=MUTED)
        self._field = self._fields.get(self.mode, self._field)
        if self.message:
            cv.itemconfigure(self._t_msg, text=self.message,
                             fill=MSG_ERROR if self._msg_error else MUTED)
        else:
            cv.itemconfigure(self._t_msg, text="")
        self._msg_shadow()
        self._place_caret()

    def _msg_shadow(self):
        """Bayangan lembut (kapsul gelap ter-blur, sedikit turun) di bawah teks pesan, ID, dan
        PIN, supaya terbaca di atas carousel / video. Dibuat ulang hanya kalau ukurannya berubah."""
        for name, item in (("msg", self._t_msg), ("value", self._t_value), ("pin", self._t_pin)):
            self._shadow_for(self._sh[name], item,
                             SHADOW_MSG if name == "msg" else SHADOW_FIELD)

    def _shadow_for(self, sh, text_item, alpha):
        cv = self.bgv
        bbox = cv.bbox(text_item) if cv.itemcget(text_item, "text") else None
        if not bbox:
            cv.itemconfigure(sh["item"], image="")
            sh["key"] = None
            return
        x0, y0, x1, y1 = bbox
        w, h = x1 - x0, y1 - y0
        if (w, h) != sh["key"]:
            sh["key"] = (w, h)
            sh["img"] = _text_shadow(w, h, alpha)
        cv.itemconfigure(sh["item"], image=sh["img"] or "")
        cv.coords(sh["item"], (x0 + x1) / 2, (y0 + y1) / 2 + max(2, h // 10))

    def _place_caret(self):
        cv = self.bgv
        if not self._field:
            return
        x0, y0, x1, y1 = self._field
        fh = y1 - y0
        item = self._t_pin if self.mode == "pin" else self._t_value
        if self.value[self.mode]:
            bb = cv.bbox(item)
            x = (bb[2] + 2) if bb else (x0 + x1) / 2
        else:          # kosong: kursor di depan tulisan petunjuk
            bb = cv.bbox(item)
            x = (bb[0] - 4) if bb else (x0 + x1) / 2
        x = int(x) + 0.5
        cv.coords(self._t_caret, x, y0 + fh * 0.3, x, y1 - fh * 0.3)
        focused = self.focus_displayof() is not None
        cv.itemconfigure(self._t_caret, state="normal" if (self._caret_on and focused)
                         else "hidden")

    def _blink_tick(self):
        self._caret_on = not self._caret_on
        try:
            self._place_caret()
        except tk.TclError:
            return
        self._blink = self.after(BLINK_MS, self._blink_tick)

    def _type(self, text):
        val = self.value[self.mode]
        text = "".join(ch for ch in text if ch.isprintable() and not ch.isspace())
        if not text:
            return
        self.value[self.mode] = (val + text)[:MAX_LEN]
        self._set_message("")

    def _set_message(self, text, error=False):
        self.message, self._msg_error = text, error
        self._caret_on = True
        self._refresh()

    def _wake(self):
        import time
        self.carousel.last_input = time.perf_counter()

    _MODS = ("Control_L", "Control_R", "Shift_L", "Shift_R")

    def _on_key_up(self, e):
        self._mods.discard(e.keysym)

    def _dev_bypass(self):
        """Ctrl KANAN + Shift KANAN + Backspace: jendela Dev dibuka oleh shortcut global
        (ui/dev_panel.install_shortcut); di sini Backspace-nya hanya tidak menghapus huruf."""
        from elearning.ui.dev_panel import dev_combo
        return dev_combo()

    def _dev_login(self, kind, account):
        if not self.winfo_exists() or account is None:
            return
        C.log(f"Dev bypass login: {kind} {account.get('id', '')}")
        if kind == "admin" and self.on_admin is not None:
            self.on_admin(account)
        elif kind == "teacher" and self.on_teacher is not None:
            self.on_teacher(account)
        elif kind in ("adult", "kids", "trial"):
            self.on_success(account)
        else:
            self._grab_focus()

    def _on_key(self, e):
        self._wake()
        ks = e.keysym
        if ks in self._MODS:
            self._mods.add(ks)
            return
        if ks == "BackSpace" and self._dev_bypass():
            return
        ctrl = bool(e.state & 0x4)
        if ks in ("Return", "KP_Enter"):
            self.do_login()
        elif ks == "BackSpace":
            if ctrl:
                self.value[self.mode] = ""
            else:
                self.value[self.mode] = self.value[self.mode][:-1]
            self._set_message("")
        elif ks in ("Tab", "ISO_Left_Tab", "Down", "Up"):
            if self._pin_shown:
                self.mode = "pin" if (self.mode == "id" and ks in ("Tab", "Down")) else "id"
                self._set_message("")
        elif ks == "Escape":
            if self.mode == "pin":
                self.mode = "id"
                self.value["pin"] = ""
            else:
                self.value["id"] = ""
            self._set_message("")
        elif ctrl and ks.lower() == "v":
            try:
                self._type(self.clipboard_get())
            except tk.TclError:
                pass
        elif ctrl:
            return None
        elif e.char and len(e.char) == 1 and e.char.isprintable():
            self._type(e.char)
        else:
            return None
        return "break"

    def _field_at(self, x, y):
        for name, f in self._fields.items():
            if name == "pin" and not self._pin_shown:
                continue
            if f[0] <= x <= f[2] and f[1] <= y <= f[3]:
                return name
        return None

    def _needs_pin(self):
        sid = self.value["id"].strip()
        return bool(sid) and (is_teacher_id(sid) or is_admin_id(sid))

    def _grab_focus(self):
        try:
            if not self.winfo_exists():
                return
            top = self.winfo_toplevel()
            if top.focus_get() is not self.bgv:
                top.focus_force()
                self.bgv.focus_set()
        except Exception:
            pass

    def _on_click(self, e):
        self.bgv.focus_set()
        name = self._field_at(e.x, e.y)
        if name and name != self.mode:
            self.mode = name
            self._set_message("")

    def _on_motion(self, e):
        self._wake()
        on = self._field_at(e.x, e.y) is not None
        self.bgv.config(cursor="xterm" if on else "")

    def destroy(self):
        if self._layout_job is not None:
            try:
                self.after_cancel(self._layout_job)
            except Exception:
                pass
            self._layout_job = None
        try:
            self.carousel.close()
        except Exception:
            pass
        if self._blink is not None:
            try:
                self.after_cancel(self._blink)
            except Exception:
                pass
        try:
            self.winfo_toplevel().unbind("<Key>")
            self.winfo_toplevel().unbind("<KeyRelease>")
        except Exception:
            pass
        tk.Frame.destroy(self)

    # --- masuk -------------------------------------------------------------------------------
    def _login_trial(self):
        self._set_message("")
        self.on_success(trial_student())

    def do_login(self):
        sid = self.value["id"].strip()
        if not sid:
            self.mode = "id"
            self._set_message("ID belum diisi.", True)
            return

        if is_admin_id(sid) or is_teacher_id(sid):
            pin = self.value["pin"]
            if not pin and self.mode != "pin":   # Enter di kolom ID: pindah ke kolom PIN
                self.mode = "pin"
                self._set_message("")
                return
            if not pin:
                self._set_message("Masukkan PIN.", True)
                return
            if is_admin_id(sid):
                account, handler = check_admin(sid, pin), self.on_admin
            else:
                account, handler = check_teacher(sid, pin), self.on_teacher
            if account is None:
                self.value["pin"] = ""
                self.mode = "pin"
                self._set_message("ID atau PIN salah.", True)
                return
            if handler is not None:
                handler(account)
            return

        if is_trial_id(sid):   # calon murid: tanpa PIN, langsung pilih ANIMATION / MODELING
            self._login_trial()
            return

        student = lookup_student(sid)
        if student is None:
            self._set_message("ID tidak ditemukan. Cek lagi atau tanya guru.", True)
            return
        if student.get("status") == STATUS_EXPIRED:
            self._set_message(
                "Akun kamu sudah expired. Hubungi guru untuk mengaktifkan kembali.", True)
            return
        self._set_message("")
        self.on_success(student)


MSG_ERROR = "#ff2e2e"      # pesan salah ID / PIN: merah menyala (lebih jenuh dari C.ERROR)


SHADOW_MSG, SHADOW_FIELD = 130, 91   # kepekatan bayangan: pesan / teks ID & PIN (30% lebih tipis)


def _text_shadow(w, h, alpha=SHADOW_MSG):
    """PhotoImage RGBA: kapsul gelap ter-blur seukuran teks (blur lewat perkecil-perbesar,
    tanpa ImageFilter / ImageDraw)."""
    try:
        from PIL import Image
        from elearning import photos
        blur = max(6, h // 2)
        pad = blur * 2
        W, H = w + 2 * pad, h + 2 * pad
        a = Image.new("L", (W, H), 0)
        a.paste(alpha, (pad - 4, pad + 2, pad + w + 4, pad + h - 2))
        small = a.resize((max(1, W // blur), max(1, H // blur)), Image.BILINEAR)
        a = small.resize((W, H), Image.BICUBIC)
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.putalpha(a)
        return photos.to_photoimage(out)
    except Exception as exc:
        C.log(f"Bayangan pesan login gagal: {exc!r}")
        return None


def _soft_shadow(img):
    """Bayangan lembut di bawah logo (blur lewat perkecil-perbesar, tanpa ImageFilter)."""
    from PIL import Image
    w, h = img.size
    blur = max(6, int(h * 0.09))           # jari-jari blur
    dy = max(3, int(h * 0.035))            # bayangan sedikit turun
    pad = blur * 2
    W, H = w + 2 * pad, h + 2 * pad + dy
    a = Image.new("L", (W, H), 0)
    a.paste(img.getchannel("A"), (pad, pad + dy))
    small = a.resize((max(1, W // blur), max(1, H // blur)), Image.BILINEAR)
    a = small.resize((W, H), Image.BICUBIC).point(lambda v: v * 115 // 255)   # ~45% gelap
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.putalpha(a)
    out.alpha_composite(img, (pad, pad))
    return out


def _fit(img, max_w, max_h):
    from PIL import Image
    bbox = img.getchannel("A").getbbox()
    if bbox:
        img = img.crop(bbox)
    scale = min(max_w / img.width, max_h / img.height, 1.0)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    try:
        return img.convert("RGBa").resize(size, resample).convert("RGBA")
    except Exception:
        return img.resize(size, resample)
