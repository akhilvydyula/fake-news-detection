@echo off
REM News Trust Platform — forwards to run.ps1 (serve, setup, stop, restart, test, ...)
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
endlocal
