@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" grok_register_ttk.py cli
