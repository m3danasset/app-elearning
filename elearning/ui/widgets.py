"""Komponen kecil yang dipakai di beberapa layar."""

import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C


def add_hover(button, normal, hover):
    """Ubah warna tombol saat kursor di atasnya."""
    button.bind("<Enter>", lambda e: button.config(bg=hover))
    button.bind("<Leave>", lambda e: button.config(bg=normal))


class MarqueeLabel(tk.Canvas):
    """Teks satu baris. Kalau kepanjangan dipotong dengan "..." di akhir; saat kursor di atasnya,
    teks berjalan ke kiri sampai ujungnya terbaca, lalu kembali dipotong saat kursor pergi."""

    STEP_MS = 30      # jeda antar gerakan
    STEP_PX = 2       # jarak geser tiap gerakan
    START_DELAY = 350  # jeda sebelum mulai berjalan (ms)
    PAD = 2           # ruang kosong di kanan teks saat berhenti

    def __init__(self, master, text, font, bg, fg, cursor="", padx=10, pady=5):
        self._font = tkfont.Font(font=font)
        self._text = text
        self._padx = padx
        super().__init__(master, bg=bg, height=self._font.metrics("linespace") + 2 * pady,
                         width=10, highlightthickness=0, bd=0, cursor=cursor)
        self._fg = fg
        self._job = None
        self._running = False
        self._x = padx
        self._full_w = self._font.measure(text)
        self._item = self.create_text(padx, self.winfo_reqheight() // 2, text=text,
                                      anchor="w", font=self._font, fill=fg)
        self.bind("<Configure>", lambda e: self._reset())
        self.bind("<Destroy>", lambda e: self.stop(), add="+")

    def set_colors(self, bg=None, fg=None):
        if bg is not None:
            self.config(bg=bg)
        if fg is not None:
            self._fg = fg
            self.itemconfig(self._item, fill=fg)

    def _avail(self):
        return max(1, self.winfo_width() - 2 * self._padx)

    def _fit(self):
        """Teks yang muat di lebar saat ini, dengan "..." kalau dipotong."""
        avail = self._avail()
        if self._full_w <= avail:
            return self._text
        dots = "..."
        lo, hi = 0, len(self._text)
        while lo < hi:   # cari huruf terbanyak yang masih muat bersama "..."
            mid = (lo + hi + 1) // 2
            if self._font.measure(self._text[:mid].rstrip() + dots) <= avail:
                lo = mid
            else:
                hi = mid - 1
        return self._text[:lo].rstrip() + dots

    def truncated(self):
        return self._full_w > self._avail()

    def _reset(self):
        self.stop()
        self._x = self._padx
        self.itemconfig(self._item, text=self._fit())
        self.coords(self._item, self._x, self.winfo_height() // 2)

    def start(self):
        """Mulai berjalan ke kiri (hanya kalau teksnya terpotong)."""
        if self._running or not self.truncated():
            return
        self._running = True
        self.itemconfig(self._item, text=self._text)
        self.coords(self._item, self._padx, self.winfo_height() // 2)
        self._x = self._padx
        self._job = self.after(self.START_DELAY, self._tick)

    def stop(self):
        self._running = False
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _tick(self):
        self._job = None
        end_x = self._avail() + self._padx - self._full_w - self.PAD   # posisi saat ujung teks terlihat
        if self._x <= end_x:
            return   # sudah sampai ujung: diam sampai kursor pergi
        self._x = max(end_x, self._x - self.STEP_PX)
        self.coords(self._item, self._x, self.winfo_height() // 2)
        self._job = self.after(self.STEP_MS, self._tick)

    def hover_off(self):
        """Kursor pergi: berhenti dan kembali ke teks yang dipotong."""
        self._reset()


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
        color = C.LOCKED if active else C.TRACK_OFF
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

    Beberapa ScrollFrame boleh hidup bersamaan di satu layar (mis. daftar murid di
    sidebar guru + isi di sebelah kanan): satu binding roda mouse melayani semuanya,
    dan yang menggulir adalah frame tempat kursor berada.
    """

    _live = []   # semua ScrollFrame yang masih hidup

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
        if not ScrollFrame._live:   # binding roda hanya dipasang sekali
            self.bind_all("<MouseWheel>", ScrollFrame._on_wheel_all)
        ScrollFrame._live.append(self)

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

    @staticmethod
    def _on_wheel_all(event):
        for frame in list(ScrollFrame._live):
            if frame._on_wheel(event):   # sudah ditangani frame ini
                return

    def _on_wheel(self, event):
        """True kalau kursor ada di dalam frame ini dan isinya memang bisa digulir."""
        if not self._needs_scroll():
            return False
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return False
        while w is not None:  # hanya kalau kursor ada di dalam area ini
            if w is self:
                self.canvas.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), "units")
                return True
            w = w.master
        return False

    def scroll_to_top(self):
        self.canvas.yview_moveto(0)

    def destroy(self):
        # Layar baru dibuat SEBELUM layar lama dihancurkan, jadi binding roda baru
        # dilepas kalau sudah tidak ada ScrollFrame yang hidup.
        if self in ScrollFrame._live:
            ScrollFrame._live.remove(self)
        if not ScrollFrame._live:
            try:
                self.unbind_all("<MouseWheel>")
            except Exception:
                pass
        super().destroy()
