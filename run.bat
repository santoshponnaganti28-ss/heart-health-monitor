@echo off
title PulseGuard AI - Python Launcher
echo ==========================================================
echo       PulseGuard AI - Setup and Execution Script
echo ==========================================================
echo.

:: Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in your system's PATH.
    echo Please install Python 3.8 or newer and make sure to check
    echo the box "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist .venv (
    echo [INFO] Creating Python virtual environment venv...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: Install dependencies
echo [INFO] Installing Flask and Machine Learning dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install required packages.
    pause
    exit /b 1
)

:: Train Machine Learning model if not present
if not exist heart_model.pkl (
    echo [INFO] Machine Learning model not found. Training model now...
    python train_model.py
    if %errorlevel% neq 0 (
        echo [WARNING] Failed to train Machine Learning model. Running in fallback mode.
    )
)

echo.
echo ==========================================================
echo   [SUCCESS] PulseGuard AI is ready!
echo   The local website will launch at: http://127.0.0.1:5000
echo   To shut down the server, close this command prompt window.
echo ==========================================================
echo.

:: Launch Flask server
python app.py
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Flask server stopped or crashed.
    pause
)
