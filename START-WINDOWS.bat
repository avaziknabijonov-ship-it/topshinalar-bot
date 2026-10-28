@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYRUN=py -3"
py -3 --version >nul 2>&1
if not errorlevel 1 goto python_ready
set "PYRUN=python"
python --version >nul 2>&1
if not errorlevel 1 goto python_ready
echo Python 3.11+ kerak. https://www.python.org/downloads/windows/
echo O'rnatishda Add Python to PATH ni belgilang, keyin bu faylni yana oching.
pause
exit /b 1
:python_ready
if exist ".venv\Scripts\python.exe" goto deps
%PYRUN% -m venv .venv
if errorlevel 1 goto failed
:deps
if exist ".venv\topshinalar-v1-deps-ok" goto run
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
type nul > ".venv\topshinalar-v1-deps-ok"
:run
".venv\Scripts\python.exe" start_local.py %*
pause
exit /b
:failed
echo O'rnatish bajarilmadi. Internet va Python sozlamalarini tekshiring.
pause
exit /b 1
