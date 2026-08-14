@echo off
setlocal
cd /d "%~dp0"

set PYTHON_CMD=python
if exist backend\.venv\Scripts\python.exe set PYTHON_CMD=backend\.venv\Scripts\python.exe

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

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 1 }" >nul 2>nul
if errorlevel 1 (
  echo CRM is still running on port 8000. Close it before restoring a database.
  pause
  exit /b 1
)

%PYTHON_CMD% scripts\backup_database.py --verify "%~1"
if errorlevel 1 (
  echo The selected backup did not pass SQLite integrity verification.
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
  %PYTHON_CMD% scripts\backup_database.py
  if errorlevel 1 (
    echo Failed to protect the current database. Restore cancelled.
    pause
    exit /b 1
  )
)

if not exist backend\data mkdir backend\data
copy "%~1" backend\data\kol_crm.db >nul
%PYTHON_CMD% scripts\backup_database.py --verify backend\data\kol_crm.db
if errorlevel 1 (
  echo Restore copy failed integrity verification. Do not start CRM; restore the safety backup from the backups folder.
  pause
  exit /b 1
)
echo Restore completed. Please restart CRM.
pause
