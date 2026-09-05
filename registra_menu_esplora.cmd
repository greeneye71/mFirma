@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\registra_menu_esplora.ps1"
if errorlevel 1 (
  echo.
  echo Registrazione non completata.
  pause
  exit /b 1
)

echo.
echo Comando "Firma PDF con mFirma" registrato per l'utente corrente.
echo Su Windows 11 puo comparire sotto "Mostra altre opzioni".
pause
exit /b 0
