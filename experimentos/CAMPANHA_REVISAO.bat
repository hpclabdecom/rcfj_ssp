@echo off
setlocal
cd /d "%~dp0\.."
python experimentos\campanha_revisao.py %*
endlocal
