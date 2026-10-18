@echo off
setlocal
cd /d "%~dp0\.."
set "LOG=results\teste_cpo_%COMPUTERNAME%.log"
echo ==== %DATE% %TIME% ==== > "%LOG%"
echo --- CPLEX Studio instalado: >> "%LOG%"
dir /b "C:\Program Files\IBM\ILOG" >> "%LOG%" 2>&1
echo --- python: >> "%LOG%"
where python >> "%LOG%" 2>&1
python --version >> "%LOG%" 2>&1
python -c "import docplex" >> "%LOG%" 2>&1 || (
  echo --- instalando docplex --- >> "%LOG%"
  python -m pip install --user docplex >> "%LOG%" 2>&1
)
echo --- preflight: >> "%LOG%"
python experimentos\preflight_maquina.py --segundos-cpsat 10 --segundos-cpo 30 >> "%LOG%" 2>&1
echo ==== fim ==== >> "%LOG%"
type "%LOG%"
echo.
echo Pronto. Pode fechar esta janela.
pause
