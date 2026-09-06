@echo off
setlocal DisableDelayedExpansion
rem Prevent implicit runtime installation by current and legacy Python launchers.
set "PYTHON_MANAGER_AUTOMATIC_INSTALL=false"
set "PYLAUNCHER_ALLOW_INSTALL="
set "PYLAUNCHER_ALWAYS_INSTALL="
rem No installation or workspace changes. All paths are relative to this file.
if defined WIKI_STUDIO_PYTHON goto custom_python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if "%errorlevel%"=="0" goto use_py
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if "%errorlevel%"=="0" goto use_python
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if "%errorlevel%"=="0" goto use_python3
goto missing_python

:custom_python
"%WIKI_STUDIO_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not "%errorlevel%"=="0" goto missing_python
echo Starting Wiki Studio. Keep this window open; Ctrl+C stops the server.
"%WIKI_STUDIO_PYTHON%" "%~dp0wiki_dashboard.py" --open-browser --auto-port %*
set "STUDIO_EXIT=%errorlevel%"
goto finished

:use_py
echo Starting Wiki Studio. Keep this window open; Ctrl+C stops the server.
py -3 "%~dp0wiki_dashboard.py" --open-browser --auto-port %*
set "STUDIO_EXIT=%errorlevel%"
goto finished

:use_python
echo Starting Wiki Studio. Keep this window open; Ctrl+C stops the server.
python "%~dp0wiki_dashboard.py" --open-browser --auto-port %*
set "STUDIO_EXIT=%errorlevel%"
goto finished

:use_python3
echo Starting Wiki Studio. Keep this window open; Ctrl+C stops the server.
python3 "%~dp0wiki_dashboard.py" --open-browser --auto-port %*
set "STUDIO_EXIT=%errorlevel%"
goto finished

:missing_python
echo Python 3.11 or newer was not found.
echo Install Python from https://www.python.org/downloads/ and enable its PATH option.
echo Or set WIKI_STUDIO_PYTHON to the full path of an existing Python executable.
set "STUDIO_EXIT=1"

:finished
if not "%STUDIO_EXIT%"=="0" pause
exit /b %STUDIO_EXIT%
