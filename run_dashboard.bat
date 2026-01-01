@echo off
REM ========================================================
REM Local Events Calendar Dashboard - Streamlit Runner
REM ========================================================
REM This batch file runs the Streamlit dashboard application

echo.
echo ========================================================
echo   SWAMPSCOTT EVENTS CALENDAR DASHBOARD
echo ========================================================
echo.
echo Launching Streamlit application...
echo.

REM Prefer Python 3.11 via py launcher; fallback to python on PATH
set "PYCMD=py -3.11"
%PYCMD% --version >nul 2>&1
if %errorlevel% neq 0 (
    set "PYCMD=python"
)

REM Check if streamlit is installed for chosen Python
%PYCMD% -m pip show streamlit >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Installing required packages...
    echo.
    %PYCMD% -m pip install -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo.
        echo Error: Failed to install packages
        echo Please run: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

REM Run the Streamlit app
echo.
echo Starting dashboard on http://localhost:8501
echo Press Ctrl+C to stop the application
echo.
%PYCMD% -m streamlit run streamlit_app.py --logger.level=warning

pause
