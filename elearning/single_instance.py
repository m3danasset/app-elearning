"""Aplikasi hanya boleh terbuka SATU kali di satu PC.

Murid pemula sering mengklik ikon berkali-kali sehingga aplikasi terbuka berkali-kali.
Saat mulai, aplikasi membuat "mutex" Windows bernama tetap. Kalau mutex itu sudah ada
(aplikasi sedang terbuka atau sedang memuat), jalankan yang baru langsung berhenti
dan jendela yang sudah ada dimunculkan ke depan (kalau sedang di-minimize, dibuka lagi).

Hanya memakai ctypes (sudah ada di .exe). Di luar Windows tidak melakukan apa-apa.
"""

import os
import sys

_handle = None     # pegangan mutex: disimpan selama aplikasi hidup (dilepas Windows saat keluar)
MUTEX_NAME = "Local\\M3DAN.BlenderELearning.SingleInstance"
ERROR_ALREADY_EXISTS = 183


def _bring_existing_to_front(title):
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW("TkTopLevel", title)   # jendela Tk dengan judul aplikasi
    if not hwnd:
        return False     # masih di splash / sedang memuat: cukup berhenti
    SW_RESTORE = 9
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    # Windows hanya mengizinkan pindah ke depan dari proses yang sedang aktif;
    # tekan-lepas ALT kecil ini membuka izin itu (trik yang umum dipakai).
    try:
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
    except Exception:
        pass
    user32.SetForegroundWindow(hwnd)
    return True


def ensure(title):
    """Panggil paling awal. Kalau aplikasi sudah terbuka: munculkan lalu keluar."""
    global _handle
    if sys.platform != "win32" or _handle is not None:
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        already = kernel32.GetLastError() == ERROR_ALREADY_EXISTS
    except Exception:
        return            # kalau gagal, jangan sampai aplikasi tidak bisa dibuka
    if not already:
        _handle = handle
        return
    try:
        _bring_existing_to_front(title)
    except Exception:
        pass
    os._exit(0)           # berhenti diam-diam (tanpa splash, tanpa jendela kedua)
