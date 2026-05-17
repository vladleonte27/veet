@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo [build] no .venv found. Run start.bat first to bootstrap.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

set TARGET=%1
if "%TARGET%"=="" set TARGET=cpu

if /i "%TARGET%"=="gpu" (
    set VEET_BUILD_GPU=1
    set LABEL=GPU
) else (
    set VEET_BUILD_GPU=0
    set LABEL=CPU
)

echo [build] target: !LABEL!
echo [build] cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo [build] running PyInstaller...
pyinstaller --clean --noconfirm veet.spec || goto :err

echo [build] packaging portable ZIP...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Veet\*' -DestinationPath 'dist\Veet-Portable-!LABEL!.zip' -Force" || goto :err

echo.
echo [build] DONE (!LABEL!).
echo   folder build:  %CD%\dist\Veet\
echo   portable zip:  %CD%\dist\Veet-Portable-!LABEL!.zip
echo.
echo To build the other variant:  build.bat gpu    or    build.bat cpu
echo To make an installer:        iscc /DBuildTarget=!LABEL! packaging\installer.iss
goto :eof

:err
echo [build] FAILED.
exit /b 1
