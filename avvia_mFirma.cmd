@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "MFIRMA_PYTHON=.venv\Scripts\python.exe"
set "MFIRMA_PYTHONW=.venv\Scripts\pythonw.exe"

rem Al primo avvio crea l'ambiente; lo ripara anche se manca un modulo.
if not exist "%MFIRMA_PYTHON%" goto install
"%MFIRMA_PYTHON%" -c "import mfirma, pyhanko, pypdf, reportlab, PySide6, qfluentwidgets" >nul 2>&1
if errorlevel 1 goto install
goto start_app

:install
echo Preparazione di mFirma al primo avvio...
call "%~dp0installa_mFirma.cmd" --from-launcher
if errorlevel 1 (
  echo.
  echo Installazione non completata. Leggi il messaggio qui sopra.
  pause
  exit /b 1
)

:start_app
if not exist "%MFIRMA_PYTHONW%" (
  echo Ambiente Python incompleto: manca %MFIRMA_PYTHONW%.
  echo Esegui installa_mFirma.cmd per ripararlo.
  pause
  exit /b 1
)
start "mFirma" "%MFIRMA_PYTHONW%" -m mfirma
