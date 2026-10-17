# Aplikasi hanya terbuka sekali: klik ikon berkali-kali tidak membuka jendela baru,
# jendela yang sudah ada dimunculkan ke depan (lihat single_instance.py).
try:
    from elearning import single_instance as _single
    from elearning.config import APP_NAME as _APP_NAME
    _single.ensure(_APP_NAME)
except Exception:
    pass

# Tampilkan splash screen sekecil mungkin SEGERA, sebelum modul berat (OpenCV, Pillow,
# layar-layar) dimuat. Ditutup di elearning/ui/window.py.
try:
    from elearning import splash as _splash
    _splash.show()
except Exception:
    pass
