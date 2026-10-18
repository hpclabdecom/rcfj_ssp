@echo off
setlocal
cd /d "%~dp0\.."
set "MAQ=i7"
echo %PROCESSOR_IDENTIFIER% | find /i "AuthenticAMD" >nul && set "MAQ=ryzen"
if "%MAQ%"=="ryzen" (set "O=results\ryzen") else (set "O=results\i7")
if "%MAQ%"=="ryzen" (set "C8=results\ryzen\heur_lns_janela_4x2") else (set "C8=results\final\heur_lns_janela")
set "C16=results\ryzen\heur_lns_janela_8x2"
set "S10=1 2 3 4 5 6 7 8 9 10"
set "Q=--qualquer-maquina"
if "%1"=="" goto uso
if not exist results\final\calibracao\escolha.json (
  echo MISSING results\final\calibracao\escolha.json ^(calibration X9^).
  exit /b 2
)
echo machine=%MAQ%  output=%O%
goto %1

:TODOS
if "%MAQ%"=="ryzen" (set "SEQ=R1b P8 P16 R4 R3 R2 R4b R3b R2b") else (set "SEQ=P8 P8C")
for %%L in (%SEQ%) do (
  call echo ===== %%L  %%date%% %%time%% =====
  call "%~f0" %%L
)
echo TODOS done.
goto fim

:P8
python experimentos\rcfjssp_ptw.py --replicas 8 --fios 1 --sementes %S10% %Q% --saida %O%\ptw_8x1 --comparar %C8%
python rcfjssp_audit.py --results %O%\ptw_8x1
goto fim
:P8C
python experimentos\rcfjssp_ptw.py --replicas 4 --fios 2 --sementes %S10% %Q% --saida %O%\ptw_4x2 --comparar %C8%
python rcfjssp_audit.py --results %O%\ptw_4x2
goto fim
:P16
python experimentos\rcfjssp_ptw.py --replicas 16 --fios 1 --sementes %S10% %Q% --saida %O%\ptw_16x1 --comparar %C16%
python rcfjssp_audit.py --results %O%\ptw_16x1
goto fim

:R1b
call experimentos\RYZEN.bat R1b
goto fim
:R2
call experimentos\RYZEN.bat R2
goto fim
:R2b
call experimentos\RYZEN.bat R2b
goto fim
:R3
call experimentos\RYZEN.bat R3
goto fim
:R3b
call experimentos\RYZEN.bat R3b
goto fim
:R4
call experimentos\RYZEN.bat R4
goto fim
:R4b
call experimentos\RYZEN.bat R4b
goto fim

:status
for /d %%D in (%O%\*) do (
  for /f %%N in ('dir /b "%%D\*.json" 2^>nul ^| find /c ".json"') do echo %%D : %%N results
)
goto fim

:uso
echo Usage: experimentos\CAMPANHA_FINAL.bat TODOS ^| status ^| P8 ^| P8C ^| P16 ^| R1b ^| R2 ^| R2b ^| R3 ^| R3b ^| R4 ^| R4b
:fim
endlocal
