@echo off
setlocal
cd /d "%~dp0" || exit /b 1
where py.exe >nul 2>nul
if errorlevel 1 (
    echo Install Python 3.13 for Windows with the Python launcher enabled.
    goto failed
)
where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo Install Node.js 24 and reopen this file.
    goto failed
)
if not exist "preview-backend\.venv\Scripts\python.exe" (
    py.exe -3.13 -m venv "preview-backend\.venv" || goto failed
)
"preview-backend\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "preview-backend\requirements.txt" || goto failed
pushd frontend || goto failed
call npm.cmd ci
if errorlevel 1 (
    popd
    goto failed
)
call npm.cmd run build
if errorlevel 1 (
    popd
    goto failed
)
popd
echo Open http://127.0.0.1:18766/ after the server starts.
echo Press Ctrl+C to stop Zhiji.
"preview-backend\.venv\Scripts\python.exe" -m uvicorn main:app --app-dir preview-backend --host 127.0.0.1 --port 18766
if errorlevel 1 goto failed
exit /b 0

:failed
echo Zhiji could not start. Read the error above.
pause
exit /b 1
