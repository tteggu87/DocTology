@echo off
setlocal DisableDelayedExpansion
rem Repository convenience entry; runtime belongs to DocTology.
if not exist "%~dp0runtime\start_dashboard.bat" (
  echo Wiki Studio launcher is missing. Keep the complete DocTology folder together.
  pause
  exit /b 1
)
rem Tail-chain without CALL to avoid another expansion of user arguments.
"%~dp0runtime\start_dashboard.bat" %*
