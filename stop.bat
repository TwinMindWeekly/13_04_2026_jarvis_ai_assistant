@echo off
title JARVIS AI Assistant - Stopping
echo.
echo  Stopping JARVIS AI Assistant...
echo.

REM Kill backend (uvicorn on port 8000)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo  Stopping backend (PID: %%a)
    taskkill /f /pid %%a >nul 2>&1
)

REM Kill frontend (node on port 5173)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    echo  Stopping frontend (PID: %%a)
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo  All services stopped.
timeout /t 2 /nobreak >nul
