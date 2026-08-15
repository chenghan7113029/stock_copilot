# Feishu dual push launcher for Windows Task Scheduler.
# Usage: .\scripts\feishu_push_slot.ps1 -Slot 0900
# Optional: -Realtime  -NoSync

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("0900", "1300", "1700")]
    [string]$Slot,

    [switch]$Realtime,
    [switch]$NoSync
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = "src"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

# Ensure npm global tools (lark-cli) are on PATH for non-interactive Task Scheduler sessions.
$npmBin = Join-Path $env:APPDATA "npm"
if ((Test-Path $npmBin) -and ($env:Path -notlike "*$npmBin*")) {
    $env:Path = "$npmBin;$env:Path"
}

$LogDir = Join-Path $RepoRoot "log"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "feishu_push_${Slot}_$stamp.log"

function Write-Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Log "[ERROR] 'py' not found"
    exit 1
}
if (-not (Get-Command lark-cli -ErrorAction SilentlyContinue)) {
    Write-Log "[ERROR] 'lark-cli' not found on PATH"
    exit 1
}

$argv = @(
    "-m", "apps.cli", "feishu", "push",
    "--watchlist",
    "--slot", $Slot
)
if ($Realtime) { $argv += "--realtime" }
if ($NoSync) { $argv += "--no-sync" }

Write-Log "cwd=$RepoRoot slot=$Slot"
Write-Log ("cmd=py " + ($argv -join " "))

& py @argv *>> $LogFile
$code = $LASTEXITCODE
Write-Log "exit_code=$code"
exit $code
