@echo off
rem Hermes Agent Gateway - Messaging Platform Integration
cd /d C:\Users\Kaivalya\Downloads\SIH-26-main\SIH-26-main\SIH-26
set "HERMES_HOME=C:\Users\Kaivalya\Downloads\SIH-26-main\SIH-26-main\SIH-26"
set "PYTHONIOENCODING=utf-8"
set "HERMES_GATEWAY_DETACHED=1"
set "HERMES_SUPERVISED_CHILD=1"
set "VIRTUAL_ENV=C:\Users\Kaivalya\Downloads\SIH-26-main\SIH-26-main\venv"
set "PYTHONPATH=C:\Users\Kaivalya\Downloads\SIH-26-main\SIH-26-main\SIH-26\hermes-agent;%PYTHONPATH%"
C:\Users\Kaivalya\Downloads\SIH-26-main\SIH-26-main\venv\Scripts\python.exe -m hermes_cli.main gateway run
exit /b 0
