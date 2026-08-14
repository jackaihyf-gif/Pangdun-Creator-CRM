@echo off
setlocal
cd /d "%~dp0"

set PYTHON_CMD=python
if exist backend\.venv\Scripts\python.exe set PYTHON_CMD=backend\.venv\Scripts\python.exe

%PYTHON_CMD% scripts\backup_database.py
if errorlevel 1 (
  echo.
  echo Backup failed. The original database was not changed.
  pause
  exit /b 1
)

echo.
echo Backup completed. It is safe to keep using CRM while this backup is created.
pause
