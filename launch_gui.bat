@echo off
setlocal

pushd "%~dp0"

set "VENV_DIR=.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

where python >nul 2>&1
if %ERRORLEVEL%==0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if %ERRORLEVEL%==0 (
        set "PY_CMD=py -3"
    ) else (
        echo [ERROR] Python was not found. Install Python 3 and try again.
        popd
        exit /b 1
    )
)

if not exist "%VENV_PYTHON%" (
    echo [INFO] Creating virtual environment in "%VENV_DIR%"...
    %PY_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        popd
        exit /b 1
    )
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    popd
    exit /b 1
)

echo [INFO] Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    popd
    exit /b 1
)

echo [INFO] Launching GUI...
python -m cpu_sdf_raymarcher --gui %*
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%
