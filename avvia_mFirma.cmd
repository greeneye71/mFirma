@echo off
setlocal
set "MFIRMA_PYTHON=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%MFIRMA_PYTHON%" (
  echo Ambiente Python non trovato. Segui le istruzioni in README.md.
  pause
  exit /b 1
)
start "mFirma" "%MFIRMA_PYTHON%" -m mfirma

