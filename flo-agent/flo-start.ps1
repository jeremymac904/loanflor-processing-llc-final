# flo-start.ps1 — Single-command recovery for Flo + Documenso after a power outage or reboot.
#
# Usage:  .\flo-start.ps1           (from the flo-agent directory)
#         .\flo-start.ps1 -SkipDocker   (if Docker Desktop is already running)
#         .\flo-start.ps1 -HermesOnly   (skip Docker entirely, just launch Hermes)
#
# What it does:
#   1. Cleans up stale Unix-domain socket files left by unclean shutdowns
#   2. Starts Docker Desktop and waits for the daemon to be ready
#   3. Verifies the three Documenso containers are running (auto-restart policy handles this)
#   4. Verifies the Documenso API responds with the saved credentials
#   5. Launches Hermes with the ashley profile
#
# Safe to run repeatedly — every step is idempotent.

param(
    [switch]$SkipDocker,
    [switch]$HermesOnly,
    [switch]$TestOnly
)

$ErrorActionPreference = "Continue"
$FloAgent = $PSScriptRoot
$VenvPython = Join-Path $FloAgent ".venv\Scripts\python.exe"
$HermesExe = Join-Path $FloAgent ".venv\Scripts\hermes.exe"
$EnvFlo = Join-Path $FloAgent "deploy\documenso\.env.flo"
$DockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$DockerCli = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"

function Write-Step { param($n, $msg) Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Write-Ok { param($msg) Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  WARN: $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "  FAIL: $msg" -ForegroundColor Red }

Write-Host "`n=== Flo Agent Recovery ===" -ForegroundColor Cyan
Write-Host "Directory: $FloAgent"
Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# ── Step 1: Clean stale socket files ──────────────────────────────────────────

if (-not $HermesOnly) {
    Write-Step 1 "Cleaning stale socket files from prior unclean shutdown"

    $socketDirs = @(
        "$env:LOCALAPPDATA\Docker\run",
        "$env:LOCALAPPDATA\docker-secrets-engine"
    )

    foreach ($dir in $socketDirs) {
        if (Test-Path $dir) {
            $socks = Get-ChildItem $dir -File -ErrorAction SilentlyContinue |
                     Where-Object { $_.Name -like "*.sock*" -or $_.Length -eq 0 }
            if ($socks.Count -gt 0) {
                $ts = Get-Date -Format 'yyyyMMdd-HHmmss'
                $bak = "$dir.bak.$ts"
                try {
                    Rename-Item $dir $bak -ErrorAction Stop
                    New-Item -ItemType Directory $dir | Out-Null
                    Write-Ok "Cleaned $($socks.Count) stale files in $dir"
                } catch {
                    Write-Warn "Could not clean $dir (may be in use): $($_.Exception.Message)"
                }
            } else {
                Write-Ok "$dir is clean"
            }
        }
    }
}

# ── Step 2: Start Docker Desktop ──────────────────────────────────────────────

if (-not $SkipDocker -and -not $HermesOnly) {
    Write-Step 2 "Starting Docker Desktop"

    $dockerRunning = $false
    try {
        $null = & $DockerCli info 2>&1
        if ($LASTEXITCODE -eq 0) { $dockerRunning = $true }
    } catch {}

    if ($dockerRunning) {
        Write-Ok "Docker daemon already running"
    } else {
        if (-not (Test-Path $DockerExe)) {
            Write-Fail "Docker Desktop not found at $DockerExe"
            exit 1
        }

        # Ensure WSL docker-desktop distro is started
        $wslState = wsl -l -v 2>&1 | Out-String
        if ($wslState -match "docker-desktop\s+Stopped") {
            Write-Host "  Kicking WSL docker-desktop distro..."
            wsl -d docker-desktop -- echo "started" 2>&1 | Out-Null
        }

        Start-Process $DockerExe
        Write-Host "  Waiting for Docker daemon (up to 120s)..."

        $timeout = 120
        $elapsed = 0
        while ($elapsed -lt $timeout) {
            Start-Sleep -Seconds 5
            $elapsed += 5
            try {
                $null = & $DockerCli info 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-Ok "Docker daemon ready after ${elapsed}s"
                    $dockerRunning = $true
                    break
                }
            } catch {}
        }

        if (-not $dockerRunning) {
            Write-Fail "Docker daemon did not start within ${timeout}s"
            Write-Host "  Check Docker Desktop for error dialogs"
            Write-Host "  Try: wsl --shutdown, then run this script again"
            exit 1
        }
    }
}

# ── Step 3: Verify Documenso containers ───────────────────────────────────────

if (-not $HermesOnly) {
    Write-Step 3 "Verifying Documenso containers"

    $containers = & $DockerCli ps --format "{{.Names}}|{{.Status}}" 2>&1
    $expected = @("flo-documenso-documenso-1", "flo-documenso-database-1", "flo-documenso-mail-1")
    $allUp = $true

    foreach ($name in $expected) {
        $match = $containers | Where-Object { $_ -like "$name*" }
        if ($match -and $match -match "Up") {
            Write-Ok "$name is running"
        } else {
            Write-Warn "$name is not running — attempting docker compose up"
            $composeDir = Join-Path $FloAgent "deploy\documenso"
            Push-Location $composeDir
            & $DockerCli compose up -d 2>&1
            Pop-Location
            Start-Sleep -Seconds 10
            $allUp = $false
            break
        }
    }

    if (-not $allUp) {
        $containers = & $DockerCli ps --format "{{.Names}}|{{.Status}}" 2>&1
        foreach ($name in $expected) {
            $match = $containers | Where-Object { $_ -like "$name*" }
            if ($match -and $match -match "Up") {
                Write-Ok "$name recovered"
            } else {
                Write-Fail "$name still not running"
            }
        }
    }
}

# ── Step 4: Verify Documenso API ──────────────────────────────────────────────

if (-not $HermesOnly) {
    Write-Step 4 "Verifying Documenso API"

    if (Test-Path $EnvFlo) {
        $envContent = Get-Content $EnvFlo
        $apiUrl = ($envContent | Select-String "DOCUMENSO_API_URL=").Line -replace "DOCUMENSO_API_URL=",""
        $apiToken = ($envContent | Select-String "DOCUMENSO_API_TOKEN=").Line -replace "DOCUMENSO_API_TOKEN=",""
        $templateId = ($envContent | Select-String "DOCUMENSO_LOE_TEMPLATE_ID=").Line -replace "DOCUMENSO_LOE_TEMPLATE_ID=",""

        # Wait for Documenso health
        $healthy = $false
        for ($i = 0; $i -lt 12; $i++) {
            try {
                $resp = Invoke-WebRequest -Uri "$apiUrl/api/v2/openapi.json" -UseBasicParsing -TimeoutSec 5
                if ($resp.StatusCode -eq 200) { $healthy = $true; break }
            } catch {}
            Start-Sleep -Seconds 5
        }

        if ($healthy) {
            Write-Ok "Documenso API responding at $apiUrl"
            try {
                $headers = @{ "Authorization" = $apiToken }
                $tmpl = Invoke-RestMethod -Uri "$apiUrl/api/v2/template/$templateId" -Headers $headers -Method Get
                Write-Ok "Template '$($tmpl.title)' (ID $templateId) verified"
            } catch {
                Write-Warn "Template check failed: $($_.Exception.Message)"
            }
        } else {
            Write-Fail "Documenso API not responding after 60s"
        }
    } else {
        Write-Warn ".env.flo not found — skipping API verification"
    }
}

# ── Step 5: Run tests (optional) ─────────────────────────────────────────────

if ($TestOnly) {
    Write-Step 5 "Running esign tests"
    $env:HERMES_HOME = $FloAgent
    $env:TZ = "UTC"
    $env:PYTHONUTF8 = "1"
    & $VenvPython -m pytest (Join-Path $FloAgent "tests\flo\test_esign.py") -v
    exit $LASTEXITCODE
}

# ── Step 6: Launch Hermes ─────────────────────────────────────────────────────

Write-Step 6 "Launching Hermes Agent (ashley profile)"
$env:HERMES_HOME = $FloAgent
Write-Host "  HERMES_HOME = $FloAgent"
Write-Host ""
Write-Host "  Starting interactive session..." -ForegroundColor Green
Write-Host "  (Ctrl+C to exit Hermes without stopping Docker)"
Write-Host ""

& $HermesExe
