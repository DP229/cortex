@echo off
REM ============================================================
REM  Cortex Local Dev Launcher (Backend + Frontend)
REM  Run from the repo root:  start_dev.bat
REM ============================================================
setlocal

set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

REM --- 1. Backend dependencies (idempotent) --------------------
echo.
echo [1/4] Ensuring backend Python dependencies...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo  ! pip install failed. Activate the venv or fix requirements.txt and retry.
    pause
    exit /b 1
)

REM --- 2. Initialize DB if missing -----------------------------
if not exist "cortex.db" (
    echo.
    echo [2/4] Initializing SQLite database...
    ".venv\Scripts\python.exe" -m cortex.main --init-db
) else (
    echo [2/4] cortex.db already exists, skipping init.
)

REM --- 3. Start backend in a new window ------------------------
echo.
echo [3/4] Launching backend on http://127.0.0.1:8080 ...
start "Cortex Backend (FastAPI :8080)" cmd /k ^
    ".venv\Scripts\python.exe" -m cortex.main --host 127.0.0.1 --port 8080 --reload

REM Brief pause so the backend boots before the proxy
timeout /t 3 /nobreak >nul

REM --- 4. Frontend dependencies + dev server -------------------
echo.
echo [4/4] Launching frontend on http://localhost:3000 ...
pushd frontend
if not exist "node_modules" (
    echo     First run — installing npm packages (takes ~1 min)...
    call npm install --silent
)
start "Cortex Frontend (Vite :3000)" cmd /k npm run dev
popd

echo.
echo ============================================================
echo  Both servers are starting in separate windows.
echo.
echo    Backend  :  http://127.0.0.1:8080/docs   (Swagger UI)
echo    Frontend :  http://localhost:3000        (React app)
echo.
echo  Login page will appear; create a user via the API or use
echo  the seed account created by --init-db (check logs).
echo  Click "IBM ELM" in the sidebar to exercise Phase 1.
echo ============================================================
echo.
pause
endlocal
