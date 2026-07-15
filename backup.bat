@echo off
setlocal
cd /d "%~dp0"

if not exist backend\data\kol_crm.db (
  echo Database not found: backend\data\kol_crm.db
  pause
  exit /b 1
)

if not exist backups mkdir backups
for /f %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmmss"') do set STAMP=%%a
set TARGET=backups\kol_crm_backup_%STAMP%.db

copy backend\data\kol_crm.db "%TARGET%" >nul
echo Backup created:
echo %CD%\%TARGET%
pause
