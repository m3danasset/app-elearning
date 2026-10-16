"""Tampilan portfolio.

ThumbGrid       : kisi thumbnail kecil (dipakai layar murid dan layar guru)
PortfolioPanel  : panel murid di dalam kursus: tombol unggah + kisi hasil karya
"""

import os
import threading
import tkinter as tk
from datetime import datetime

from elearning import config as C
from elearning.ui.controls import RoundButton, RoundPanel
from elearning import photos, portfolio
from elearning.ui.dialogs import ConfirmDialog
from elearning.ui.widgets import ScrollFrame, add_hover

_CARD_PAD = 8
_CELL_W = portfolio.THUMB_W + 2 * _CARD_PAD + 14   # lebar satu kolom termasuk jarak
_NAME_MAX = 24


def _short(name, limit=_NAME_MAX):
    return name if len(name) <= limit else name[:limit - 1] + "…"


class ThumbGrid(tk.Frame):
    """Kisi thumbnail. Jumlah kolom menyesuaikan lebar area.

    items     : hasil portfolio.list_items()
    on_delete : kalau diisi, tiap kartu punya tautan "Hapus" -> on_delete(item)
    on_error  : dipanggil dengan teks kalau file tidak bisa dibuka
    """

    def __init__(self, master, items, bg=C.BG, on_delete=None, on_error=None):
        super().__init__(master, bg=bg)
        self.on_delete = on_delete
        self.on_error = on_error
        self._cols = 0
        self._cards = [self._make_card(it) for it in items]
        self.bind("<Configure>", lambda e: self._relayout(e.width))

    def _relayout(self, width):
        cols = max(1, width // _CELL_W)
        if cols == self._cols:
            return
        self._cols = cols
        for i, card in enumerate(self._cards):
            card.grid(row=i // cols, column=i % cols, padx=6, pady=6, sticky="nw")

    def _open(self, item):
        try:
            portfolio.open_file(item["path"])
        except Exception as exc:
            C.log(f"Gagal membuka {item['path']!r}: {exc!r}")
            if self.on_error:
                self.on_error("File tidak bisa dibuka. Mungkin sudah dipindah atau dihapus.")

    def _make_card(self, item):
        panel = RoundPanel(self, padx=_CARD_PAD, pady=_CARD_PAD, radius=12, fit_width=True)
        card = panel.inner

        photo = None
        try:
            img = portfolio.load_thumb(item["path"])
            if img is not None:   # sudut thumbnail ikut membulat
                from elearning.ui import ui_icons as I
                base = photos.Image.new("RGB", img.size, I._rgb(C.CARD))
                base.paste(img, (0, 0), I.round_mask(img.width, img.height, 8))
                img = base
            photo = photos.to_photoimage(img) if img is not None else None
        except Exception as exc:
            C.log(f"Thumbnail {item['path']!r} tidak bisa ditampilkan: {exc!r}")
        if photo is not None:
            pic = tk.Label(card, image=photo, bg=C.CARD, bd=0, cursor="hand2")
            pic.image = photo   # simpan referensi supaya gambar tidak hilang
        else:
            pic = tk.Label(card, text="(tanpa thumbnail)", bg=C.CARD_HOVER, fg=C.MUTED,
                           width=22, height=6, font=(C.FONT, 9), cursor="hand2")
        pic.pack()
        pic.bind("<Button-1>", lambda e, it=item: self._open(it))

        if item["kind"] == "video":
            badge = tk.Label(pic, text="▶  VIDEO", bg="#0b0d12", fg="white", cursor="hand2",
                             font=(C.FONT, 8, "bold"), padx=6, pady=1)
            badge.place(x=6, y=portfolio.THUMB_H - 24)
            badge.bind("<Button-1>", lambda e, it=item: self._open(it))

        tk.Label(card, text=_short(item["name"]), bg=C.CARD, fg=C.TEXT, anchor="w",
                 font=(C.FONT, 9, "bold")).pack(fill="x", pady=(6, 0))
        meta = tk.Frame(card, bg=C.CARD)
        meta.pack(fill="x")
        when = item["added"]
        if isinstance(when, datetime):
            when = when.strftime("%d/%m/%Y")
        tk.Label(meta, text=f"{when}  ·  {portfolio.format_size(item['size'])}", bg=C.CARD,
                 fg=C.MUTED, anchor="w", font=(C.FONT, 8)).pack(side="left")
        if self.on_delete is not None:
            dele = tk.Label(meta, text="Hapus", bg=C.CARD, fg=C.ERROR, cursor="hand2",
                            font=(C.FONT, 8, "underline"))
            dele.pack(side="right")
            dele.bind("<Button-1>", lambda e, it=item: self.on_delete(it))
        return panel


class PortfolioPanel(tk.Frame):
    """Area kanan di kursus: murid unggah gambar/video hasil karyanya untuk kursus ini."""

    def __init__(self, master, student, course, on_change=None):
        super().__init__(master, bg=C.BG)
        self.student = student
        self.course = course
        self.on_change = on_change
        self._busy = False

        head = tk.Frame(self, bg=C.BG)
        head.pack(fill="x", padx=28, pady=(22, 0))
        self.upload_btn = RoundButton(
            head, text="+  Upload gambar / video", command=self._upload, bg=C.ACCENT,
            fg="white", activebackground=C.ACCENT_HOVER, activeforeground="white",
            disabledforeground="#ffd9b0", relief="flat", bd=0, highlightthickness=0,
            font=(C.FONT, 11, "bold"), cursor="hand2", padx=18, pady=8)
        self.upload_btn.pack(side="right", anchor="n")
        add_hover(self.upload_btn, C.ACCENT, C.ACCENT_HOVER)
        left = tk.Frame(head, bg=C.BG)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="Portfolio saya", bg=C.BG, fg=C.TEXT, anchor="w",
                 font=(C.FONT, 18, "bold")).pack(fill="x")
        tk.Label(left, text=f"Hasil karya gambar dan video untuk {course['title']}. "
                            "Klik gambar untuk membukanya.",
                 bg=C.BG, fg=C.MUTED, anchor="w", justify="left", wraplength=400,
                 font=(C.FONT, 10)).pack(fill="x", pady=(2, 0))

        self.status = tk.Label(self, text="", bg=C.BG, fg=C.MUTED, anchor="w",
                               justify="left", wraplength=640, font=(C.FONT, 10))
        self.status.pack(fill="x", padx=28, pady=(10, 4))

        self.scroll = ScrollFrame(self, bg=C.BG)
        self.scroll.pack(fill="both", expand=True, padx=(22, 16), pady=(0, 12))
        self.refresh()

    # --- isi ----------------------------------------------------------------------
    def refresh(self):
        for w in self.scroll.inner.winfo_children():
            w.destroy()
        items = portfolio.list_items(self.student["id"], self.course["id"])
        if not items:
            tk.Label(self.scroll.inner, bg=C.BG, fg=C.MUTED, font=(C.FONT, 11),
                     justify="left", anchor="w",
                     text="Belum ada hasil karya.\nKlik “Upload gambar / video” "
                          "untuk menambahkan.").pack(fill="x", padx=6, pady=24)
            return
        ThumbGrid(self.scroll.inner, items, on_delete=self._delete,
                  on_error=lambda msg: self.status.config(text=msg, fg=C.ERROR)
                  ).pack(fill="x")

    # --- unggah -------------------------------------------------------------------
    def _pick_files(self):
        img = portfolio.IMAGE_EXT
        vid = portfolio.VIDEO_EXT
        try:
            result = self.tk.call(
                "tk_getOpenFile", "-parent", str(self.winfo_toplevel()),
                "-title", "Pilih gambar atau video portfolio", "-multiple", 1,
                "-filetypes",
                ((("Gambar dan video"), img + vid), ("Gambar", img), ("Video", vid),
                 ("Semua file", "*")))
        except Exception as exc:
            C.log(f"Dialog pilih file portfolio gagal: {exc!r}")
            self.status.config(text="Dialog pilih file tidak bisa dibuka.", fg=C.ERROR)
            return []
        if isinstance(result, (tuple, list)):
            return [str(p) for p in result]
        text = str(result).strip()
        if not text:
            return []
        return [text] if os.path.isfile(text) else [str(p) for p in self.tk.splitlist(text)]

    def _upload(self):
        if self._busy:
            return
        paths = self._pick_files()
        if not paths:   # dibatalkan
            return
        self._busy = True
        self.upload_btn.config(state="disabled")
        sid, cid = self.student["id"], self.course["id"]
        job = {"done": 0, "ok": 0, "errors": [], "finished": False, "total": len(paths)}

        def work():
            for p in paths:
                try:
                    portfolio.add_file(sid, cid, p)
                    job["ok"] += 1
                except ValueError as exc:
                    job["errors"].append(f"{_short(os.path.basename(p), 30)}: {exc}")
                except Exception as exc:   # jangan sampai thread berhenti diam-diam
                    C.log(f"Unggah portfolio gagal {p!r}: {exc!r}")
                    job["errors"].append(f"{_short(os.path.basename(p), 30)}: gagal diunggah")
                job["done"] += 1
            job["finished"] = True

        threading.Thread(target=work, daemon=True).start()
        self._poll(job)

    def _poll(self, job):
        try:
            if not self.winfo_exists():   # murid sudah pindah layar; unggahan tetap selesai
                return
            if not job["finished"]:
                self.status.config(
                    text=f"Mengunggah {min(job['done'] + 1, job['total'])} "
                         f"dari {job['total']}… (video besar butuh waktu)", fg=C.MUTED)
                self.after(150, lambda: self._poll(job))
                return
            self._busy = False
            self.upload_btn.config(state="normal")
            self.refresh()
            if self.on_change:
                self.on_change()
            parts = []
            if job["ok"]:
                parts.append(f"{job['ok']} file ditambahkan.")
            if job["errors"]:
                parts.append("Gagal: " + "; ".join(job["errors"][:4])
                             + (" …" if len(job["errors"]) > 4 else ""))
            self.status.config(text="  ".join(parts), fg=C.ERROR if job["errors"] else C.ON)
        except tk.TclError:
            pass

    # --- hapus --------------------------------------------------------------------
    def _delete(self, item):
        def confirm():
            try:
                portfolio.remove_item(item["path"])
            except Exception as exc:
                C.log(f"Gagal menghapus {item['path']!r}: {exc!r}")
                return "File tidak bisa dihapus."
            return None

        ConfirmDialog(self, "Hapus dari portfolio?",
                      f"{item['name']} akan dihapus dari portfolio dan tidak bisa "
                      "dikembalikan.", confirm, confirm_text="Hapus").wait_window()
        self.refresh()
        if self.on_change:
            self.on_change()
