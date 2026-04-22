@echo off
:: ============================================================
:: Cortex Windows Setup Script
:: Fixes pydantic-core import error by recreating venv with Python 3.12
:: ============================================================
setlocal EnableDelayedExpansion

echo [1/6] Checking Python versions...
py --list 2>nul
if %errorlevel% neq 0 (
    echo ERROR: 'py' launcher not found. Install Python from python.org first.
    exit /b 1
)

echo.
echo [2/6] Deactivating current venv (if active)...
if defined VIRTUAL_ENV (
    call deactivate 2>nul
    echo      Deactivated: %VIRTUAL_ENV%
)

echo.
echo [3/6] Removing old .venv directory...
if exist ".venv" (
    rmdir /s /q ".venv"
    if exist ".venv" (
        echo ERROR: Could not delete .venv. Close any IDES or terminals using it.
        exit /b 1
    )
    echo      Old .venv deleted.
) else (
    echo      No existing .venv found.
)

echo.
echo [4/6] Creating new virtual environment with Python 3.12...
py -3.12 -m venv .venv
if %errorlevel% neq 0 (
    echo ERROR: Failed to create venv with Python 3.12. Is it installed?
    echo        Run: winget install Python.Python.3.12
    exit /b 1
)
echo      .venv created successfully with Python 3.12.

echo.
echo [5/6] Installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .[dev]
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Check error output above.
    exit /b 1
)

echo.
echo [6/6] Verifying installation...
python -c "import pydantic; print('  pydantic:', pydantic.__version__)" || (
    echo ERROR: pydantic import failed!
    exit /b 1
)
python -c "import pydantic_core; print('  pydantic_core: OK')" || (
    echo ERROR: pydantic_core import failed!
    exit /b 1
)
python -c "import fastapi; print('  fastapi:', fastapi.__version__)" || (
    echo ERROR: fastapi import failed!
    exit /b 1
)
python -c "import uvicorn; print('  uvicorn:', uvicorn.__version__)" || (
    echo ERROR: uvicorn import failed!
    exit /b 1
)

echo.
echo =========================================
echo SUCCESS! All imports working.
echo.
echo To start the server, run:
echo   .venv\Scripts\activate.bat
echo   uvicorn cortex.api:app --reload --port 8080
echo =========================================
endlocal
