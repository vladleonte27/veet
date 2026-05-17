@echo off
setlocal
cd /d "%~dp0..\website"

echo [deploy] pushing site changes to Vercel ...
call vercel --prod --yes || (
  echo [deploy] FAILED.
  exit /b 1
)
echo.
echo [deploy] live at https://veet.space
