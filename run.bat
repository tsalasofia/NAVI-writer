@echo off
TITLE NAVI.ai Launcher
echo Starting NAVI.ai...

:: Check if virtual environment exists
if not exist "venv" (
    echo [!] Setup is missing. Running first-time setup...
    call setup.bat
)

:: Check if Ollama is running
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo [!] Ollama is not running in the background.
    echo Please open Ollama and make sure it is running.
    echo.
    pause
    exit /b
)

:: Activate environment and start Streamlit app
call venv\Scripts\activate
streamlit run app.py