@echo off
REM stock_copilot CLI trial workflow launcher (Windows CMD)
REM Run from repo root: scripts\run_trial.cmd

chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8

cd /d "%~dp0.."

where py >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 'py' not found. Install Python 3.10+ from https://www.python.org/downloads/
    exit /b 1
)

echo.
echo [run_trial] launching trial_cli_workflow via py ...
echo [run_trial] cwd: %CD%
echo.

py scripts\trial_cli_workflow.py %*
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% neq 0 (
    echo [run_trial] finished with exit code %EXITCODE% ^(some steps failed^)
) else (
    echo [run_trial] finished with exit code 0 ^(all OK^)
)
exit /b %EXITCODE%
