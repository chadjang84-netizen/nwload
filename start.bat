@echo off
setlocal EnableDelayedExpansion

pushd "%~dp0"
set ROOT=%CD%
set BACKEND=%ROOT%\cell_traffic_optimizer
set FRONTEND=%ROOT%\frontend

echo =============================================
echo   Cell Traffic Optimizer
echo =============================================

echo [Cleanup] Stopping old servers...
powershell -NoProfile -Command "Get-Process python -EA SilentlyContinue | Where-Object {$_.MainWindowTitle -eq ''} | Stop-Process -Force"
powershell -NoProfile -Command "Get-Process node -EA SilentlyContinue | Where-Object {$_.CommandLine -like '*vite*'} | Stop-Process -Force"
ping -n 3 127.0.0.1 >nul

if not exist "%BACKEND%\.venv\Scripts\python.exe" (
    echo [Backend] venv not found - running uv sync...
    pushd "%BACKEND%"
    uv sync --native-tls
    if errorlevel 1 ( echo [ERROR] uv sync failed & pause & popd & exit /b 1 )
    popd
)

set BE_SCRIPT=%TEMP%\cto_backend.bat
(
echo @echo off
echo pushd "%BACKEND%"
echo .venv\Scripts\python.exe -m uvicorn cell_traffic_optimizer.server.app:app --host 0.0.0.0 --port 8000
echo pause
) > "%BE_SCRIPT%"

echo [Backend] Starting... http://localhost:8000
start "CTO-Backend" cmd /c "%BE_SCRIPT%"

echo [Backend] Waiting...
set /a cnt=0
:wait_be
ping -n 2 127.0.0.1 >nul
set /a cnt+=1
powershell -NoProfile -Command "try{Invoke-WebRequest http://localhost:8000/api/config -UseBasicParsing -TimeoutSec 1|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 goto be_ok
if !cnt! geq 30 ( echo [ERROR] Backend not responding & pause & exit /b 1 )
goto wait_be
:be_ok
echo [Backend] Ready

if not exist "%FRONTEND%\node_modules" (
    echo [Frontend] Running npm install...
    pushd "%FRONTEND%"
    call npm install
    if errorlevel 1 ( echo [ERROR] npm install failed & pause & popd & exit /b 1 )
    popd
)

set FE_SCRIPT=%TEMP%\cto_frontend.bat
(
echo @echo off
echo pushd "%FRONTEND%"
echo npm run dev
echo pause
) > "%FE_SCRIPT%"

echo [Frontend] Starting... http://localhost:5173
start "CTO-Frontend" cmd /c "%FE_SCRIPT%"

echo [Frontend] Waiting...
set /a cnt=0
:wait_fe
ping -n 2 127.0.0.1 >nul
set /a cnt+=1
powershell -NoProfile -Command "try{Invoke-WebRequest http://localhost:5173 -UseBasicParsing -TimeoutSec 1|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 goto fe_ok
if !cnt! geq 30 ( echo [WARN] Open http://localhost:5173 manually & goto open_browser )
goto wait_fe
:fe_ok
echo [Frontend] Ready

:open_browser
start http://localhost:5173

echo =============================================
echo   Backend : http://localhost:8000
echo   Docs    : http://localhost:8000/docs
echo   Frontend: http://localhost:5173
echo   Close CTO-Backend / CTO-Frontend to stop.
echo =============================================
pause
popd
endlocal
