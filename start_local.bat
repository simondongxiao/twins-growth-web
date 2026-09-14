@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (py -3 tools\serve.py) else (python tools\serve.py)
pause
