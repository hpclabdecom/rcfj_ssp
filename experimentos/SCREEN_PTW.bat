@echo off
setlocal
cd /d "%~dp0\.."
if not defined T set "T=8"
set "MAQ=i7"
echo %PROCESSOR_IDENTIFIER% | find /i "AuthenticAMD" >nul && set "MAQ=ryzen"
set /a T2=%T%/2
set "I=lcbrtu_3 lcbrtu_5 lcbrtu_8"
set "S=1 2 3"
set "O=results\%MAQ%"
if "%MAQ%"=="i7" (set "CMP=results\final\heur_lns_janela")
if "%MAQ%"=="ryzen" (set "CMP=results\ryzen\heur_lns_janela_4x2")
set "QM=--qualquer-maquina"
if "%1"=="B" goto B
if "%1"=="C" goto C
echo Usage: experimentos\SCREEN_PTW.bat B ^| C   (B = %T% replicas x 1 thread, C = %T2% replicas x 2 threads; three instances, seeds 1-3)
exit /b 2

:B
python experimentos\rcfjssp_ptw.py --replicas %T% --fios 1 --sementes %S% --instancias %I% %QM% --saida %O%\screen_ptw_%T%x1 --comparar %CMP%
python rcfjssp_audit.py --results %O%\screen_ptw_%T%x1
exit /b 0

:C
python experimentos\rcfjssp_ptw.py --replicas %T2% --fios 2 --sementes %S% --instancias %I% %QM% --saida %O%\screen_ptw_%T2%x2 --comparar %CMP%
python rcfjssp_audit.py --results %O%\screen_ptw_%T2%x2
exit /b 0
