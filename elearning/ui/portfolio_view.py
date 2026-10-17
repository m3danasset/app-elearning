"""Tampilan portfolio.

ThumbGrid       : kisi thumbnail kecil (dipakai layar murid dan layar guru)
PortfolioPanel  : panel murid di dalam kursus: tombol unggah + kisi hasil karya
"""

import os
import threading
import tkinter as tk
from datetime import datetime

from elearning.i18n import L
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

    def __init__(self, master, items, bg=C.BG, on_delete=None, on_error=None, on_save=None):
        super().__init__(master, bg=bg)
        self.on_delete = on_delete
        self.on_save = on_save
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
                self.on_error(L("File tidak bisa dibuka. Mungkin sudah dipindah atau dihapus.",
                                  "Could not open the file. It may have been moved or deleted."))

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
                if item["kind"] == "video":    # tanda video: lingkaran gelap + segitiga, halus
                    d = 34
                    x, y = (img.width - d) // 2, (img.height - d) // 2
                    circ = I.round_mask(d, d, d / 2).point(lambda v: v * 150 // 255)
                    img.paste((0, 0, 0), (x, y), circ)
                    tri = I._render_icon("play_fill", "#ffffff", "#000000", 18).convert("L")
                    img.paste((255, 255, 255), (x + 9, y + 8), tri)
            photo = photos.to_photoimage(img) if img is not None else None
        except Exception as exc:
            C.log(f"Thumbnail {item['path']!r} tidak bisa ditampilkan: {exc!r}")
        if photo is not None:
            pic = tk.Label(card, image=photo, bg=C.CARD, bd=0, cursor="hand2")
            pic.image = photo   # simpan referensi supaya gambar tidak hilang
        else:
            pic = tk.Label(card, text=L("(tanpa thumbnail)", "(no thumbnail)"), bg=C.CARD_HOVER, fg=C.MUTED,
                           width=22, height=6, font=(C.FONT, 9), cursor="hand2")
        pic.pack()
        pic.bind("<Button-1>", lambda e, it=item: self._open(it))


        tk.Label(card, text=_short(item["name"]), bg=C.CARD, fg=C.TEXT, anchor="w",
                 font=(C.FONT, 9, "bold")).pack(fill="x", pady=(6, 0))
        meta = tk.Frame(card, bg=C.CARD)
        meta.pack(fill="x")
        when = item["added"]
        if isinstance(when, datetime):
            when = when.strftime("%d/%m/%Y")
        tk.Label(meta, text=f"{when}  ·  {portfolio.format_size(item['size'])}", bg=C.CARD,
                 fg=C.MUTED, anchor="w", font=(C.FONT, 8)).pack(side="left")
        acts = meta
        if self.on_save is not None and self.on_delete is not None:   # dua aksi: baris sendiri
            acts = tk.Frame(card, bg=C.CARD)
            acts.pack(fill="x", pady=(2, 0))
        for text, fn, hover in ((L("Hapus", "Delete"), self.on_delete, C.ERROR),
                                (L("Simpan", "Save"), self.on_save, C.TEXT)):
            if fn is None:
                continue
            lb = tk.Label(acts, text=text, bg=C.CARD, fg=C.MUTED, cursor="hand2", font=(C.FONT, 8))
            lb.pack(side="right", padx=(10, 0))
            lb.bind("<Enter>", lambda e, w=lb, h=hover: w.config(fg=h))
            lb.bind("<Leave>", lambda e, w=lb: w.config(fg=C.MUTED))
            if fn is self.on_save:
                lb.bind("<Button-1>", lambda e, it=item: self.on_save([it]))
            else:
                lb.bind("<Button-1>", lambda e, it=item: self.on_delete(it))
        return panel


class PortfolioPanel(tk.Frame):
    """Halaman Portfolio / Assignment murid (galeri gaya Behance) atau bahan guru.

    section: None = portfolio murid, ASSIGNMENT = assignment murid,
             CONTOH / CONTOH_PF = bahan dari guru (layar guru; student = {"id": "_"}).
    Murid melihat kategori: Semua  ·  Upload saya  ·  Dari guru.
    """

    @staticmethod
    def _texts():
        """Dibuat saat dipakai (bukan saat modul dimuat) supaya ikut bahasa yang aktif."""
        return {
            None: (L("Portfolio saya", "My portfolio"), L("+  Upload karya", "+  Upload artwork"),
                   portfolio.CONTOH_PF),
            portfolio.ASSIGNMENT: (L("Assignment saya", "My assignments"), "+  Upload render",
                                   portfolio.CONTOH),
            portfolio.CONTOH: ("Contoh assignment", "+  Upload contoh", None),
            portfolio.CONTOH_PF: ("Inspirasi portfolio", "+  Upload inspirasi", None),
        }

    def __init__(self, master, student, course, on_change=None, section=None):
        super().__init__(master, bg=C.BG)
        from elearning.ui.gallery import GalleryBoard
        self.student = student
        self.course = course
        self.on_change = on_change
        self.section = section
        self.teacher = section in portfolio.TEACHER_SECTIONS
        title, upload, self.guru_section = self._texts()[section]
        self.category = "all"
        self._busy = False

        head = tk.Frame(self, bg=C.BG)
        head.pack(fill="x", padx=28, pady=(22, 0))
        self.upload_btn = RoundButton(
            head, text=upload, command=self._upload, bg=C.ACCENT,
            fg="white", activebackground=C.ACCENT_HOVER, activeforeground="white",
            disabledforeground="#ffd9b0", relief="flat", bd=0, highlightthickness=0,
            font=(C.FONT, 11, "bold"), cursor="hand2", padx=18, pady=8)
        self.upload_btn.pack(side="right", anchor="n")
        add_hover(self.upload_btn, C.ACCENT, C.ACCENT_HOVER)
        if not self.teacher:      # murid: simpan file yang sedang tampil ke flashdisk
            RoundButton(head, text=L("Simpan ke flashdisk", "Save to flash drive"), command=self._save_all,
                        bg=C.CARD, fg=C.TEXT, activebackground=C.CARD_HOVER,
                        font=(C.FONT, 10), padx=14, pady=8).pack(side="right", anchor="n",
                                                                 padx=(0, 8))
        left = tk.Frame(head, bg=C.BG)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=title, bg=C.BG, fg=C.TEXT, anchor="w",
                 font=(C.FONT, 18, "bold")).pack(fill="x")
        self.summary = tk.Label(left, text="", bg=C.BG, fg=C.MUTED, anchor="w",
                                font=(C.FONT, 10))
        self.summary.pack(fill="x", pady=(2, 0))

        self.tabs = {}
        if not self.teacher:      # kategori: semua / upload sendiri / disediakan guru
            bar = tk.Frame(self, bg=C.BG)
            bar.pack(fill="x", padx=28, pady=(14, 0))
            for key in ("all", "own", "guru"):
                b = RoundButton(bar, text="", command=lambda k=key: self._set_category(k),
                                font=(C.FONT, 10), padx=12, pady=5)
                b.pack(side="left", padx=(0, 6))
                self.tabs[key] = b

        self.status = tk.Label(self, text="", bg=C.BG, fg=C.MUTED, anchor="w",
                               justify="left", wraplength=640, font=(C.FONT, 10))
        self.status.pack(fill="x", padx=28, pady=(8, 4))

        self.scroll = ScrollFrame(self, bg=C.BG)
        self.scroll.pack(fill="both", expand=True, padx=(28, 16), pady=(0, 12))
        self.gallery = GalleryBoard(self.scroll.inner, on_open=self._open,
                                    on_save=None if self.teacher else self._save,
                                    on_delete=self._delete,
                                    on_blender=None if self.teacher else self._to_blender)
        self.gallery.pack(fill="x")
        self.refresh()

    # --- isi ----------------------------------------------------------------------
    def _items(self):
        own = [dict(it, own=True) for it in
               portfolio.list_items(self.student["id"], self.course["id"], self.section)]
        guru = []
        if self.guru_section:
            guru = [dict(it, own=False) for it in
                    portfolio.list_items("_", self.course["id"], self.guru_section)]
        return own, guru

    def refresh(self):
        own, guru = self._items()
        if self.teacher:
            shown = own
            empty = L("Belum ada. Klik \u201c", "Nothing yet. Click \u201c") + \
                self.upload_btn.cget("text").strip("+ ") + \
                L("\u201d untuk menambahkan.", "\u201d to add one.")
        else:
            shown = {"all": sorted(own + guru, key=lambda i: i["added"], reverse=True),
                     "own": own, "guru": guru}[self.category]
            empty = {"all": L("Belum ada karya. Klik tombol Upload untuk menambahkan.",
                              "No artwork yet. Click Upload to add some."),
                     "own": L("Kamu belum mengunggah apa pun di sini.",
                              "You have not uploaded anything here yet."),
                     "guru": L("Guru belum menyediakan bahan untuk kursus ini.",
                               "Your teacher has not added material for this course yet.")
                     }[self.category]
            labels = {"all": L("Semua", "All") + f"  {len(own) + len(guru)}",
                      "own": L("Upload saya", "My uploads") + f"  {len(own)}",
                      "guru": L("Dari guru", "From teacher") + f"  {len(guru)}"}
            for k, b in self.tabs.items():
                on = k == self.category
                b.config(text=labels[k], bg=C.SEG_ON if on else C.BG,
                         fg=C.TEXT if on else C.MUTED,
                         activebackground=C.SEG_ON if on else C.CARD_HOVER,
                         activeforeground=C.TEXT)
        all_items = own + guru
        videos = sum(1 for i in all_items if i["kind"] == "video")
        last = max((i["added"] for i in all_items), default=None)
        parts = [f"{len(all_items)} " + L("karya", "artworks"),
                 f"{videos} " + L("video", "videos")]
        if last is not None:
            days = (datetime.now() - last).days
            parts.append(L("terakhir hari ini", "last today") if days <= 0
                         else L(f"terakhir {days} hari lalu",
                                f"last {days} day{'s' if days != 1 else ''} ago"))
        self.summary.config(text=f"{self.course['title']}   ·   " + "  ·  ".join(parts))
        self.gallery.set_items(shown, empty)

    def _set_category(self, key):
        if key != self.category:
            self.category = key
            self.refresh()
            self.scroll.scroll_to_top()

    def _open(self, item):
        try:
            portfolio.open_file(item["path"])
        except Exception as exc:
            C.log(f"Gagal membuka {item['path']!r}: {exc!r}")
            self.status.config(text=L("File tidak bisa dibuka.", "Could not open the file."),
                               fg=C.ERROR)

    # --- gambar guru -> Blender (Image Editor di kiri 3D viewport, tanpa addon) -----------
    def _to_blender(self, item):
        from elearning import blender_launcher
        app = self.winfo_toplevel()
        if blender_launcher.open_with_reference(app, [item["path"]]):
            self.status.config(text=L("Blender dibuka dengan gambar referensi di sebelah kiri.",
                                       "Blender opened with the reference image on the left."),
                               fg=C.ON)
            ctl = getattr(app, "blender_float", None)
            if ctl is not None:   # sama seperti tombol Buka Blender: aplikasi mengecil
                ctl.enter()

    # --- simpan ke flashdisk ---------------------------------------------------------
    def _save(self, items):
        from elearning.ui import usb_save
        sub = f"{self.course['title']} - {'Assignment' if self.section else 'Portfolio'}"
        usb_save.save_items(self, items, lambda text, ok: self.status.config(
            text=text, fg=C.ON if ok else C.ERROR), subfolder=sub)

    def _save_all(self):
        self._save(list(self.gallery.items))

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
            self.status.config(text=L("Dialog pilih file tidak bisa dibuka.",
                                       "Could not open the file picker."), fg=C.ERROR)
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
        if not self.teacher:     # murid: file browser gaya aplikasi (Details / thumbnail)
            from elearning.ui.file_browser import open_file_browser
            what = "render assignment" if self.section == portfolio.ASSIGNMENT \
                else L("karya", "artwork")
            if open_file_browser(self, mode="pick", exts=portfolio.IMAGE_EXT + portfolio.VIDEO_EXT,
                                 title=L("Pilih ", "Choose ") + what, on_pick=self._upload_paths) is not None:
                return
        self._upload_paths(self._pick_files())   # guru / cadangan: dialog bawaan Windows

    def _upload_paths(self, paths):
        if self._busy or not paths:   # dibatalkan
            return
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self._busy = True
        self.upload_btn.config(state="disabled")
        sid, cid = self.student["id"], self.course["id"]
        job = {"done": 0, "ok": 0, "errors": [], "finished": False, "total": len(paths)}

        def work():
            for p in paths:
                try:
                    portfolio.add_file(sid, cid, p, self.section)
                    job["ok"] += 1
                except ValueError as exc:
                    job["errors"].append(f"{_short(os.path.basename(p), 30)}: {exc}")
                except Exception as exc:   # jangan sampai thread berhenti diam-diam
                    C.log(f"Unggah portfolio gagal {p!r}: {exc!r}")
                    job["errors"].append(f"{_short(os.path.basename(p), 30)}: "
                                         + L("gagal diunggah", "upload failed"))
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
                    text=L(f"Mengunggah {min(job['done'] + 1, job['total'])} "
                           f"dari {job['total']}… (video besar butuh waktu)",
                           f"Uploading {min(job['done'] + 1, job['total'])} "
                           f"of {job['total']}… (large videos take a while)"), fg=C.MUTED)
                self.after(150, lambda: self._poll(job))
                return
            self._busy = False
            self.upload_btn.config(state="normal")
            self.refresh()
            if self.on_change:
                self.on_change()
            parts = []
            if job["ok"]:
                parts.append(L(f"{job['ok']} file ditambahkan.", f"{job['ok']} file(s) added."))
            if job["errors"]:
                parts.append(L("Gagal: ", "Failed: ") + "; ".join(job["errors"][:4])
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
                return L("File tidak bisa dihapus.", "Could not delete the file.")
            return None

        ConfirmDialog(self, L("Hapus file ini?", "Delete this file?"),
                      L(f"{item['name']} akan dihapus dan tidak bisa dikembalikan.",
                        f"{item['name']} will be deleted and cannot be restored."),
                      confirm, confirm_text=L("Hapus", "Delete")).wait_window()
        self.refresh()
        if self.on_change:
            self.on_change()


class ExamplesPanel(tk.Frame):
    """Layar guru: bahan dari guru per kursus, untuk Assignment (contoh) dan Portfolio
    (inspirasi). Muncul di kategori "Dari guru" pada halaman murid."""

    def __init__(self, master):
        super().__init__(master, bg=C.BG)
        from elearning.courses import COURSES, has_video
        from elearning.ui.controls import RoundSelect
        self.courses = [c for c in COURSES if c["program"] in ("adult", "kids") and has_video(c)]
        self._by_title = {c["title"]: c for c in self.courses}
        self.section = portfolio.CONTOH
        bar = tk.Frame(self, bg=C.BG)
        bar.pack(fill="x", padx=28, pady=(18, 0))
        self.seg = {}
        for key, label in ((portfolio.CONTOH, "Assignment"), (portfolio.CONTOH_PF, "Portfolio")):
            b = RoundButton(bar, text=label, command=lambda k=key: self._set_section(k),
                            font=(C.FONT, 10), padx=12, pady=5)
            b.pack(side="left", padx=(0, 6))
            self.seg[key] = b
        tk.Label(bar, text="Kursus", bg=C.BG, fg=C.MUTED, font=(C.FONT, 10)).pack(
            side="left", padx=(18, 10))
        self.var = tk.StringVar(value=self.courses[0]["title"])
        RoundSelect(bar, self.var, *self._by_title, command=lambda v: self._show()).pack(
            side="left")
        self.body = tk.Frame(self, bg=C.BG)
        self.body.pack(fill="both", expand=True)
        self._show()

    def _set_section(self, key):
        if key != self.section:
            self.section = key
            self._show()

    def _show(self):
        for k, b in self.seg.items():
            on = k == self.section
            b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
                     activebackground=C.SEG_ON if on else C.CARD_HOVER, activeforeground=C.TEXT)
        for w in self.body.winfo_children():
            w.destroy()
        PortfolioPanel(self.body, {"id": "_"}, self._by_title[self.var.get()],
                       section=self.section).pack(fill="both", expand=True)
