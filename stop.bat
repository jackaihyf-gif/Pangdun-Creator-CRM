@echo off
setlocal
cd /d "%~dp0"
title Stop Pangdun CRM

powershell -NoProfile -Command "$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue ^| Select-Object -First 1; if (-not $listener) { exit 3 }; $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $listener.OwningProcess); if (-not $process.CommandLine -or $process.CommandLine -notmatch 'uvicorn.+backend\.app\.main') { exit 4 }; Stop-Process -Id $listener.OwningProcess -Force"

if errorlevel 4 (
  echo Port 8000 is used by another application. Nothing was stopped.
  pause
  exit /b 1
)
if errorlevel 3 (
  echo Pangdun CRM is not running.
  pause
  exit /b 0
)

echo Pangdun CRM has stopped.
timeout /t 2 >nul
