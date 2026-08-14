@echo off
setlocal
cd /d "%~dp0"

if /I "%~1"=="--worker" goto :run
if /I "%~1"=="--foreground" goto :run

start "" wscript.exe "%~dp0start-hidden.vbs"
exit /b 0

:run
title Pangdun CRM
echo.
echo === Pangdun KOL CRM ===

if /I "%~1"=="--worker" if not exist backend\data\kol_crm.db exit /b 20

powershell -NoProfile -Command "try { if ((Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>nul
if not errorlevel 1 exit /b 0

set PYTHON_CMD=
where python >nul 2>nul
if not errorlevel 1 set PYTHON_CMD=python
if not defined PYTHON_CMD if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set PYTHON_CMD="%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not defined PYTHON_CMD (
  echo Python was not found. Please install Python 3.11+ and add it to PATH.
  pause
  exit /b 1
)

if not exist backend\data mkdir backend\data
if not exist imports mkdir imports
if not exist uploads mkdir uploads
if not exist backups mkdir backups

if exist backend\data\agent.env (
  for /f "usebackq tokens=1,* delims==" %%A in ("backend\data\agent.env") do set "%%A=%%B"
)

if not exist backend\.venv (
  echo Creating Python virtual environment...
  %PYTHON_CMD% -m venv backend\.venv
)

call backend\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r backend\requirements.txt

where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Please install Node.js LTS.
  pause
  exit /b 1
)

cd frontend
if not exist node_modules (
  echo Installing frontend dependencies...
  call npm.cmd install --cache .npm-cache
)
echo Building frontend...
call npm.cmd run build
if errorlevel 1 (
  pause
  exit /b 1
)
cd ..

echo Checking admin account...
python -m backend.app.create_admin

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R /C:"IPv4.*192\\." /C:"IPv4.*10\\." /C:"IPv4.*172\\."') do (
  set LAN_IP=%%a
  goto :gotip
)
:gotip
set LAN_IP=%LAN_IP: =%

echo.
echo Local access: http://127.0.0.1:8000
if defined LAN_IP echo LAN access:   http://%LAN_IP%:8000
echo.
if /I "%~1"=="--foreground" echo Keep this window open while using CRM.
echo.

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
if /I "%~1"=="--foreground" pause
