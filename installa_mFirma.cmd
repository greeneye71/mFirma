@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Installazione mFirma

echo ========================================
echo   Installazione / riparazione mFirma
echo ========================================
echo.

set "MFIRMA_BASE_PYTHON="

rem Il Python Launcher sceglie la versione Python 3 piu recente installata.
where py.exe >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import sys, struct; raise SystemExit(0 if sys.version_info >= (3, 11) and struct.calcsize('P') * 8 == 64 else 1)" >nul 2>&1
  if not errorlevel 1 set "MFIRMA_BASE_PYTHON=py -3"
)

if not defined MFIRMA_BASE_PYTHON (
  where python.exe >nul 2>&1
  if not errorlevel 1 (
    python -c "import sys, struct; raise SystemExit(0 if sys.version_info >= (3, 11) and struct.calcsize('P') * 8 == 64 else 1)" >nul 2>&1
    if not errorlevel 1 set "MFIRMA_BASE_PYTHON=python"
  )
)

if not defined MFIRMA_BASE_PYTHON goto python_missing

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creazione dell'ambiente Python locale .venv...
  %MFIRMA_BASE_PYTHON% -m venv ".venv"
  if errorlevel 1 goto install_error
) else (
  echo [1/3] Ambiente Python locale gia presente.
)

echo [2/3] Installazione delle dipendenze...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "requirements.lock"
if errorlevel 1 goto install_error

echo [3/3] Installazione di mFirma...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -e . --no-deps
if errorlevel 1 goto install_error

".venv\Scripts\python.exe" -c "import mfirma, pyhanko, pypdf, reportlab, PySide6, qfluentwidgets"
if errorlevel 1 goto install_error

echo.
echo Installazione completata correttamente.
if /i not "%~1"=="--from-launcher" pause
exit /b 0

:python_missing
echo ERRORE: serve Python 3.11 o successivo a 64 bit.
echo.
echo Installa Python 3.13 con questo comando in PowerShell:
echo   winget install --id Python.Python.3.13 -e
echo.
echo Poi chiudi e riapri questa finestra ed esegui di nuovo
echo installa_mFirma.cmd oppure avvia_mFirma.cmd.
echo.
if /i not "%~1"=="--from-launcher" pause
exit /b 2

:install_error
echo.
echo ERRORE: installazione non riuscita.
echo Controlla la connessione Internet e riprova eseguendo
echo installa_mFirma.cmd. L'ambiente esistente verra riparato.
echo.
if /i not "%~1"=="--from-launcher" pause
exit /b 1
