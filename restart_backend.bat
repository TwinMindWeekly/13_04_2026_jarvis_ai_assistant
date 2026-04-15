@echo off
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
cd /d D:\workspaces\projects\TwinMindWeekly\13_04_2026_jarvis_ai_assistant\backend
venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
