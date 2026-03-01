@echo off
echo ============================================
echo  Ollama VRAM Unloader
echo ============================================
echo.

REM --- Read model name from config.json using PowerShell ---
for /f "delims=" %%i in ('powershell -NoProfile -Command "(Get-Content config.json | ConvertFrom-Json).model"') do set MODEL=%%i

if "%MODEL%"=="" (
    echo [WARN] Could not read model from config.json
    echo [INFO] Using fallback: huihui_ai/exaone3.5-abliterated:7.8b
    set MODEL=huihui_ai/exaone3.5-abliterated:7.8b
)

echo [INFO] Unloading model from VRAM: %MODEL%
echo.

REM --- Primary method: ollama stop ---
ollama stop "%MODEL%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Model unloaded successfully.
) else (
    echo.
    echo [WARN] ollama stop failed. Trying keep_alive=0 method...
    echo.

    REM --- Fallback: send keep_alive=0 request via curl ---
    curl -s -X POST http://localhost:11434/api/chat ^
        -H "Content-Type: application/json" ^
        -d "{\"model\":\"%MODEL%\",\"messages\":[],\"keep_alive\":0}" ^
        > nul 2>&1

    echo [OK] keep_alive=0 request sent. Model should unload shortly.
)

echo.
echo [INFO] Check VRAM usage with: nvidia-smi
echo ============================================
pause
