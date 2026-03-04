@echo off
setlocal

cd /d "%~dp0"

echo [1/3] Instalando dependencias...
py -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [2/3] Gerando executavel...
py -m PyInstaller --noconfirm --clean --windowed --onefile --name MacroPilot --collect-all customtkinter --collect-all pynput --hidden-import=models --hidden-import=recorder --hidden-import=player --hidden-import=storage --hidden-import=utils app.py
if errorlevel 1 goto :error

echo [3/3] Build concluido.
echo Executavel: %~dp0dist\MacroPilot.exe
exit /b 0

:error
echo Build falhou.
exit /b 1
