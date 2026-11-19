@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python update.py
pause