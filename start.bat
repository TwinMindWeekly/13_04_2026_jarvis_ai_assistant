@echo off
chcp 65001 >nul 2>&1
title JARVIS AI Assistant - Startup
echo.
echo  ======================================
echo    JARVIS AI Assistant - Starting...
echo  ======================================
echo.

REM === Configuration ===
set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"
set "VENV_DIR=%BACKEND_DIR%\venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
set "UVICORN_EXE=%VENV_DIR%\Scripts\uvicorn.exe"

REM === Step 1: Find Python ===
echo [1/6] Checking Python installation...
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "SYS_PYTHON=python"
    goto :found_python
)
where python3 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "SYS_PYTHON=python3"
    goto :found_python
)
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "SYS_PYTHON=py -3"
    goto :found_python
)
REM Check common install paths
if exist "C:\Python311\python.exe" (
    set "SYS_PYTHON=C:\Python311\python.exe"
    goto :found_python
)
if exist "C:\Python312\python.exe" (
    set "SYS_PYTHON=C:\Python312\python.exe"
    goto :found_python
)
if exist "C:\Python313\python.exe" (
    set "SYS_PYTHON=C:\Python313\python.exe"
    goto :found_python
)
REM Try existing venv from sibling project
for /d %%D in ("%PROJECT_DIR%..\*") do (
    if exist "%%D\backend\venv\Scripts\python.exe" (
        set "SYS_PYTHON=%%D\backend\venv\Scripts\python.exe"
        goto :found_python
    )
)
echo [ERROR] Python 3.11+ not found. Please install Python from https://python.org
pause
exit /b 1

:found_python
echo        Found: %SYS_PYTHON%

REM === Step 2: Create venv if needed ===
echo [2/6] Checking Python virtual environment...
if not exist "%PYTHON_EXE%" (
    echo        Creating venv...
    %SYS_PYTHON% -m venv "%VENV_DIR%"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
    echo        Venv created at %VENV_DIR%
) else (
    echo        Venv exists
)

REM === Step 3: Install backend dependencies ===
echo [3/6] Checking backend dependencies...
"%PIP_EXE%" show fastapi >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo        Installing backend dependencies (this may take a few minutes)...
    "%PIP_EXE%" install -r "%BACKEND_DIR%\requirements.txt" --quiet
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install backend dependencies
        pause
        exit /b 1
    )
    echo        Dependencies installed
) else (
    echo        Dependencies already installed
)

REM === Step 4: Check .env file ===
echo [4/6] Checking backend .env configuration...
if not exist "%BACKEND_DIR%\.env" (
    echo        Creating .env from .env.example...
    copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
    echo.
    echo  ==========================================
    echo   WARNING: .env created with placeholder keys
    echo   Edit backend\.env and add your API keys:
    echo     - OPENAI_API_KEY
    echo     - GOOGLE_API_KEY
    echo     - ANTHROPIC_API_KEY
    echo  ==========================================
    echo.
) else (
    echo        .env exists
)

REM === Step 5: Check Node.js and install frontend ===
echo [5/6] Checking frontend dependencies...
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js not found. Please install from https://nodejs.org
    pause
    exit /b 1
)
if not exist "%FRONTEND_DIR%\node_modules" (
    echo        Installing frontend dependencies...
    cd /d "%FRONTEND_DIR%"
    npm install --silent
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install frontend dependencies
        pause
        exit /b 1
    )
    cd /d "%PROJECT_DIR%"
    echo        Dependencies installed
) else (
    echo        Dependencies already installed
)

REM === Step 6: Kill existing processes on ports 8000 and 5173 ===
echo [6/6] Checking for port conflicts...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo        Killing process on port 8000 (PID: %%a)
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    echo        Killing process on port 5173 (PID: %%a)
    taskkill /f /pid %%a >nul 2>&1
)

REM === Launch Backend ===
echo.
echo  Starting Backend (FastAPI) on http://localhost:8000 ...
start "JARVIS Backend" cmd /k "cd /d "%BACKEND_DIR%" && "%UVICORN_EXE%" app.main:app --reload --host 0.0.0.0 --port 8000"

REM Wait for backend to be ready
echo  Waiting for backend to start...
timeout /t 3 /nobreak >nul

REM === Launch Frontend ===
echo  Starting Frontend (React) on http://localhost:5173 ...
start "JARVIS Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

REM Wait for frontend
timeout /t 3 /nobreak >nul

REM === Open browser ===
echo.
echo  ======================================
echo    JARVIS AI Assistant is running!
echo    Opening http://localhost:5173 ...
echo  ======================================
echo.
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:5173
echo  API Docs: http://localhost:8000/docs
echo.
echo  Press any key to open in browser...
pause >nul
start http://localhost:5173
