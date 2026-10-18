"""Simpan file portfolio / assignment ke flashdisk murid.

Folder tujuan dipilih lewat dialog bawaan Tk (tk_chooseDirectory, tanpa modul tambahan).
Dialog langsung membuka flashdisk pertama yang tercolok (drive "removable" di Windows);
folder terakhir yang dipilih diingat di data\\usb_folder.txt.
Penyalinan berjalan di thread terpisah supaya aplikasi tidak macet (video bisa besar).
"""

import os
import shutil
import string
import sys
import threading
import tkinter as tk

from elearning.i18n import L
from elearning import config as C

LAST_FILE = os.path.join(C.DATA_DIR, "usb_folder.txt")


def removable_drives():
    """Drive flashdisk yang tercolok, mis. ['E:\\\\']. Kosong di luar Windows."""
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        k = ctypes.windll.kernel32
        mask = k.GetLogicalDrives()
        out = []
        for i, letter in enumerate(string.ascii_uppercase):
            if mask & (1 << i):
                root = f"{letter}:\\"
                if k.GetDriveTypeW(root) == 2:      # 2 = DRIVE_REMOVABLE
                    out.append(root)
        return out
    except Exception as exc:
        C.log(f"Daftar flashdisk gagal: {exc!r}")
        return []


def drive_info(root):
    """(nama volume, sisa byte, total byte) flashdisk; nama kosong / angka None kalau gagal."""
    label = ""
    if sys.platform == "win32":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(64)
            if ctypes.windll.kernel32.GetVolumeInformationW(root, buf, 64, None, None, None,
                                                             None, 0):
                label = buf.value
        except Exception:
            pass
    try:
        du = shutil.disk_usage(root)
        return label, du.free, du.total
    except OSError:
        return label, None, None


def drive_mask():
    """Bit huruf drive yang ada (murah, boleh dipanggil sering dari thread utama)."""
    if sys.platform != "win32":
        return 0
    try:
        import ctypes
        return ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return 0


def _start_folder():
    drives = removable_drives()
    try:
        with open(LAST_FILE, encoding="utf-8") as f:
            last = f.read().strip()
        from elearning.ui.file_browser import blocked
        if last and os.path.isdir(last) and not blocked(last) and (not drives or
                                             any(last.upper().startswith(d) for d in drives)):
            return last
    except OSError:
        pass
    if drives:
        return drives[0]
    z = getattr(C, "STUDENT_DRIVE", "")
    if z and os.path.isdir(z):   # bukan folder profil di C: (drive Windows, diblok)
        return z
    return os.path.expanduser("~")


def choose_folder(parent, title=None):
    try:
        path = parent.tk.call("tk_chooseDirectory", "-parent", parent.winfo_toplevel(),
                              "-initialdir", _start_folder(), "-mustexist", 1,
                              "-title", title or L("Pilih flashdisk / folder tujuan",
                                                   "Choose a flash drive / folder"))
    except tk.TclError as exc:
        C.log(f"Dialog pilih folder gagal: {exc!r}")
        return ""
    path = str(path or "")
    if path:
        try:
            os.makedirs(C.DATA_DIR, exist_ok=True)
            with open(LAST_FILE, "w", encoding="utf-8") as f:
                f.write(os.path.normpath(path))
        except OSError:
            pass
    return os.path.normpath(path) if path else ""


def _free(folder, name):
    stem, ext = os.path.splitext(name)
    path, n = os.path.join(folder, name), 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{stem} ({n}){ext}")
        n += 1
    return path


def save_items(widget, items, on_done, subfolder=""):
    """Pilih folder lalu salin semua item. on_done(teks, berhasil) dipanggil di thread utama."""
    if not items:
        on_done(L("Belum ada file untuk disimpan.", "No files to save yet."), False)
        return
    folder = choose_folder(widget)
    if not folder:
        return
    from elearning.ui.file_browser import blocked
    if blocked(folder):   # B: = sistem e-learning: murid tidak boleh menyimpan ke sana
        on_done(L("Tidak boleh menyimpan ke drive sistem (B: / C:). Pilih flashdisk atau drive Z:.",
                  "You cannot save to a system drive (B: / C:). Pick a flash drive or drive Z:."),
                False)
        return
    if subfolder:
        folder = os.path.join(folder, "".join(ch for ch in subfolder if ch not in '\\/:*?"<>|'))
    box = {}

    def work():
        ok, failed = 0, 0
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            box["res"] = (L("Folder tidak bisa dibuat: ", "Could not create the folder: ") + str(exc),
                          False)
            return
        for it in items:
            try:
                name = it.get("name") or os.path.basename(it["path"])
                ext = os.path.splitext(it["path"])[1]
                if not name.lower().endswith(ext.lower()):
                    name += ext
                shutil.copyfile(it["path"], _free(folder, name))
                ok += 1
            except Exception as exc:
                C.log(f"Simpan ke flashdisk gagal {it.get('path')!r}: {exc!r}")
                failed += 1
        if failed and not ok:
            box["res"] = (L("Gagal menyimpan. Pastikan flashdisk tercolok dan tidak penuh.",
                            "Could not save. Make sure the flash drive is plugged in and not full."),
                          False)
        else:
            extra = L(f" ({failed} gagal)", f" ({failed} failed)") if failed else ""
            box["res"] = (L(f"{ok} file disimpan ke {folder}{extra}",
                            f"{ok} file(s) saved to {folder}{extra}"), True)

    threading.Thread(target=work, daemon=True).start()

    def poll():
        if "res" not in box:
            try:
                widget.after(120, poll)
            except tk.TclError:
                pass
            return
        try:
            on_done(*box["res"])
        except tk.TclError:
            pass
    on_done(L(f"Menyimpan {len(items)} file…", f"Saving {len(items)} file(s)…"), True)
    poll()
