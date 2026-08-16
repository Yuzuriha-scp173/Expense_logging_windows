@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required. Install it from https://www.python.org/downloads/
  echo Make sure "Add python.exe to PATH" is checked.
  pause
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is required. Install it from https://nodejs.org/
  pause
  exit /b 1
)

echo Creating Python environment...
python -m venv backend\.venv
call backend\.venv\Scripts\pip.exe install -r backend\requirements.txt
if errorlevel 1 goto :fail

echo Installing UI packages...
pushd frontend
call npm install
if errorlevel 1 goto :fail
popd

echo Installing desktop shell...
call npm install
if errorlevel 1 goto :fail

echo Building and placing the Desktop shortcut...
call npm run install:desktop
if errorlevel 1 goto :fail

echo.
echo Done. Double-click Daybook on your Desktop.
pause
exit /b 0

:fail
echo.
echo Setup did not finish. Fix the error above and run install.bat again.
pause
exit /b 1
