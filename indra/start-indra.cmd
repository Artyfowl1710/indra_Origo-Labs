@echo off
title INDRA System Starter
echo Starting INDRA One-Click System...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-indra.ps1"
if errorlevel 1 (
    echo.
    echo INDRA exited with error. Press any key to close...
    pause >nul
)
