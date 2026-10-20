@echo off
setlocal enabledelayedexpansion

:: Ensure working directory is always the script directory (project root)
cd /d "%~dp0"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

echo =======================================================
echo          Starting Naughty or not (Sanction checK)      
echo =======================================================

echo [1/4] Checking Docker status...
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Docker daemon is not running. Starting Docker Desktop...
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    ) else if exist "%LocalAppData%\Programs\Docker\Docker\Docker Desktop.exe" (
        start "" "%LocalAppData%\Programs\Docker\Docker\Docker Desktop.exe"
    )
    set /a WAIT_DOCKER=0
    :wait_docker_loop
    timeout /t 3 /nobreak >nul
    docker info >nul 2>&1
    if %ERRORLEVEL% EQU 0 goto docker_ready
    set /a WAIT_DOCKER+=3
    if !WAIT_DOCKER! GEQ 180 (
        echo [ERROR] Timed out waiting for Docker Desktop to start.
        pause
        exit /b 1
    )
    goto wait_docker_loop
)

:docker_ready
echo Docker is running.

echo [2/4] Starting Watchman container...
docker compose up -d

echo [3/4] Waiting for Watchman service health check (http://127.0.0.1:8084/ping)...
set /a WAIT_WATCHMAN=0
:wait_watchman_loop
curl -s http://127.0.0.1:8084/ping | findstr "PONG" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Watchman service is healthy and ready.
    goto launch_app
)
timeout /t 2 /nobreak >nul
set /a WAIT_WATCHMAN+=2
if !WAIT_WATCHMAN! GEQ 180 (
    echo [ERROR] Timed out after 3 minutes waiting for Watchman service.
    echo Please check container logs with 'docker compose logs watchman'.
    pause
    exit /b 1
)
goto wait_watchman_loop

:launch_app
echo [4/4] Launching Sanction checK Streamlit interface at http://127.0.0.1:8501...
start http://127.0.0.1:8501
call .venv\Scripts\activate.bat
streamlit run app/main.py --server.port 8501 --server.address 127.0.0.1
