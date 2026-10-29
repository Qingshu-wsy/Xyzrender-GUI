@echo off
REM Build xyzrender GUI as a standalone exe using PyInstaller.
REM Set PYTHON to the Python executable for the environment with build dependencies.

if not defined PYTHON set "PYTHON=python"

if not exist "%PYTHON%" if "%PYTHON%" neq "python" (
    echo ERROR: Python executable not found: %PYTHON%
    exit /b 1
)

"%PYTHON%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller is not installed for "%PYTHON%".
    echo Install it with: "%PYTHON%" -m pip install pyinstaller
    exit /b 1
)

echo ============================================
echo  Building xyzrender GUI exe (PyInstaller)
echo ============================================

"%PYTHON%" -m PyInstaller xyzrender_gui.spec --clean
if errorlevel 1 goto :build_failed

echo.
echo ============================================
echo  BUILD OK
echo  Executable:  dist\xyzrender-gui\xyzrender-gui.exe
echo ============================================
exit /b 0

:build_failed
echo.
echo ============================================
echo  BUILD FAILED
echo ============================================
exit /b 1
