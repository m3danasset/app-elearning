"""Komponen kecil yang dipakai di beberapa layar."""

import tkinter as tk

from elearning import config as C


def add_hover(button, normal, hover):
    """Ubah warna tombol saat kursor di atasnya."""
    button.bind("<Enter>", lambda e: button.config(bg=hover))
    button.bind("<Leave>", lambda e: button.config(bg=normal))


class Switch(tk.Canvas):
    """Tombol geser ON/OFF.

    command(nilai_baru) dipanggil saat diklik; kalau mengembalikan False,
    tombol tidak berpindah (misalnya karena gagal menyimpan).
    """

    W, H = 56, 30

    def __init__(self, master, value=False, command=None, bg=C.CARD):
        super().__init__(master, width=self.W, height=self.H, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.value = bool(value)
        self.command = command
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def set(self, value):
        self.value = bool(value)
        self._draw()

    def _on_click(self, _event=None):
        new = not self.value
        if self.command is not None and self.command(new) is False:
            return
        self.set(new)

    def _draw(self):
        self.delete("all")
        w, h, pad = self.W, self.H, 3
        r = h // 2
        color = C.ON if self.value else C.TRACK_OFF
        self.create_oval(0, 0, h, h, fill=color, outline=color)
        self.create_oval(w - h, 0, w, h, fill=color, outline=color)
        self.create_rectangle(r, 0, w - r, h, fill=color, outline=color)
        x = w - h + pad if self.value else pad
        self.create_oval(x, pad, x + h - 2 * pad, h - pad,
                         fill="white", outline="white")


class DarkScrollbar(tk.Canvas):
    """Scrollbar gelap buatan sendiri (tanpa modul tambahan, supaya aman di dalam .exe)."""

    W = 10
    MIN_THUMB = 28

    def __init__(self, master, command, bg=C.BG):
        super().__init__(master, width=self.W, bg=bg, highlightthickness=0, bd=0)
        self.command = command
        self.first, self.last = 0.0, 1.0
        self._grab = None  # selisih posisi klik terhadap atas "thumb" saat digeser
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)

    def set(self, first, last):  # dipanggil oleh canvas yang digulir
        self.first, self.last = float(first), float(last)
        self._draw()

    def _thumb(self):
        h = max(1, self.winfo_height())
        y0 = self.first * h
        y1 = max(self.last * h, y0 + self.MIN_THUMB)
        if y1 > h:
            y0, y1 = max(0, h - (y1 - y0)), h
        return y0, y1

    def _draw(self, active=False):
        self.delete("all")
        y0, y1 = self._thumb()
        w = self.W
        color = "#5a6072" if active else C.TRACK_OFF
        self.create_oval(0, y0, w, y0 + w, fill=color, outline=color)
        self.create_oval(0, y1 - w, w, y1, fill=color, outline=color)
        self.create_rectangle(0, y0 + w / 2, w, y1 - w / 2, fill=color, outline=color)

    def _press(self, e):
        y0, y1 = self._thumb()
        if y0 <= e.y <= y1:
            self._grab = e.y - y0
            self._draw(active=True)
        else:  # klik di jalur: gulir satu halaman
            self.command("scroll", -1 if e.y < y0 else 1, "pages")

    def _motion(self, e):
        if self._grab is not None:
            h = max(1, self.winfo_height())
            self.command("moveto", (e.y - self._grab) / h)

    def _release(self, _e):
        self._grab = None
        self._draw()


class ScrollFrame(tk.Frame):
    """Area yang bisa digulir (roda mouse + scrollbar).

    Taruh isi di  .inner . Scrollbar hanya tampil kalau isinya lebih tinggi
    daripada area yang tersedia.
    """

    _wheel_owner = None   # ScrollFrame yang sedang memegang roda mouse

    def __init__(self, master, bg=C.BG):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0,
                                height=60, yscrollincrement=24)
        self.vsb = DarkScrollbar(self, command=self.canvas.yview, bg=bg)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.bind_all("<MouseWheel>", self._on_wheel)
        ScrollFrame._wheel_owner = self

    def _needs_scroll(self):
        return self.inner.winfo_reqheight() > self.canvas.winfo_height()

    def _refresh(self):
        self.canvas.configure(scrollregion=(0, 0, 0, self.inner.winfo_reqheight()))
        if self._needs_scroll():
            if not self.vsb.winfo_ismapped():
                self.vsb.pack(side="right", fill="y", padx=(6, 0))
        else:
            self.vsb.pack_forget()
            self.canvas.yview_moveto(0)

    def _on_inner(self, _event):
        self._refresh()

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self._win, width=event.width)  # isi selebar area
        self._refresh()

    def _on_wheel(self, event):
        if not self._needs_scroll():
            return
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return
        while w is not None:  # hanya kalau kursor ada di dalam area ini
            if w is self:
                self.canvas.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), "units")
                return
            w = w.master

    def scroll_to_top(self):
        self.canvas.yview_moveto(0)

    def destroy(self):
        # Layar baru dibuat SEBELUM layar lama dihancurkan. Kalau layar lama ikut
        # melepas binding, roda mouse di layar baru mati; jadi lepas hanya kalau
        # binding itu masih milik frame ini.
        if ScrollFrame._wheel_owner is self:
            ScrollFrame._wheel_owner = None
            try:
                self.unbind_all("<MouseWheel>")
            except Exception:
                pass
        super().destroy()
