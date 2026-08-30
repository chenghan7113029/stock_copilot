# Feishu 研报推送 launcher for Windows Task Scheduler.
# Usage: .\scripts\feishu_push_slot.ps1 -Slot 0830
# Pushes report confront + persona-stress per watchlist code (2 docs + 2 messages each).
# Optional: -Realtime  -NoSync

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("0830", "0900", "1300", "1700")]
    [string]$Slot,

    [switch]$Realtime,
    [switch]$NoSync
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = "src"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)

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
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    Write-Host $line
}

function Test-LarkUserAuth {
    $raw = & lark-cli auth status --json --verify 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        return $false, "lark-cli auth status 失败"
    }
    try {
        $payload = $raw | ConvertFrom-Json
    } catch {
        return $false, "无法解析 lark-cli auth status 输出"
    }
    $user = $payload.identities.user
    if (-not $user) {
        return $false, "未找到 user 身份信息"
    }
    # needs_refresh 时 --verify 会尝试用 refresh token 续期；只有 refresh 也过期才需重新扫码
    if ($user.status -ne "ready") {
        $hint = if ($user.hint) { $user.hint } else { "请运行: lark-cli auth login --recommend" }
        return $false, "lark-cli 用户身份不可用（$($user.message)）。$hint"
    }
    if ($user.tokenStatus -eq "expired") {
        return $false, "lark-cli refresh token 已过期，请重新授权: lark-cli auth login --recommend"
    }
    if ($user.verified -eq $false) {
        $err = if ($user.verifyError) { $user.verifyError } else { "token 校验失败" }
        return $false, "lark-cli token 不可用：$err"
    }
    return $true, ""
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Log "[ERROR] 'py' not found"
    exit 1
}
if (-not (Get-Command lark-cli -ErrorAction SilentlyContinue)) {
    Write-Log "[ERROR] 'lark-cli' not found on PATH"
    exit 1
}

$authOk, $authMsg = Test-LarkUserAuth
if (-not $authOk) {
    Write-Log "[ERROR] $authMsg"
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

$code = 0
# Native stderr (e.g. [warn] from apps.cli) becomes ErrorRecord under 2>&1;
# with Stop that aborts the whole watchlist after the first warning.
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & py @argv 2>&1 | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) {
            $line = $_.Exception.Message
            if (-not $line) { $line = [string]$_ }
        } else {
            $line = [string]$_
        }
        if ($line) { Add-Content -Path $LogFile -Value $line -Encoding utf8 }
        Write-Host $line
    }
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        $code = $LASTEXITCODE
    }
} catch {
    Write-Log "[ERROR] $($_.Exception.Message)"
    $code = 1
} finally {
    $ErrorActionPreference = $prevEap
}

Write-Log "exit_code=$code"
exit $code
