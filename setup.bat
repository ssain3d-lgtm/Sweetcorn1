@echo off
echo ============================================
echo  AI Girlfriend Bot - Setup Script
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found

:: Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ollama not found. Installing...
    echo Please install Ollama from: https://ollama.com/download
    echo After installing, run this script again.
    pause
    exit /b 1
)
echo [OK] Ollama found

:: Check ComfyUI (optional)
echo.
echo [INFO] Checking ComfyUI connection...
curl -s http://localhost:8188/system_stats >nul 2>&1
if errorlevel 1 (
    echo [WARN] ComfyUI not running. Image features will be disabled.
    echo Please start ComfyUI before running the bot for image support.
) else (
    echo [OK] ComfyUI connected
)

:: Install Python dependencies
echo.
echo [INFO] Installing Python dependencies...
pip install "python-telegram-bot[job-queue]==21.9" aiohttp aiosqlite asyncio-throttle --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: Download LLM model
echo.
echo [INFO] Downloading LLM model (huihui_ai/qwen3.5-abliterated)...
echo This may take a while depending on your internet speed...
ollama pull huihui_ai/qwen3.5-abliterated:latest
if errorlevel 1 (
    echo [WARN] Failed to pull abliterated model, trying fallback...
    ollama pull dolphin-mistral-nemo:12b
)
echo [OK] LLM model ready

:: Create folders
echo.
echo [INFO] Creating project folders...
if not exist "database" mkdir database
if not exist "logs" mkdir logs
if not exist "workflows" mkdir workflows
if not exist "reports" mkdir reports
echo [OK] Folders created

:: Setup config
if not exist "config.json" (
    echo [WARN] config.json not found!
) else (
    echo [OK] config.json found - token already configured
)

echo.
echo ============================================
echo  Setup Complete!
echo ============================================
echo.
echo Next steps:
echo 1. Make sure Ollama is running
echo 2. Run start.bat to launch the bot
echo.
pause
