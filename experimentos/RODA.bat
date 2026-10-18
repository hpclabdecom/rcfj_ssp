@echo off
setlocal
set "CPO_EXE="
set "W=8"
cd /d "%~dp0\.."
if "%1"=="" goto uso
goto %1

:PRE
python experimentos\preflight_maquina.py --workers %W%
goto fim

:X0
for /d %%D in (results\final\*) do python rcfjssp_audit.py --results %%D
goto fim

:X1
python experimentos\rcfjssp_final.py --braco relato --workers %W% --limite 1800 --sementes 1 2 3 4 5 6 7 8 9 10
goto X1fim
:X1a
python experimentos\rcfjssp_final.py --braco relato --workers %W% --limite 1800 --sementes 1 2 3 4 5
goto X1fim
:X1b
python experimentos\rcfjssp_final.py --braco relato --workers %W% --limite 1800 --sementes 6 7 8 9 10
:X1fim
python rcfjssp_audit.py --results results\final\relato_w%W%_1800
goto fim

:X4
python experimentos\rcfjssp_valida_i7.py --workers %W% --saida results\final\validacao
python rcfjssp_audit.py --results results\final\validacao
python rcfjssp_campaign.py --report
goto fim

:X6
:X6a
python experimentos\rcfjssp_cpo.py --exp 1 --check --permite-community --out results\final\cpo_exp123
python experimentos\rcfjssp_cpo.py --exp 2 --check --permite-community --out results\final\cpo_exp123
python experimentos\rcfjssp_cpo.py --exp 3 --check --permite-community --out results\final\cpo_exp123
python rcfjssp_audit.py --results results\final\cpo_exp123
if /i "%1"=="X6a" goto fim
:X6b
python experimentos\rcfjssp_cpo.py --exp 4 --limit 1800 --out results\final\cpo_exp4
python rcfjssp_audit.py --results results\final\cpo_exp4
goto fim

:X9
python experimentos\instancias_calibracao.py
python experimentos\calibra_lns.py --segundos 60 --saida results\final\calibracao
python experimentos\calibra_lns.py --resumo --saida results\final\calibracao
goto fim

:X8b
python experimentos\rcfjssp_lns.py --sementes 1 2 3 4 5 6 7 8 9 10 --viz janela --saida results\final\heur_lns_janela
python rcfjssp_audit.py --results results\final\heur_lns_janela
python experimentos\rcfjssp_lns.py --relatorio --saida results\final\heur_lns_janela
goto fim

:X10
python experimentos\x10_reservatorio.py --workers %W%
python rcfjssp_audit.py --results results\final\reservatorio_w8_TALNS
goto fim

:uso
echo Usage: experimentos\RODA.bat PRE^|X0^|X1^|X1a^|X1b^|X4^|X6^|X6a^|X6b^|X9^|X8b^|X10
echo Order used on the i7: X4, X6a, X1, X6b, X9, X8b, X10
:fim
endlocal
