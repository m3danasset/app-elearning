# Tampilkan splash screen sekecil mungkin SEGERA, sebelum modul berat (OpenCV, Pillow,
# layar-layar) dimuat. Ditutup di elearning/ui/window.py.
try:
    from elearning import splash as _splash
    _splash.show()
except Exception:
    pass
