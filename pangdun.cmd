@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PANGDUN_ROOT=%~dp0"
"%PANGDUN_ROOT%backend\.venv\Scripts\python.exe" "%PANGDUN_ROOT%cli\pangdun.py" %*
