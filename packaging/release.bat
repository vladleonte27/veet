@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0.."

if "%~1"=="" (
  echo Usage: release.bat ^<version^>
  echo Example: release.bat 0.1.1
  exit /b 1
)
set VERSION=%~1

echo.
echo === Veet release v!VERSION! ===
echo.

REM ── 1. Bump version in installer.iss ────────────────────────
echo [1/6] bumping version to !VERSION! ...
powershell -NoProfile -Command "(Get-Content packaging\installer.iss) -replace '#define MyAppVersion\s+\".*\"', '#define MyAppVersion   \"!VERSION!\"' | Set-Content packaging\installer.iss"

REM ── 2. Build .exe ───────────────────────────────────────────
echo [2/6] building Windows .exe ...
call packaging\build.bat cpu || goto :err

REM ── 3. Compile installer ────────────────────────────────────
echo [3/6] compiling installer ...
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "!ISCC!" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "!ISCC!" (
  echo [release] ISCC.exe not found — install Inno Setup 6.
  exit /b 1
)
"!ISCC!" /DBuildTarget=CPU packaging\installer.iss || goto :err

REM ── 4. Rename installer for permalink ───────────────────────
echo [4/6] preparing release asset ...
copy /Y "dist\installer\Veet-Setup-CPU-!VERSION!.exe" "dist\installer\Veet-Setup.exe" >nul

REM ── 5. Push to GitHub Releases ──────────────────────────────
echo [5/6] cutting GitHub release v!VERSION! ...
gh release view v!VERSION! >nul 2>&1
if !errorlevel! equ 0 (
  echo   release v!VERSION! exists — replacing asset
  gh release upload v!VERSION! "dist\installer\Veet-Setup.exe" --clobber || goto :err
) else (
  gh release create v!VERSION! "dist\installer\Veet-Setup.exe" ^
    --title "Veet v!VERSION!" ^
    --notes "Veet voice-typing for Windows — local Whisper, hold Alt+Shift to talk." ^
    --latest || goto :err
)

REM ── 6. Deploy site to Vercel ────────────────────────────────
echo [6/6] deploying site to Vercel ...
pushd website
call vercel --prod --yes || (popd & goto :err)
popd

echo.
echo === DONE v!VERSION! ===
echo Release:  https://github.com/vladleonte27/veet/releases/tag/v!VERSION!
echo Site:     https://veet.space
goto :eof

:err
echo.
echo [release] FAILED.
exit /b 1
