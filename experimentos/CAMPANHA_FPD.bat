@echo off
setlocal
cd /d "%~dp0\.."
rem Combined control F+PD: PT-W 8x1 with a fixed ladder (no adaptation) and alpha_E = 0 (energy = makespan);
rem exchanges, Metropolis acceptance and slot-dependent kernels unchanged. Ryzen only, on the five
rem benchmark instances whose best known value is above the published lower bound (exploratory control).
set "O=results\ryzen"
python experimentos\rcfjssp_ptw_controls.py --braco F --alpha-e 0 --replicas 8 --fios 1 --instancias lcbrtu_0 lcbrtu_3 lcbrtu_5 lcbrtu_7 lcbrtu_8 --sementes 1 2 3 4 5 6 7 8 9 10 --saida %O%\ptw_8x1_FPD_escada_fixa_alpha0 --comparar %O%\ptw_8x1 --qualquer-maquina
python rcfjssp_audit.py --results %O%\ptw_8x1_FPD_escada_fixa_alpha0
