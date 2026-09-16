# flo-autostart.ps1 — Silent startup script for Task Scheduler.
# Runs at login to ensure Docker Desktop and the Documenso stack start cleanly.
#
# This script:
#   1. Cleans stale AF_UNIX socket files left by unclean shutdowns
#   2. Waits for Docker Desktop to start (it auto-starts via the Run registry key)
#   3. Kicks the WSL docker-desktop distro if it's stuck in Stopped
#   4. Waits for Docker daemon to be ready
#   5. Verifies Documenso containers are running
#
# Runs hidden (no terminal window) via Task Scheduler.
# Logs to flo-autostart.log in the flo-agent directory.

$ErrorActionPreference = "Continue"
$FloAgent = $PSScriptRoot
$LogFile = Join-Path $FloAgent "flo-autostart.log"
$DockerCli = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"

function Log { param($msg) $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"; "$ts  $msg" | Out-File -FilePath $LogFile -Append -Encoding utf8 }

Log "=== Flo autostart begin ==="

# Step 1: Clean stale sockets
$socketDirs = @(
    "$env:LOCALAPPDATA\Docker\run",
    "$env:LOCALAPPDATA\docker-secrets-engine"
)

foreach ($dir in $socketDirs) {
    if (Test-Path $dir) {
        $files = Get-ChildItem $dir -File -ErrorAction SilentlyContinue
        if ($files.Count -gt 0) {
            $ts = Get-Date -Format 'yyyyMMdd-HHmmss'
            $bak = "$dir.bak.$ts"
            try {
                Rename-Item $dir $bak -ErrorAction Stop
                New-Item -ItemType Directory $dir | Out-Null
                Log "Cleaned stale sockets in $dir"
            } catch {
                Log "WARN: Could not clean $dir — $($_.Exception.Message)"
            }
        }
    }
}

# Step 2: Wait for Docker Desktop process (it starts from the Run key)
$waited = 0
while ($waited -lt 60) {
    $dockerProcs = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
    if ($dockerProcs) { break }
    Start-Sleep -Seconds 5
    $waited += 5
}

if (-not (Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue)) {
    Log "Docker Desktop not started by Run key — starting it"
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
}

# Step 3: Kick WSL if stuck
Start-Sleep -Seconds 5
$wslState = wsl -l -v 2>&1 | Out-String
if ($wslState -match "docker-desktop\s+Stopped") {
    Log "WSL docker-desktop is Stopped — kicking it"
    wsl -d docker-desktop -- echo "started" 2>&1 | Out-Null
}

# Step 4: Wait for Docker daemon
$timeout = 180
$elapsed = 0
$ready = $false
while ($elapsed -lt $timeout) {
    try {
        $null = & $DockerCli info 2>&1
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 5
    $elapsed += 5
}

if ($ready) {
    Log "Docker daemon ready after ${elapsed}s"
} else {
    Log "ERROR: Docker daemon not ready after ${timeout}s"
    exit 1
}

# Step 5: Verify containers
$containers = & $DockerCli ps --format "{{.Names}}" 2>&1
$expected = @("flo-documenso-documenso-1", "flo-documenso-database-1", "flo-documenso-mail-1")
$allPresent = $true

foreach ($name in $expected) {
    if ($containers -notcontains $name) {
        $allPresent = $false
        Log "Container $name not running — running docker compose up"
        break
    }
}

if (-not $allPresent) {
    $composeDir = Join-Path $FloAgent "deploy\documenso"
    Push-Location $composeDir
    & $DockerCli compose up -d 2>&1 | Out-String | ForEach-Object { Log $_ }
    Pop-Location
}

# Final check
Start-Sleep -Seconds 5
$finalContainers = & $DockerCli ps --format "{{.Names}}|{{.Status}}" 2>&1
foreach ($name in $expected) {
    $match = $finalContainers | Where-Object { $_ -like "$name*" }
    if ($match) { Log "OK: $match" } else { Log "MISSING: $name" }
}

Log "=== Flo autostart complete ==="
