@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist "logs" mkdir "logs"
call :cleanup_logs "logs\start_*.log" 5
for /f "tokens=1-3 delims=/ " %%a in ("%DATE%") do set "RUN_DATE=%%a%%b%%c"
set "RUN_TIME=%TIME: =0%"
set "RUN_TIME=%RUN_TIME::=%"
set "RUN_TIME=%RUN_TIME:.=%"
set "START_LOG=%CD%\logs\start_%RUN_DATE%_%RUN_TIME%.log"
echo [%DATE% %TIME%] Starting photo2mesh... > "%START_LOG%"
call :cleanup_logs "logs\start_*.log" 5

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    echo Creating Python virtual environment... >> "%START_LOG%"
    py -3 -m venv .venv >> "%START_LOG%" 2>&1
    if errorlevel 1 (
        python -m venv .venv >> "%START_LOG%" 2>&1
    )
    if errorlevel 1 (
        echo Failed to create .venv. Please install Python 3 on Windows.
        echo Failed to create .venv. >> "%START_LOG%"
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\activate.bat" (
    echo .venv exists, but activate.bat was not found.
    echo .venv exists, but activate.bat was not found. >> "%START_LOG%"
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate .venv.
    echo Failed to activate .venv. >> "%START_LOG%"
    pause
    exit /b 1
)

python -m pip install -r requirements.txt >> "%START_LOG%" 2>&1
if errorlevel 1 (
    echo Failed to install dependencies. See %START_LOG% for details.
    echo Failed to install dependencies. >> "%START_LOG%"
    pause
    exit /b 1
)

set "PYTHONPATH=%CD%\app"
if "%PHOTO2MESH_HOST%"=="" set "PHOTO2MESH_HOST=127.0.0.1"
if "%PHOTO2MESH_PORT%"=="" set "PHOTO2MESH_PORT=7860"

echo Starting photo2mesh at http://%PHOTO2MESH_HOST%:%PHOTO2MESH_PORT%
echo Starting photo2mesh at http://%PHOTO2MESH_HOST%:%PHOTO2MESH_PORT% >> "%START_LOG%"

python -m flask --app photo2mesh.server run --host %PHOTO2MESH_HOST% --port %PHOTO2MESH_PORT% >> "%START_LOG%" 2>&1
set "FLASK_EXIT=%ERRORLEVEL%"

echo Flask server stopped with exit code %FLASK_EXIT%.
echo Flask server stopped with exit code %FLASK_EXIT%. >> "%START_LOG%"
call :cleanup_logs "logs\start_*.log" 5
echo See %START_LOG% for details.
pause
exit /b %FLASK_EXIT%

:cleanup_logs
setlocal EnableDelayedExpansion
set "PATTERN=%~1"
set "KEEP=%~2"
set /a COUNT=0
for /f "delims=" %%f in ('dir /b /a-d /o-d "%PATTERN%" 2^>nul') do (
    set /a COUNT+=1
    if !COUNT! GTR !KEEP! del "logs\%%f" >nul 2>nul
)
endlocal
exit /b 0
