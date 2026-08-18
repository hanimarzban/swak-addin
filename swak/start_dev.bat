@echo off
:: SWAK — Quick Start Script for Windows
:: Double-click to start both servers

title SWAK Dev Environment

echo ================================================
echo   SWAK Data Tools — Local Development
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from python.org
    pause
    exit /b 1
)

:: Check if requirements installed
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [Setup] Installing requirements...
    pip install -r server\requirements.txt
    pip install cryptography
    echo.
)

:: Copy .env if not exists
if not exist "server\.env" (
    echo [Setup] Creating .env from template...
    copy server\.env.template server\.env
    echo [Setup] Edit server\.env to add your API keys ^(optional^)
    echo.
)

:: Start Flask backend in new window
echo [Start] Starting Flask backend on :5000 ...
start "SWAK Flask Backend" cmd /k "python server\start.py"
timeout /t 2 /nobreak >nul

:: Start Dev server in new window
echo [Start] Starting Dev server on :3000 ...
start "SWAK Dev Server" cmd /k "python dev_server.py"
timeout /t 2 /nobreak >nul

echo.
echo ================================================
echo   Both servers started!
echo.
echo   1. Open in browser: https://localhost:3000/taskpane.html
echo   2. Click Advanced ^> Proceed to localhost ^(first time only^)
echo   3. Follow LOCAL_TEST_GUIDE.md to sideload in Excel
echo ================================================
echo.

:: Open browser automatically
start "" "https://localhost:3000/taskpane.html"

echo Press any key to stop all servers...
pause >nul

:: Stop servers
taskkill /fi "windowtitle eq SWAK Flask Backend" /f >nul 2>&1
taskkill /fi "windowtitle eq SWAK Dev Server" /f >nul 2>&1
echo [Stop] Servers stopped.
