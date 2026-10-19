"""Tombol dan kolom isian bersudut bulat (gaya claude.ai), dipakai di semua layar & dialog.

RoundButton  : pengganti langsung tk.Button. Menerima opsi yang sama (text, command, bg, fg,
               activebackground, activeforeground, disabledforeground, font, padx, pady,
               state) dan .config()/.cget() yang sama, jadi kode lama (mis. add_hover,
               tombol tab yang diwarnai ulang) tetap jalan tanpa diubah.
RoundEntry   : kolom isian bersudut bulat dengan placeholder; widget Entry-nya ada di .entry
dark_titlebar: bilah judul jendela Windows ikut gelap (Windows 10 20H1+ / Windows 11)

Semua gambar sudut dibuat dengan ui_icons.pill (matematika murni, tanpa ImageDraw).
"""

import sys
import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning.ui import ui_icons as I


def _parent_bg(master, default=C.BG):
    try:
        return master.cget("bg")
    except Exception:
        return default


def dark_titlebar(win):
    """Bilah judul gelap di Windows. Diam-diam diabaikan di sistem lain / versi lama."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        value = ctypes.c_int(1)
        for attr in (20, 19):   # DWMWA_USE_IMMERSIVE_DARK_MODE (baru, lalu versi lama)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        try:   # Windows 11: warna bilah judul sama dengan latar sidebar
            rgb = I._rgb(C.SIDEBAR)
            colorref = ctypes.c_int(rgb[0] | (rgb[1] << 8) | (rgb[2] << 16))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref),
                                                       ctypes.sizeof(colorref))
        except Exception:
            pass
    except Exception as exc:
        C.log(f"Bilah judul gelap gagal: {exc!r}")


class RoundButton(tk.Canvas):
    """Tombol bersudut bulat. Lihat keterangan modul."""

    _OPTS = ("text", "command", "bg", "background", "fg", "foreground", "activebackground",
             "activeforeground", "disabledforeground", "font", "padx", "pady", "state",
             "radius", "border", "icon")
    _IGNORED = ("relief", "bd", "borderwidth", "highlightthickness", "anchor", "justify",
                "overrelief", "takefocus", "default", "compound", "underline", "wraplength")

    def __init__(self, master, text="", command=None, bg=C.CARD, fg=C.TEXT,
                 activebackground=None, activeforeground=None, disabledforeground=C.LOCKED,
                 font=None, padx=14, pady=6, state="normal", radius=9, border="auto",
                 icon=None, cursor="hand2", width=None, **_ignored):
        self._pbg = _parent_bg(master)
        self._text, self._command = text, command
        self._bg, self._fg = bg, fg
        self._abg, self._afg, self._dfg = activebackground, activeforeground, disabledforeground
        self._font = tkfont.Font(font=font or (C.FONT, 10))
        self._padx, self._pady = int(padx), int(pady)
        self._state, self._radius, self._border, self._icon = state, radius, border, icon
        self._cursor = cursor
        self._hover = self._pressed = False
        self._imgs = []
        w, h = self._natural()
        super().__init__(master, width=w, height=h, bg=self._pbg, highlightthickness=0,
                         bd=0, cursor=cursor if state != "disabled" else "arrow",
                         takefocus=1)
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<space>", lambda e: self.invoke())

    # --- ukuran & gambar ------------------------------------------------------------
    def _natural(self):
        icon_w = 22 if self._icon else 0
        w = self._font.measure(self._text) + 2 * self._padx + icon_w
        h = self._font.metrics("linespace") + 2 * self._pady
        return max(w, 2 * self._padx), h

    def _colors(self):
        if self._state == "disabled":
            return self._bg, self._dfg
        fill = self._bg
        fg = self._fg
        if self._hover and self._abg:
            fill = self._abg
            fg = self._afg or self._fg
        return fill, fg

    def _draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            w, h = int(super().cget("width")), int(super().cget("height"))
        self.delete("all")
        self._imgs = []
        fill, fg = self._colors()
        border = self._border
        if border == "auto":   # tombol yang warnanya sama dengan latar: beri garis tepi tipis
            border = C.BORDER if fill.lower() == self._pbg.lower() else None
        r = min(self._radius, h / 2.0)
        if fill.lower() != self._pbg.lower() or border:
            p = I.pill(w, h, fill, self._pbg, r=r, border=border)
            if p is not None:
                self._imgs.append(p)
                self.create_image(0, 0, image=p, anchor="nw")
            else:
                self.create_rectangle(0, 0, w, h, fill=fill, outline=border or fill)
        tw = self._font.measure(self._text)
        x = (w - tw - (22 if self._icon else 0)) / 2
        if self._icon:
            ph = I.icon(self._icon, fg, fill, 16)
            if ph is not None:
                self._imgs.append(ph)
                self.create_image(x + 8, h / 2, image=ph)
            x += 22
        self.create_text(x, h / 2 + (1 if self._pressed else 0), text=self._text, anchor="w",
                         fill=fg, font=self._font)

    # --- interaksi --------------------------------------------------------------------
    def _enter(self, _e):
        self._hover = True
        self._draw()

    def _leave(self, _e):
        self._hover = self._pressed = False
        self._draw()

    def _press(self, _e):
        if self._state == "disabled":
            return
        self._pressed = True
        self._draw()

    def _release(self, e):
        was = self._pressed
        self._pressed = False
        self._draw()
        if was and 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self.invoke()

    def invoke(self):
        if self._state != "disabled" and self._command is not None:
            return self._command()

    # --- kompatibel dengan tk.Button -----------------------------------------------------
    def configure(self, cnf=None, **kw):
        if cnf:
            kw = {**cnf, **kw}
        if not kw:
            return super().configure()
        resize = False
        rest = {}
        for k, v in kw.items():
            if k == "text":
                self._text, resize = str(v), True
            elif k == "command":
                self._command = v
            elif k in ("bg", "background"):
                self._bg = v
            elif k in ("fg", "foreground"):
                self._fg = v
            elif k == "activebackground":
                self._abg = v
            elif k == "activeforeground":
                self._afg = v
            elif k == "disabledforeground":
                self._dfg = v
            elif k == "font":
                self._font = tkfont.Font(font=v)
                resize = True
            elif k == "padx":
                self._padx, resize = int(v), True
            elif k == "pady":
                self._pady, resize = int(v), True
            elif k == "state":
                self._state = v
                rest["cursor"] = "arrow" if v == "disabled" else self._cursor
            elif k == "cursor":
                self._cursor = v
                if self._state != "disabled":
                    rest["cursor"] = v
            elif k in self._IGNORED:
                pass
            else:
                rest[k] = v
        if resize:
            w, h = self._natural()
            rest.update(width=w, height=h)
        if rest:
            super().configure(**rest)
        self._draw()

    config = configure

    def cget(self, key):
        table = {"text": self._text, "state": self._state, "bg": self._bg,
                 "background": self._bg, "fg": self._fg, "foreground": self._fg,
                 "activebackground": self._abg, "command": self._command}
        if key in table:
            return table[key]
        return super().cget(key)

    def __getitem__(self, key):
        return self.cget(key)

    def __setitem__(self, key, value):
        self.configure({key: value})


class RoundEntry(tk.Canvas):
    """Kolom isian bersudut bulat. Widget Entry ada di .entry (untuk focus_set, bind, dst)."""

    FOCUS_BORDER = "#77756e"

    def __init__(self, master, textvariable=None, show=None, placeholder="", width_chars=28,
                 font=None, height=42, fill=None, radius=10, icon=None, right_pad=0):
        self._pbg = _parent_bg(master)
        self._right_pad = right_pad     # ruang di kanan dalam kolom (mis. penghitung kata)
        self._right = None
        self._fill = fill or C.SEARCH_BG
        self._radius, self._icon = radius, icon
        self._font = tkfont.Font(font=font or (C.FONT, 11))
        width = self._font.measure("0") * width_chars + 28
        super().__init__(master, width=width, height=height, bg=self._pbg,
                         highlightthickness=0, bd=0, cursor="xterm")
        self._imgs = []
        self.focused = False
        self.var = textvariable if textvariable is not None else tk.StringVar()
        e = self.entry = tk.Entry(self, textvariable=self.var, bg=self._fill, fg=C.TEXT,
                                  insertbackground=C.TEXT, relief="flat", bd=0,
                                  highlightthickness=0, font=self._font,
                                  disabledbackground=self._fill)
        if show:
            e.config(show=show)
        self._x0 = 40 if icon else 14
        self._win = self.create_window(self._x0, height / 2, anchor="w", window=e)
        self.ph = tk.Label(e, text=placeholder, bg=self._fill, fg=C.MUTED, font=self._font,
                           cursor="xterm", bd=0, padx=0)
        self.ph.bind("<Button-1>", lambda ev: e.focus_set())
        e.bind("<FocusIn>", lambda ev: self._set_focus(True), add="+")
        e.bind("<FocusOut>", lambda ev: self._set_focus(False), add="+")
        self.bind("<Button-1>", lambda ev: e.focus_set())
        self.bind("<Configure>", lambda ev: self._draw())
        self.var.trace_add("write", lambda *a: self._placeholder())
        self._placeholder()

    def _placeholder(self):
        try:
            if self.var.get():
                self.ph.place_forget()
            else:
                self.ph.place(x=1, rely=0.5, anchor="w")
        except tk.TclError:
            pass

    def _set_focus(self, on):
        self.focused = on
        self._draw()

    def _draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        self.delete("deco")
        self._imgs = []
        border = self.FOCUS_BORDER if self.focused else C.BORDER
        p = I.pill(w, h, self._fill, self._pbg, r=self._radius, border=border)
        if p is not None:
            self._imgs.append(p)
            self.create_image(0, 0, image=p, anchor="nw", tags="deco")
        if self._icon:
            ic = I.icon(self._icon, C.MUTED, self._fill, 18)
            if ic is not None:
                self._imgs.append(ic)
                self.create_image(22, h / 2, image=ic, tags="deco")
        self.tag_lower("deco")
        self.coords(self._win, self._x0, h / 2)
        self.itemconfigure(self._win, width=max(20, w - self._x0 - 14 - self._right_pad))
        if self._right is not None:
            self.coords(self._right, w - 14, h / 2)

    def set_right_text(self, text, color=C.MUTED, font=None):
        """Teks kecil di dalam kolom, rata kanan (mis. '12/30 kata')."""
        if self._right is None:
            self._right = self.create_text(self.winfo_width() - 14, self.winfo_height() / 2,
                                           anchor="e", text="", font=font or (C.FONT, 9))
        self.itemconfigure(self._right, text=text, fill=color)
        f = tkfont.Font(font=font or (C.FONT, 9))
        self._right_pad = f.measure(text) + 16 if text else 0   # isian tidak menabrak teks
        w = self.winfo_width()
        if w > 10:
            self.itemconfigure(self._win, width=max(20, w - self._x0 - 14 - self._right_pad))

    # pintasan supaya bisa dipakai seperti Entry
    def focus_set(self):
        self.entry.focus_set()

    def get(self):
        return self.var.get()


class RoundCard(tk.Canvas):
    """Kartu bersudut bulat bergaris tepi. Isi diletakkan di .inner (Frame).
    Tinggi kartu mengikuti isinya (mis. kolom PIN yang muncul / hilang)."""

    def __init__(self, master, width=420, fill=None, border=C.BORDER, radius=20, pad=28):
        self._pbg = _parent_bg(master)
        self._fill = fill or self._pbg
        self._border, self._radius, self._pad = border, radius, pad
        super().__init__(master, width=width, height=100, bg=self._pbg, highlightthickness=0,
                         bd=0)
        self._img = None
        self.inner = tk.Frame(self, bg=self._fill)
        self._win = self.create_window(pad, pad, anchor="nw", window=self.inner,
                                       width=width - 2 * pad)
        self.inner.bind("<Configure>", lambda e: self._fit())

    def _fit(self):
        h = self.inner.winfo_reqheight() + 2 * self._pad
        w = int(self.cget("width"))
        if int(self.cget("height")) != h:
            self.configure(height=h)
        self.delete("bg")
        self._img = I.pill(w, h, self._fill, self._pbg, r=self._radius, border=self._border)
        if self._img is not None:
            self.create_image(0, 0, image=self._img, anchor="nw", tags="bg")
            self.tag_lower("bg")


class RoundPanel(tk.Canvas):
    """Kartu bersudut bulat (pengganti Frame bergaris tepi persegi). Isi diletakkan di .inner.

    - Lebar mengikuti induk (pack(fill="x") / grid sticky), atau fit_width=True: selebar isi.
    - Tinggi mengikuti isi; stretch=True: isi ikut ditarik setinggi kartu (mis. kartu kursus
      di grid yang barisnya dibagi rata).
    - stripe="#warna": garis warna membulat di sisi kiri (warna kursus / jenis laporan).
    - set_style(fill=..., border=...): ganti warna (efek hover).
    """

    def __init__(self, master, fill=C.CARD, border=C.BORDER, radius=12, padx=14, pady=10,
                 stripe=None, stretch=False, fit_width=False):
        self._pbg = _parent_bg(master)
        self._fill, self._border, self._radius = fill, border, radius
        self._padx, self._pady, self._stripe = padx, pady, stripe
        self._stretch, self._fit = stretch, fit_width
        self._x0 = padx + (12 if stripe else 0)
        super().__init__(master, width=40, height=40, bg=self._pbg, highlightthickness=0, bd=0)
        self._imgs = []
        self.inner = tk.Frame(self, bg=fill)
        self._win = self.create_window(self._x0, pady, anchor="nw", window=self.inner)
        self.inner.bind("<Configure>", lambda e: self._fit_size(), add="+")
        self._job = None
        self._drawn = None
        self.bind("<Configure>", lambda e: self._schedule())

    def _schedule(self):
        """Ukuran berubah: gambar LANGSUNG (supaya tidak ada sisa gambar lama / bayangan saat
        jendela dibesarkan), lalu sekali lagi setelah ukuran berhenti berubah (saat digeser)."""
        if self._job is None:
            self._draw()
        else:
            self.after_cancel(self._job)
        self._job = self.after(40, self._settle)

    def _settle(self):
        self._job = None
        self._draw()

    def _fit_size(self):
        want_h = self.inner.winfo_reqheight() + 2 * self._pady
        kw = {}
        if int(super().cget("height")) != want_h:
            kw["height"] = want_h
        if self._fit:
            want_w = self.inner.winfo_reqwidth() + self._x0 + self._padx
            if int(super().cget("width")) != want_w:
                kw["width"] = want_w
        if kw:
            super().configure(**kw)

    def _draw(self, force=False):
        self._job = None
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:
            return
        if not force and self._drawn == (w, h, self._fill, self._border):
            return
        self._drawn = (w, h, self._fill, self._border)
        if not self._fit:
            self.itemconfigure(self._win, width=max(10, w - self._x0 - self._padx))
        if self._stretch:
            self.itemconfigure(self._win, height=max(self.inner.winfo_reqheight(),
                                                     h - 2 * self._pady))
        self.delete("bg")
        self._imgs = []
        p = I.pill(w, h, self._fill, self._pbg, r=self._radius, border=self._border)
        if p is not None:
            self._imgs.append(p)
            self.create_image(0, 0, image=p, anchor="nw", tags="bg")
        if self._stripe:
            sh = max(8, h - 2 * self._pady)
            s = I.pill(4, sh, self._stripe, self._fill, r=2)
            if s is not None:
                self._imgs.append(s)
                self.create_image(self._padx, self._pady, image=s, anchor="nw", tags="bg")
        self.tag_lower("bg")

    def set_style(self, fill=None, border=None):
        if fill is not None:
            self._fill = fill
        if border is not None:
            self._border = border
        self._draw(force=True)


class RoundSelect(RoundButton):
    """Pengganti tk.OptionMenu bersudut bulat. select["menu"] = tk.Menu (bisa diisi ulang)."""

    def __init__(self, master, variable, *values, command=None, bg=C.CARD, font=None,
                 width_chars=None):
        self._var = variable
        self._cmd = command
        super().__init__(master, text=self._label(), command=self._post, bg=bg, fg=C.TEXT,
                         activebackground=C.CARD_HOVER, font=font or (C.FONT, 10),
                         padx=14, pady=6, icon=None)
        self.menu = tk.Menu(self, tearoff=0, bg=C.CARD, fg=C.TEXT, activebackground=C.ACCENT,
                            activeforeground="white", font=font or (C.FONT, 10), bd=0)
        for v in values:
            self.menu.add_command(label=v, command=lambda v=v: self._choose(v))
        variable.trace_add("write", lambda *a: self.configure(text=self._label()))

    def _label(self):
        return f"{self._var.get()}   ▾"

    def _choose(self, value):
        self._var.set(value)
        if self._cmd is not None:
            self._cmd(value)

    def _post(self):
        try:
            self.menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + 4)
        finally:
            self.menu.grab_release()

    def cget(self, key):
        if key == "menu":
            return self.menu
        return super().cget(key)


class RoundCheck(tk.Canvas):
    """Kotak centang bersudut bulat sesuai tema (klik kotak atau teksnya)."""

    BOX = 18

    def __init__(self, master, text, value=True, command=None, bg=C.CARD, font=None,
                 sub=None):
        self._font = font or (C.FONT, 10)
        self.sub = sub      # teks kecil abu-abu di belakang label (mis. "terkunci")
        f = tkfont.Font(font=self._font)
        w = self.BOX + 10 + f.measure(text) + (f.measure("  " + sub) if sub else 0) + 4
        self._bg = bg
        super().__init__(master, width=w, height=self.BOX + 6, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.text, self.value, self.command = text, bool(value), command
        self._hover = False
        self._img = None
        self.bind("<Button-1>", lambda e: self.set(not self.value, notify=True))
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self._draw()

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    def set(self, value, notify=False):
        self.value = bool(value)
        self._draw()
        if notify and self.command is not None:
            self.command()

    def _draw(self):
        self.delete("all")
        b, y0 = self.BOX, 3
        if self.value:
            fill, border = (C.ACCENT_HOVER if self._hover else C.ACCENT), None
        else:
            fill, border = (C.CARD_HOVER if self._hover else self._bg), C.MUTED
        self._img = I.pill(b, b, fill, self._bg, r=5, border=border)
        if self._img is not None:
            self.create_image(0, y0, image=self._img, anchor="nw")
        if self.value:     # centang halus (anti-alias), di dalam kotak membulat
            ck = I.icon("check_bold", "#ffffff", fill, b - 4)
            if ck is not None:
                self._ck = ck
                self.create_image(2, y0 + 2, image=ck, anchor="nw")
            else:
                self.create_line(4.5, y0 + 9.5, 7.8, y0 + 12.8, 13.8, y0 + 5.6, fill="white",
                                 width=2, capstyle="round", joinstyle="round")
        t = self.create_text(b + 10, y0 + b / 2, text=self.text, anchor="w", font=self._font,
                             fill=C.TEXT if self.value else C.MUTED)
        if self.sub:
            x1 = self.bbox(t)[2]
            self.create_text(x1 + 6, y0 + b / 2, text=self.sub, anchor="w", font=(C.FONT, 8),
                             fill=C.LOCKED)


class ResizeCurtain:
    """Tirai polos di atas sebuah area SELAMA jendela berubah ukuran (jendela <-> layar penuh).

    Di Windows, saat ukuran berubah, puluhan widget digambar ulang satu per satu; bagian
    yang belum selesai tampak terpotong atau hitam. Tirai menutupi proses itu, lalu diangkat
    setelah semuanya sudah tergambar di ukuran baru, jadi yang terlihat hanya hasil akhirnya.
    """

    SETTLE_MS = 140

    def __init__(self, widget, bg=C.BG, skip=None):
        self.widget = widget
        self.skip = skip   # fungsi -> True: jangan pasang tirai (mis. halaman video)
        self.cover = tk.Frame(widget, bg=bg, bd=0, highlightthickness=0)
        self._size = None
        self._job = None
        widget.bind("<Configure>", self._on_configure, add="+")

    def _on_configure(self, e):
        if e.widget is not self.widget:
            return
        size = (e.width, e.height)   # ukuran jendela utama (tetap, diatur WM): lebar ATAU tinggi
        if self._size is None:           # ukuran pertama: tidak perlu tirai
            self._size = size
            return
        if size == self._size:
            return
        self._size = size
        try:   # search palette (Ctrl+K) langsung ditutup: tidak tertinggal di posisi lama
            from elearning.ui.search_palette import close_palette
            close_palette()
        except Exception:
            pass
        if self.skip is not None and self.skip():
            return
        if not self.cover.winfo_ismapped():
            self.cover.place(x=0, y=0, relwidth=1, relheight=1)
            self.cover.lift()
        if self._job is not None:
            self.widget.after_cancel(self._job)
        self._job = self.widget.after(self.SETTLE_MS, self._lift)

    def _lift(self):
        self._job = None
        try:
            self.widget.update_idletasks()   # semua sudah tergambar di ukuran baru (di balik tirai)
        except tk.TclError:
            return
        # Grafik menggambar ulang sesaat setelah ukuran berhenti berubah: tunggu sekali lagi
        self._job = self.widget.after(60, self._hide)

    def _hide(self):
        self._job = None
        try:
            self.widget.update_idletasks()
            self.cover.place_forget()
        except tk.TclError:
            pass


class WheelPicker(tk.Canvas):
    """Pilihan angka / teks TANPA menu turun: gulir roda mouse di atasnya untuk mengganti
    (atas = berikutnya, bawah = sebelumnya). Panah atas/bawah juga bisa setelah diklik.
    Kotak bersudut bulat (antialias), tepi oranye saat kursor di atasnya; nilai sebelum &
    sesudah tampil samar di kiri-kanan sebagai petunjuk bahwa bisa digulir."""

    H = 34

    def __init__(self, master, variable, values, width=None, bg=C.CARD, fill=C.BG,
                 font=None, command=None):
        self.values = [str(v) for v in values]
        self._var, self._cmd = variable, command
        self._font = tkfont.Font(font=font or (C.FONT, 10))
        self._small = tkfont.Font(font=(C.FONT, 8))
        longest = max(self._font.measure(v) for v in self.values)
        side = max(self._small.measure(v) for v in self.values)
        self.W = width or int(longest + 2 * side + 44)
        super().__init__(master, width=self.W, height=self.H, bg=bg, highlightthickness=0,
                         bd=0, cursor="sb_v_double_arrow", takefocus=1)
        self._bg, self._fill = bg, fill
        self._hover = self._focus = False
        self._acc = 0
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False))
        self.bind("<Button-1>", lambda e: self.focus_set())
        self.bind("<FocusIn>", lambda e: self._set(focus=True))
        self.bind("<FocusOut>", lambda e: self._set(focus=False))
        self.bind("<Up>", lambda e: self.step(1))
        self.bind("<Down>", lambda e: self.step(-1))
        variable.trace_add("write", lambda *a: self._draw())
        self._draw()

    def _index(self):
        try:
            return self.values.index(str(self._var.get()))
        except ValueError:
            return 0

    def step(self, n):
        i = max(0, min(len(self.values) - 1, self._index() + n))
        if self.values[i] != str(self._var.get()):
            self._var.set(self.values[i])
            if self._cmd is not None:
                self._cmd(self.values[i])
        return "break"

    def _on_wheel(self, e):
        self._acc += e.delta                   # touchpad: delta kecil dikumpulkan dulu
        n = int(self._acc / 120)
        if n:
            self._acc -= n * 120
            self.step(n)
        return "break"                         # jangan ikut menggulir area di belakangnya

    def _set(self, hover=None, focus=None):
        if hover is not None:
            self._hover = hover
        if focus is not None:
            self._focus = focus
        self._draw()

    def _draw(self):
        from elearning.ui import ui_icons as I
        self.delete("all")
        ring = C.ACCENT if (self._hover or self._focus) else None
        ph = I.pill(self.W, self.H, self._fill, self._bg, r=8, border=ring)
        if ph is not None:
            self._ph = ph
            self.create_image(0, 0, image=ph, anchor="nw")
        i = self._index()
        cy = self.H / 2
        self.create_text(self.W / 2, cy, text=self.values[i], fill=C.TEXT, font=self._font)
        if i > 0:
            self.create_text(9, cy, text=self.values[i - 1], anchor="w", fill=C.LOCKED,
                             font=self._small)
        if i < len(self.values) - 1:
            self.create_text(self.W - 9, cy, text=self.values[i + 1], anchor="e",
                             fill=C.LOCKED, font=self._small)
