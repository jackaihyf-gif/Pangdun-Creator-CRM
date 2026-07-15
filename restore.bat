@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Usage: restore.bat backups\kol_crm_backup_yyyy-mm-dd_HHmmss.db
  echo.
  echo Available backups:
  dir /b backups\*.db 2>nul
  pause
  exit /b 1
)

if not exist "%~1" (
  echo Backup file not found: %~1
  pause
  exit /b 1
)

set /p CONFIRM=Restore "%~1" to backend\data\kol_crm.db? Type YES to continue: 
if not "%CONFIRM%"=="YES" (
  echo Cancelled.
  pause
  exit /b 0
)

if not exist backups mkdir backups
if exist backend\data\kol_crm.db (
  for /f %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmmss"') do set STAMP=%%a
  copy backend\data\kol_crm.db "backups\before_restore_%STAMP%.db" >nul
)

if not exist backend\data mkdir backend\data
copy "%~1" backend\data\kol_crm.db >nul
echo Restore completed. Please restart CRM.
pause
