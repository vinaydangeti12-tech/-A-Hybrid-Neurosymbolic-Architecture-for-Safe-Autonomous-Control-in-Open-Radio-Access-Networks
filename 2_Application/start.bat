@echo off
title TRACE_v2 — Startup
echo.
echo ============================================================
echo   H-TRACE — Neurosymbolic O-RAN Control (AI + ML + Safety Gate)
echo ============================================================
echo.

:: ── Clear stale Python bytecode ─────────────────────────────────
:: OneDrive can rewrite file mtimes on Windows, which defeats Python's
:: mtime-based .pyc invalidation and makes it run stale compiled code.
:: Remove all __pycache__ and disable bytecode writing to avoid this.
echo [0/4] Clearing stale Python bytecode (__pycache__)...
for /d /r "%~dp0" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
set PYTHONDONTWRITEBYTECODE=1

:: ── Check Python ────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

:: ── Check Node ──────────────────────────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)

:: ── .env check ──────────────────────────────────────────────────
if not exist ".env" (
    echo [INFO] No .env file found — copying from .env.example
    copy .env.example .env >nul
    echo [INFO] Edit .env and add your GOOGLE_API_KEY, then re-run.
    pause
    exit /b 0
)

:: ── Install Python deps ─────────────────────────────────────────
echo [1/4] Installing Python dependencies...
pip install -r server\requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)

:: ── Install Node deps ───────────────────────────────────────────
echo [2/4] Installing Node dependencies...
cd client
if not exist "node_modules" (
    npm install --silent
)
cd ..

:: ── Start Flask backend ─────────────────────────────────────────
echo [3/4] Starting backend server on http://localhost:8000 ...
start "TRACE_v2 Backend" cmd /k "cd server && python -B app.py"
timeout /t 3 /nobreak >nul

:: ── Start React frontend ────────────────────────────────────────
echo [4/4] Starting React dashboard on http://localhost:5173 ...
start "TRACE_v2 Dashboard" cmd /k "cd client && npm run dev"
timeout /t 2 /nobreak >nul

echo.
echo ============================================================
echo   TRACE_v2 is running!
echo.
echo   Dashboard   : http://localhost:5173
echo   Backend API : http://localhost:8000
echo   ADK Web     : run  ^"adk web^"  in  agents/  directory
echo ============================================================
echo.
pause
