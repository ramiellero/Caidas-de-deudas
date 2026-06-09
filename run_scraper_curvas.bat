@echo off
setlocal
set "WORKDIR=c:\Users\rellero\OneDrive - IRSACORP\Downloads\Dashboard Caídas de Deudas"
set "PYTHON=C:\Users\rellero\AppData\Local\Programs\Python\Python312\python.exe"

cd /d "%WORKDIR%"
"%PYTHON%" "%WORKDIR%\scraper_curvas.py" --commit
