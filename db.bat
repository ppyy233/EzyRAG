@echo off
chcp 65001 >nul
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\db_manage.py" %*
pause
