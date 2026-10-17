@echo off
rem Ambil versi terbaru dari GitHub, pasang (update.bat), lalu buka aplikasi. Klik dua kali saja.
cd /d "%~dp0"
echo Menutup aplikasi e-learning (kalau terbuka)...
taskkill /im "Blender E-Learning.exe" /f >nul 2>nul
echo Mengambil versi terbaru...
git fetch origin || goto gagal
git checkout claude/search-palette || goto gagal
git pull || goto gagal
git log --oneline -1
echo Memasang update...
echo.| call update.bat
echo Membuka aplikasi...
start "" "dist\Blender E-Learning.exe"
exit /b 0
:gagal
echo.
echo GAGAL. Foto layar ini dan kirim ke Claude.
pause
exit /b 1
