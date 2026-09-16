# Cloudflare Tunnel setup for sign.lfprocessing.net → localhost:3000
# Run this script AFTER authenticating with: cloudflared login
#
# Prerequisites:
#   1. cloudflared.exe available in PATH or specify full path below
#   2. Cloudflare account with lfprocessing.net domain
#   3. Run: cloudflared login   (opens browser for Cloudflare auth — owner action)
#
# This script creates a named tunnel and configures DNS so
# sign.lfprocessing.net routes to the local Documenso instance.

$ErrorActionPreference = "Stop"

$CLOUDFLARED = "cloudflared"  # or full path like "C:\path\to\cloudflared.exe"
$TUNNEL_NAME = "flo-documenso"
$HOSTNAME = "sign.lfprocessing.net"
$LOCAL_URL = "http://localhost:3000"

Write-Host "=== Flo Signatures — Cloudflare Tunnel Setup ===" -ForegroundColor Cyan

# Step 1: Check auth
Write-Host "`n1. Checking Cloudflare authentication..."
try {
    & $CLOUDFLARED tunnel list 2>&1 | Out-Null
    Write-Host "   Authenticated." -ForegroundColor Green
} catch {
    Write-Host "   NOT authenticated. Run 'cloudflared login' first." -ForegroundColor Red
    Write-Host "   This opens your browser to authorize Cloudflare access." -ForegroundColor Yellow
    exit 1
}

# Step 2: Create tunnel
Write-Host "`n2. Creating tunnel '$TUNNEL_NAME'..."
$existing = & $CLOUDFLARED tunnel list --output json 2>$null | ConvertFrom-Json
$found = $existing | Where-Object { $_.name -eq $TUNNEL_NAME }
if ($found) {
    $TUNNEL_ID = $found.id
    Write-Host "   Tunnel already exists: $TUNNEL_ID" -ForegroundColor Yellow
} else {
    $result = & $CLOUDFLARED tunnel create $TUNNEL_NAME 2>&1
    Write-Host "   $result"
    $TUNNEL_ID = (& $CLOUDFLARED tunnel list --output json 2>$null | ConvertFrom-Json | Where-Object { $_.name -eq $TUNNEL_NAME }).id
    Write-Host "   Created tunnel: $TUNNEL_ID" -ForegroundColor Green
}

# Step 3: Configure DNS
Write-Host "`n3. Configuring DNS for $HOSTNAME..."
& $CLOUDFLARED tunnel route dns $TUNNEL_NAME $HOSTNAME 2>&1
Write-Host "   DNS configured." -ForegroundColor Green

# Step 4: Write config file
$configDir = "$env:USERPROFILE\.cloudflared"
$configPath = "$configDir\config.yml"
Write-Host "`n4. Writing tunnel config to $configPath..."

$configContent = @"
tunnel: $TUNNEL_ID
credentials-file: $configDir\$TUNNEL_ID.json

ingress:
  - hostname: $HOSTNAME
    service: $LOCAL_URL
  - service: http_status:404
"@

$configContent | Out-File -FilePath $configPath -Encoding utf8
Write-Host "   Config written." -ForegroundColor Green

# Step 5: Test run
Write-Host "`n5. Starting tunnel (press Ctrl+C to stop)..."
Write-Host "   $HOSTNAME -> $LOCAL_URL" -ForegroundColor Cyan
Write-Host ""
& $CLOUDFLARED tunnel run $TUNNEL_NAME
