@echo off
title Stop INDRA Services
echo Stopping all INDRA services...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-indra.ps1"
echo.
pause
