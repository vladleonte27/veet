@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo [veet] setting up virtual environment...
    python -m venv .venv || goto :err
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt || goto :err
)

start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0veet.py"
goto :eof

:err
echo [veet] setup failed.
pause
