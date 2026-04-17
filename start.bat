@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title JARVIS AI Assistant - Startup
echo.
echo  ======================================
echo    JARVIS AI Assistant - Starting...
echo  ======================================
echo.

set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"
set "VENV_DIR=%BACKEND_DIR%\venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
set "UVICORN_EXE=%VENV_DIR%\Scripts\uvicorn.exe"

REM === Step 1: Venv ===
echo [1/6] Checking Python venv...
if exist "%PYTHON_EXE%" (
    echo        Venv OK
    goto :step3
)

echo        Venv not found, creating...
py -3 -m venv "%VENV_DIR%"
if !ERRORLEVEL! neq 0 (
    echo  [ERROR] Failed to create venv. Install Python 3.11+ from https://python.org
    goto :fail
)
echo        Venv created

:step3
REM === Step 3: Backend deps ===
echo [2/6] Checking backend dependencies...
"%PIP_EXE%" show fastapi >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo        Installing backend dependencies [first run downloads ~3 GB, can take 10-30 min on slow networks]...
    echo        Progress will be shown below. Do NOT close this window.
    echo.
    "%PIP_EXE%" install -r "%BACKEND_DIR%\requirements.txt" --extra-index-url https://pnnbao97.github.io/llama-cpp-python-v0.3.16/cpu/ --progress-bar on --disable-pip-version-check
    if !ERRORLEVEL! neq 0 (
        echo  [ERROR] pip install failed
        goto :fail
    )
    echo        Installed
) else (
    echo        OK
)

REM === Step 4: .env ===
echo [3/6] Checking .env...
if not exist "%BACKEND_DIR%\.env" (
    copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul 2>&1
    echo        Created .env - edit backend\.env to add your API keys!
) else (
    echo        OK
)

REM === Step 5: Frontend deps ===
echo [4/6] Checking frontend...
node --version >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo  [ERROR] Node.js not found. Install from https://nodejs.org
    goto :fail
)
if not exist "%FRONTEND_DIR%\node_modules" (
    echo        Installing frontend dependencies [may take 2-5 min]...
    echo.
    pushd "%FRONTEND_DIR%"
    call npm install --progress=true
    if !ERRORLEVEL! neq 0 (
        popd
        echo  [ERROR] npm install failed
        goto :fail
    )
    popd
    echo        Installed
) else (
    echo        OK
)

REM === Step 6: Kill ports ===
echo [5/6] Freeing ports...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
    echo        Killed PID %%a on port 8000
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
    echo        Killed PID %%a on port 5173
)
echo        OK

REM === Launch using Windows Terminal split panes ===
echo [6/6] Launching...

REM Check if Windows Terminal (wt.exe) is available
where wt >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo        Using Windows Terminal split panes
    wt new-tab --title "JARVIS Backend" -d "%BACKEND_DIR%" cmd /k "%UVICORN_EXE% app.main:app --reload --host 0.0.0.0 --port 8000" ; split-pane --title "JARVIS Frontend" -d "%FRONTEND_DIR%" cmd /k "npx vite --port 5173"
) else (
    echo        Using separate windows
    start "JARVIS Backend" cmd /k "cd /d %BACKEND_DIR% && %UVICORN_EXE% app.main:app --reload --host 0.0.0.0 --port 8000"
    start "JARVIS Frontend" cmd /k "cd /d %FRONTEND_DIR% && npx vite --port 5173"
)

timeout /t 5 /nobreak >nul

echo.
echo  ======================================
echo    JARVIS AI Assistant is running!
echo  ======================================
echo.
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:5173
echo  API Docs: http://localhost:8000/docs
echo.

start "" http://localhost:5173

echo  Press any key to close this window...
pause >nul
goto :eof

:fail
echo.
echo  Startup failed. See error above.
pause
exit /b 1
