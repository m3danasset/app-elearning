# Blender E-Learning (M3DAN Studios): catatan untuk Claude Code

Aplikasi desktop Tkinter (Windows 11), dikirim sebagai .exe (PyInstaller). Revisi dipasang
dengan update.bat yang menimpa file .py yang direvisi. Peran: admin, guru, murid (dewasa
PB..., anak SK...), trial. Balas pengguna dalam bahasa Indonesia.

## Cek wajib sebelum setiap build / revisi
1. Hanya pakai modul yang sudah ikut di .exe. JANGAN pakai: zipfile, xml, socket, glob,
   tkinter.filedialog, tkinter.messagebox, ImageDraw, ImageFilter. Untuk dialog pakai
   bawaan Tk (tk_getOpenFile, tk_chooseDirectory). Tes dengan modul-modul itu diblokir;
   import yang gagal membuat .exe diam-diam kembali ke aplikasi lama.
2. Tidak boleh ada glitch UI (tombol terpotong, blok hitam) saat pindah windowed/fullscreen,
   tab, periode, filter, atau tampilan.
3. Animasi harus mulus, tidak patah-patah: jadwal frame tetap, gerakan berbasis waktu.
   Maks. 60 fps untuk transisi kecil, 30 fps untuk animasi berat (carousel login).
   Ukur jarak antar frame di layar biasa dan 1920x1080 sebelum dikirim.
4. Tidak ada yang pecah/pixelated (ikon, panah, switch, centang, lingkaran, bentuk apa pun):
   pakai gambar antialias (ui/ui_icons.py), bukan garis Tk.
5. Harus ringan di Ryzen 5 2400G + Vega (tanpa GPU terpisah). Kerja berat di thread
   (Pillow melepas GIL); Tk hanya dipanggil dari thread utama.
6. Kirim zip kumulatif berisi file .py yang berubah untuk update.bat; folder data harus aman.
7. UI konsisten dengan layar login & gaya claude.ai: sudut membulat, ikon minimalis.
   Setiap fitur/tombol baru wajib mengikuti gaya ini.

## Status terakhir (layar login)
- ui/login_screen.py: logo besar (assets\logo.png, dengan bayangan lembut buatan sendiri),
  kolom "Enter Your ID" transparan (gambar + teks canvas, bukan Entry), kolom PIN tambahan
  muncul di bawahnya untuk ID guru/admin (Enter/Tab/panah = pindah, Esc = kembali ke ID).
  Tanpa tombol Masuk (Enter).
- ui/carousel3d.py: carousel 3D silinder, maks. 10 portfolio murid (bukan assignment /
  contoh guru), loop, 30 fps dengan jadwal frame tetap, gerak lambat (1 kartu / 9 detik),
  fade tepi kiri-kanan. Dirender di 2-3 thread.
- ui/login_bg.py: canvas video latar (opacity rendah) + pita carousel.
- config.py: LOGIN_CAROUSEL_FPS = 30 (maks. 30).
- Belum diuji langsung di PC studio (Ryzen 5 2400G): kelancaran carousel & ukuran logo asli.
