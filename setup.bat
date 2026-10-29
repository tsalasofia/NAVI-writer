@echo off
TITLE NAVI.ai Setup
echo ===================================================
echo   NAVI.ai First-Time Setup
echo ===================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Python is not installed or not added to PATH.
    echo Please download and install Python from https://www.python.org/
    pause
    exit /b
)

:: Create Virtual Environment if it doesn't exist
if not exist "venv" (
    echo [*] Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment and install requirements
echo [*] Installing dependencies (this may take a minute)...
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ===================================================
echo Setup complete! You can now run 'run.bat'.
echo ===================================================
pause