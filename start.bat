@echo off
echo ============================================
echo  AI Girlfriend Bot - Starting...
echo ============================================
echo.

:: Start Ollama in background
echo [INFO] Starting Ollama...
start /b ollama serve >nul 2>&1
timeout /t 2 /nobreak >nul

:: Check config
if not exist "config.json" (
    echo [ERROR] config.json not found. Please run setup.bat first.
    pause
    exit /b 1
)

:: Start bot
echo [INFO] Starting bot...
python bot.py
if errorlevel 1 (
    echo [ERROR] Bot crashed. Check logs/bot.log for details.
    pause
)
