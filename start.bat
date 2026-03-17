@echo off
setlocal enabledelayedexpansion
title Wiom UAT Event Viewer - Setup
color 0F

echo.
echo  ============================================
echo    Wiom UAT Event Viewer
echo    Live analytics event dashboard
echo  ============================================
echo.

:: -----------------------------------------------
:: 1. Check Python
:: -----------------------------------------------
echo  [1/3] Checking Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] Python is NOT installed.
    echo.
    echo  Python is required to run the event viewer.
    echo  Choose an installation method:
    echo.
    echo    1. Install automatically via winget (recommended)
    echo    2. I'll install manually from python.org
    echo.
    set /p PYCHOICE="  Enter choice (1 or 2): "
    if "!PYCHOICE!"=="1" (
        echo.
        echo  Installing Python via winget... (this may take a minute)
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        if !errorlevel! neq 0 (
            echo.
            echo  [X] winget install failed. Please install Python manually:
            echo      https://www.python.org/downloads/
            echo      IMPORTANT: Check "Add Python to PATH" during installation.
            echo.
            pause
            exit /b 1
        )
        echo.
        echo  [OK] Python installed. You may need to RESTART this terminal.
        echo       Close this window and run start.bat again.
        echo.
        pause
        exit /b 0
    ) else (
        echo.
        echo  Please install Python from: https://www.python.org/downloads/
        echo  IMPORTANT: Check "Add Python to PATH" during installation.
        echo  Then run start.bat again.
        echo.
        pause
        exit /b 1
    )
) else (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
    echo  [OK] !PYVER! found
)

:: -----------------------------------------------
:: 2. Check ADB
:: -----------------------------------------------
echo.
echo  [2/3] Checking ADB (Android Debug Bridge)...
where adb >nul 2>&1
if %errorlevel% neq 0 (
    :: Check common Android SDK locations
    set "ADB_FOUND="
    if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
        set "ADB_FOUND=%LOCALAPPDATA%\Android\Sdk\platform-tools"
    )
    if exist "%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe" (
        set "ADB_FOUND=%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools"
    )

    if defined ADB_FOUND (
        echo  [!] ADB found at !ADB_FOUND! but not in PATH.
        echo      Adding to PATH for this session...
        set "PATH=!ADB_FOUND!;!PATH!"
        echo  [OK] ADB added to PATH
    ) else (
        echo.
        echo  [!] ADB is NOT installed.
        echo.
        echo  ADB is needed to communicate with your Android device/emulator.
        echo  Choose an installation method:
        echo.
        echo    1. Install Android Platform Tools automatically (recommended, ~10MB)
        echo    2. I already have Android Studio (I'll fix PATH myself)
        echo.
        set /p ADBCHOICE="  Enter choice (1 or 2): "
        if "!ADBCHOICE!"=="1" (
            echo.
            echo  Downloading Android Platform Tools...
            mkdir "%USERPROFILE%\android-platform-tools" 2>nul
            powershell -Command "Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile '%TEMP%\platform-tools.zip'"
            if !errorlevel! neq 0 (
                echo  [X] Download failed. Check your internet connection.
                pause
                exit /b 1
            )
            echo  Extracting...
            powershell -Command "Expand-Archive -Path '%TEMP%\platform-tools.zip' -DestinationPath '%USERPROFILE%\android-platform-tools' -Force"
            set "PATH=%USERPROFILE%\android-platform-tools\platform-tools;!PATH!"
            :: Add to user PATH permanently
            powershell -Command "[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path','User') + ';%USERPROFILE%\android-platform-tools\platform-tools', 'User')"
            echo  [OK] ADB installed and added to PATH
            del "%TEMP%\platform-tools.zip" 2>nul
        ) else (
            echo.
            echo  If you have Android Studio, ADB is at:
            echo    %%LOCALAPPDATA%%\Android\Sdk\platform-tools\
            echo.
            echo  Add that folder to your system PATH, then run start.bat again.
            pause
            exit /b 1
        )
    )
) else (
    echo  [OK] ADB found
)

:: Verify ADB works
adb version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [X] ADB found but not working. Please check your installation.
    pause
    exit /b 1
)

:: -----------------------------------------------
:: 3. Hand off to Python setup wizard
:: -----------------------------------------------
echo.
echo  [3/3] Starting setup wizard...
echo.

python "%~dp0setup.py"

pause
