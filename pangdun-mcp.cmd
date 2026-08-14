@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PANGDUN_ROOT=%~dp0"
cd /d "%PANGDUN_ROOT%"
"%PANGDUN_ROOT%backend\.venv\Scripts\python.exe" -m pangdun_mcp.server
