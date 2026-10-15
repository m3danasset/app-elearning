@echo off
cd /d "%~dp0"
echo === Memasang kebutuhan (PyInstaller, OpenCV, Pillow, python-mpv) ===
python -m pip install --upgrade pyinstaller -r requirements.txt
if errorlevel 1 goto gagal
echo.
echo === Membuat .exe ===
python -m PyInstaller --onefile --windowed --noconfirm --clean ^
  --name "Blender E-Learning" ^
  --icon "%CD%\assets\icon.ico" ^
  --add-data "%CD%\assets\icon.ico;assets" ^
  --hidden-import PIL._tkinter_finder ^
  --hidden-import mpv ^
  --hidden-import ctypes.util ^
  --specpath "%CD%\build" ^
  --workpath "%CD%\build\work" ^
  --distpath "%CD%\dist" ^
  main.py
if errorlevel 1 goto gagal
echo.
echo === Menyalin video dan kode ke samping .exe ===
call "%~dp0update.bat" nopause
if errorlevel 1 goto gagal
echo.
echo SELESAI.
echo Hasilnya ada di folder dist\ :
echo   Blender E-Learning.exe
echo   assets\video\     (video latar, bisa diganti tanpa build ulang)
echo   app\elearning\    (kode aplikasi, bisa diperbarui tanpa build ulang)
echo Untuk PC lain: copy SEMUA isi folder dist\.
pause
exit /b 0
:gagal
echo.
echo GAGAL. Kirim pesan error di atas ke Claude.
pause
exit /b 1
