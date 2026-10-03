@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto erro
.venv\Scripts\python.exe -m pip install -r server\requirements.txt
if errorlevel 1 goto erro
echo Abra http://127.0.0.1:8766/#euler-demo no navegador.
.venv\Scripts\python.exe server\app.py %*
pause
exit /b
:erro
echo Nao foi possivel preparar o ambiente. Verifique Python 3.11 ou superior e sua conexao.
pause
exit /b 1
