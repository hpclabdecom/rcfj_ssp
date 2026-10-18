@echo off
setlocal
cd /d "%~dp0\.."
set "O=results\ryzen"
set "S=1 2 3 4 5 6 7 8 9 10"
if "%1"=="" goto uso
goto %1

:TODOS8_16
for %%R in (R1 R1b R2 R2b R3 R3b R4 R4b) do (
  call echo ===== %%R  %%date%% %%time%% =====
  call "%~f0" %%R
)
echo TODOS8_16 FIM. Traga a pasta %O% inteira.
goto fim

:TODOS8
:R1
python experimentos\rcfjssp_lns.py --viz janela --walkers 4 --fios 2 --sementes %S% --saida %O%\heur_lns_janela_4x2 --qualquer-maquina
python rcfjssp_audit.py --results %O%\heur_lns_janela_4x2
python experimentos\rcfjssp_lns.py --relatorio --saida %O%\heur_lns_janela_4x2
if /i "%1"=="R1" goto fim
:R2
python experimentos\x10_reservatorio.py --workers 8 --saida %O%\reservatorio_w8_TALNS --qualquer-maquina
python rcfjssp_audit.py --results %O%\reservatorio_w8_TALNS
if /i "%1"=="R2" goto fim
:R3
python experimentos\rcfjssp_cpo.py --exp 4 --limit 1800 --workers 8 --out %O%\cpo_exp4_w8 --qualquer-maquina
python rcfjssp_audit.py --results %O%\cpo_exp4_w8
if /i "%1"=="R3" goto fim
:R4
python experimentos\rcfjssp_final.py --braco relato --workers 8 --limite 1800 --sementes 1 --saida %O% --qualquer-maquina
python rcfjssp_audit.py --results %O%\relato_w8_1800
goto fim

:TODOS16
:R1b
python experimentos\rcfjssp_lns.py --viz janela --walkers 8 --fios 2 --sementes %S% --saida %O%\heur_lns_janela_8x2 --qualquer-maquina
python rcfjssp_audit.py --results %O%\heur_lns_janela_8x2
python experimentos\rcfjssp_lns.py --relatorio --saida %O%\heur_lns_janela_8x2
if /i "%1"=="R1b" goto fim
:R2b
python experimentos\x10_reservatorio.py --workers 16 --saida %O%\reservatorio_w16_TALNS --qualquer-maquina
python rcfjssp_audit.py --results %O%\reservatorio_w16_TALNS
if /i "%1"=="R2b" goto fim
:R3b
python experimentos\rcfjssp_cpo.py --exp 4 --limit 1800 --workers 16 --out %O%\cpo_exp4_w16 --qualquer-maquina
python rcfjssp_audit.py --results %O%\cpo_exp4_w16
if /i "%1"=="R3b" goto fim
:R4b
python experimentos\rcfjssp_final.py --braco relato --workers 16 --limite 1800 --sementes 1 --saida %O% --qualquer-maquina
python rcfjssp_audit.py --results %O%\relato_w16_1800
goto fim

:uso
echo Uso: experimentos\RYZEN.bat R1^|R1b^|R2^|R2b^|R3^|R3b^|R4^|R4b^|TODOS8^|TODOS16^|TODOS8_16
echo Ordem: R1, R1b, R2, R2b, R3, R3b, R4, R4b
:fim
endlocal
