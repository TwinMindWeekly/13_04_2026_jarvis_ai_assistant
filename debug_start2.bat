@echo on
set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"
set "UVICORN_EXE=%BACKEND_DIR%\venv\Scripts\uvicorn.exe"
set "PIP_EXE=%BACKEND_DIR%\venv\Scripts\pip.exe"

echo === Step 3: pip show fastapi ===
"%PIP_EXE%" show fastapi >nul 2>&1
echo pip show fastapi ERRORLEVEL=%ERRORLEVEL%

echo === Step 4: .env check ===
if exist "%BACKEND_DIR%\.env" (echo .env exists) else (echo .env MISSING)

echo === Step 5: node_modules check ===
if exist "%FRONTEND_DIR%\node_modules" (echo node_modules exists) else (echo node_modules MISSING)

echo === Step 6: netstat port check ===
netstat -aon 2>nul | findstr ":8000 " | findstr "LISTENING"
echo port 8000 check done

echo === LAUNCH BACKEND ===
echo Will run: start "JARVIS Backend" cmd /k cd /d %BACKEND_DIR% ^&^& %UVICORN_EXE% app.main:app --reload --host 0.0.0.0 --port 8000
start "JARVIS Backend" cmd /k "cd /d %BACKEND_DIR% && %UVICORN_EXE% app.main:app --reload --host 0.0.0.0 --port 8000"
echo Backend launch ERRORLEVEL=%ERRORLEVEL%

echo === LAUNCH FRONTEND ===
echo Will run: start "JARVIS Frontend" cmd /k cd /d %FRONTEND_DIR% ^&^& npx vite --port 5173
start "JARVIS Frontend" cmd /k "cd /d %FRONTEND_DIR% && npx vite --port 5173"
echo Frontend launch ERRORLEVEL=%ERRORLEVEL%

echo.
echo === ALL DONE ===
pause
