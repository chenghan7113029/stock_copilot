# stock_copilot CLI trial workflow launcher (Windows PowerShell)
# Usage: .\scripts\run_trial.ps1 [--code 600519] [--skip-sync]

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

Set-Location (Join-Path $PSScriptRoot "..")

try { chcp 65001 | Out-Null } catch { }

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] 'py' not found. Install Python 3.10+ from https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[run_trial] launching trial_cli_workflow via py ..."
Write-Host "[run_trial] cwd: $(Get-Location)"
Write-Host ""

& py scripts/trial_cli_workflow.py @args
$code = $LASTEXITCODE

Write-Host ""
if ($code -ne 0) {
    Write-Host "[run_trial] finished with exit code $code (some steps failed)" -ForegroundColor Yellow
} else {
    Write-Host "[run_trial] finished with exit code 0 (all OK)" -ForegroundColor Green
}
exit $code
