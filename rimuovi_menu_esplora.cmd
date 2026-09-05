@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\rimuovi_menu_esplora.ps1"
if errorlevel 1 (
  echo.
  echo Rimozione non completata.
  pause
  exit /b 1
)

echo.
echo Comando di mFirma rimosso da Esplora file.
pause
exit /b 0
