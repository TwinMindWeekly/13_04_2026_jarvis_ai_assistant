@echo off
title JARVIS AI Assistant - Stopping
echo.
echo  Stopping JARVIS AI Assistant...
echo.

REM Unload Ollama wikilink model from VRAM before killing backend
curl -s -X POST http://localhost:11434/api/generate -d "{\"model\":\"huihui_ai/llama3.2-abliterate:3b\",\"prompt\":\"\",\"keep_alive\":0}" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo  Ollama model unloaded from VRAM
) else (
    echo  Ollama not running or model not loaded — skipping
)

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
