@echo off
rem Menyalin kode (elearning\) dari folder proyek ke dist\app\ (dan video contoh kalau belum ada)
rem TANPA membuat .exe lagi. Jalankan setiap kali ada revisi kode.
cd /d "%~dp0"
if not exist "dist\Blender E-Learning.exe" (
  echo dist\Blender E-Learning.exe belum ada. Jalankan build.bat sekali dulu.
  pause
  exit /b 1
)
if exist "dist\app\elearning" rd /s /q "dist\app\elearning"
xcopy "%CD%\elearning" "%CD%\dist\app\elearning" /E /I /Y /Q >nul
if errorlevel 1 goto gagal
for /d /r "dist\app\elearning" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
rem Video hanya disalin kalau folder video di dist\ belum ada (agar video ganti-an tidak tertimpa)
if not exist "dist\assets\video" (
  xcopy "%CD%\assets\video" "%CD%\dist\assets\video" /E /I /Y /Q >nul
  if errorlevel 1 goto gagal
)
rem Video pembuka pelajaran murid (3 detik): selalu disalin (folder video lama tidak diganti)
if exist "assets\video\intro\intro.mp4" (
  if not exist "dist\assets\video\intro" mkdir "dist\assets\video\intro"
  copy /y "%CD%\assets\video\intro\intro.mp4" "%CD%\dist\assets\video\intro\intro.mp4" >nul
  if errorlevel 1 goto gagal
)
rem Logo layar login: disalin tiap update (kecil), supaya logo baru langsung dipakai
if exist "assets\logo.png" (
  if not exist "dist\assets" mkdir "dist\assets"
  copy /y "%CD%\assets\logo.png" "%CD%\dist\assets\logo.png" >nul
  if errorlevel 1 goto gagal
)
rem Pemutar bersuara + subtitle: salin mpv.py (dari paket python-mpv) ke dist\app, dan libmpv-2.dll ke dist\
rem Keduanya opsional: kalau tidak ada, pemutar cadangan (tanpa suara) dipakai.
if not exist "dist\app" mkdir "dist\app"
python -c "import importlib.util as u,shutil;shutil.copyfile(u.find_spec('mpv').origin,r'dist\app\mpv.py')" >nul 2>nul
if exist "libmpv-2.dll" copy /y "%CD%\libmpv-2.dll" "%CD%\dist\libmpv-2.dll" >nul
if /i not "%1"=="nopause" (
  echo.
  echo SELESAI. dist\ sudah diperbarui. Tidak perlu build ulang.
  pause
)
exit /b 0
:gagal
echo.
echo GAGAL menyalin. Pastikan aplikasi sudah ditutup lalu coba lagi.
if /i not "%1"=="nopause" pause
exit /b 1
