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


def eject(root):
    """Keluarkan flashdisk dengan aman (seperti "Eject" di Explorer): kunci volume, tulis sisa
    cache, lepas (dismount), keluarkan media. None = berhasil, atau pesan English kalau gagal
    (mis. ada file yang masih terbuka). Panggil dari thread (bisa ~1 dtk)."""
    if sys.platform != "win32":
        return "Eject is only available on Windows."
    import ctypes
    import time
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)      # salinan sendiri (argtypes)
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                              wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.CreateFileW.restype = wintypes.HANDLE
    k.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    k.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    h = k.CreateFileW("\\\\.\\" + root[:2], 0xC0000000, 3, None, 3, 0, None)
    if h is None or h == wintypes.HANDLE(-1).value:
        return f"Can't eject {root[:2]}. Try again."
    got = wintypes.DWORD()

    def ioctl(code, inbuf=None, size=0):
        return k.DeviceIoControl(h, code, inbuf, size, None, 0, ctypes.byref(got), None)

    try:
        k.FlushFileBuffers(h)
        for _ in range(10):                          # FSCTL_LOCK_VOLUME (file masih terbuka?)
            if ioctl(0x00090018):
                break
            time.sleep(0.2)
        else:
            return f"{root[:2]} is in use. Close its files first."
        ioctl(0x00090020)                            # FSCTL_DISMOUNT_VOLUME
        keep = ctypes.c_ubyte(0)                     # PREVENT_MEDIA_REMOVAL = FALSE
        ioctl(0x002D4804, ctypes.byref(keep), 1)     # IOCTL_STORAGE_MEDIA_REMOVAL
        if not ioctl(0x002D4808):                    # IOCTL_STORAGE_EJECT_MEDIA
            return f"Can't eject {root[:2]}. Try again."
        C.log(f"Flashdisk {root[:2]} dikeluarkan (eject)")
        return None
    finally:
        k.CloseHandle(h)


_quiet = []


def drive_info(root):
    """(nama volume, sisa byte, total byte) flashdisk; nama kosong / angka None kalau gagal."""
    label = ""
    if sys.platform == "win32":
        try:
            import ctypes
            if not _quiet:       # tanpa popup "Please insert a disk" untuk drive tanpa media
                ctypes.windll.kernel32.SetErrorMode(0x0001)
                _quiet.append(True)
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


class UsbMonitor:
    """Pemantau flashdisk SATU per jendela (widget USB Dashboard murid + menu USB sidebar).
    Thread utama: cek huruf drive tiap 1 dtk (murah). Berubah, atau tiap 5 dtk: baca
    flashdisk di thread (nama, sisa ruang; tanpa media = tidak dihitung). Pendengar dipanggil
    di thread utama dengan daftar [(root, label, free, total)] setiap isinya berubah."""

    POLL_MS, RESCAN_S = 1000, 5.0

    def __init__(self, top):
        self.top = top
        self.drives = None             # None = belum pernah dibaca
        self._subs = []
        self._mask = None
        self._box = []
        self._busy = False
        self._scan_t = 0.0
        self._job = None

    def subscribe(self, fn):
        """fn(drives) dipanggil saat berubah (dan segera kalau sudah ada data).
        Mengembalikan fungsi untuk berhenti mendengar."""
        self._subs.append(fn)
        if self.drives is not None:
            self.top.after_idle(lambda: fn in self._subs and fn(self.drives))
        if self._job is None:
            self._job = self.top.after(10, self._poll)

        def stop():
            if fn in self._subs:
                self._subs.remove(fn)
        return stop

    def refresh(self):
        """Baca ulang secepatnya (mis. sesudah eject)."""
        self._mask = None

    def drop(self, roots):
        """Flashdisk yang baru dikeluarkan: langsung hilang dari daftar."""
        if self.drives:
            self._set([d for d in self.drives if d[0] not in roots])
        self.refresh()

    def _set(self, drives):
        if drives == self.drives:
            return
        self.drives = drives
        for fn in list(self._subs):
            try:
                fn(drives)
            except Exception as exc:
                C.log(f"Pemantau USB: pendengar gagal: {exc!r}")

    def _poll(self):
        import time
        self._job = None
        if not self._subs:
            return                     # tidak ada yang mendengar: berhenti (hemat)
        try:
            if not self.top.winfo_exists():
                return
        except tk.TclError:
            return
        if self._box:
            self._set(self._box.pop())
            self._box.clear()
        mask = drive_mask()
        now = time.monotonic()
        if (mask != self._mask or now - self._scan_t > self.RESCAN_S) and not self._busy:
            self._mask, self._scan_t, self._busy = mask, now, True
            box = self._box

            def work():
                try:
                    out = [(r,) + drive_info(r) for r in removable_drives()]
                    out = [d for d in out if d[3] is not None]   # tanpa media (sudah eject)
                except Exception as exc:
                    C.log(f"Pemantau USB: {exc!r}")
                    out = []
                box.append(out)
                self._busy = False

            threading.Thread(target=work, daemon=True).start()
        wait = 100 if (self._busy or self._box or self.drives is None) else self.POLL_MS
        self._job = self.top.after(wait, self._poll)


def monitor(widget):
    top = widget.winfo_toplevel()
    m = getattr(top, "_usb_monitor", None)
    if m is None:
        m = top._usb_monitor = UsbMonitor(top)
    return m


def eject_async(widget, roots, on_done):
    """Eject di thread; sesudahnya (thread utama): yang berhasil dibuang dari pemantau lalu
    on_done(daftar pesan gagal)."""
    box = []
    mon = monitor(widget)

    def work():
        box.append([(r, eject(r)) for r in roots])

    def wait():
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        if not box:
            widget.after(100, wait)
            return
        done = {r for r, err in box[0] if err is None}
        if done:
            mon.drop(done)
        on_done([err for _r, err in box[0] if err])

    threading.Thread(target=work, daemon=True).start()
    widget.after(100, wait)


def drive_name(d):
    """'KINGSTON (E:)' / 'USB (E:)' dari (root, label, free, total)."""
    return f"{d[1]} ({d[0][:2]})" if d[1] else f"USB ({d[0][:2]})"


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
