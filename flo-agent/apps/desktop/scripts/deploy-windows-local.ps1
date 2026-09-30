<#
.SYNOPSIS
  Deploys a built Flo Windows package to the canonical per-user install
  directory, then (re)creates the Desktop and Start Menu shortcuts.

.DESCRIPTION
  Installs `release\win-unpacked` to
  `%LOCALAPPDATA%\Programs\Flo` -- the same layout electron-builder's NSIS
  target produces for `perMachine:false`, so a locally deployed build and an
  installer-driven install are byte-for-byte the same tree.

  Ashley's runtime state lives in `%APPDATA%\Flo` (Electron userData:
  `flo-secrets.json`, `connections.json`, `active-profile.json`, provider
  credentials, window state). This script only ever WRITES to the install
  directory and never touches `%APPDATA%`, so that data is preserved by
  construction rather than by a backup/restore dance.

  Finally it delegates shortcut creation + icon-cache refresh to
  windows-shortcuts.ps1.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/deploy-windows-local.ps1
#>
[CmdletBinding()]
param(
  # Built, unpacked package directory produced by `npm run pack:win`.
  # Left empty by default and resolved in the body, because $PSScriptRoot is
  # not populated inside a param() default block under Windows PowerShell 5.1.
  [string]$SourceDir,

  # Canonical install location (matches electron-builder perMachine:false).
  [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Flo'),

  # Refuse to overwrite an existing install.
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot is empty in some invocation contexts; fall back to the path the
# engine recorded for this script.
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $SourceDir) {
  $SourceDir = Join-Path $ScriptDir '..\release\win-unpacked'
}

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $SourceDir 'Flo.exe'))) {
  throw "[deploy-windows] '$SourceDir' does not look like a built Flo package (no Flo.exe). Run the Windows pack first."
}

Write-Host '[deploy-windows] source     :' $SourceDir
Write-Host '[deploy-windows] install    :' $InstallDir
Write-Host '[deploy-windows] appdata    :' (Join-Path $env:APPDATA 'Flo') '(never written to)'

# --- guard: refuse to clobber a live install without -Force -----------------
if ((Test-Path -LiteralPath $InstallDir) -and -not $Force) {
  throw "[deploy-windows] '$InstallDir' already exists. Re-run with -Force to replace it."
}

# A running Flo.exe locks its own image file, which makes the copy fail
# half-way and leaves a mixed-version tree. Catch that up front.
$running = Get-Process -Name Flo -ErrorAction SilentlyContinue
if ($running) {
  $inInstall = $running | Where-Object { $_.Path -and $_.Path.StartsWith($InstallDir, [StringComparison]::OrdinalIgnoreCase) }
  if ($inInstall) {
    throw "[deploy-windows] Flo is running from '$InstallDir' (PID $($inInstall.Id -join ', ')). Close it and re-run."
  }
}

if (Test-Path -LiteralPath $InstallDir) {
  # Stash the previous install rather than deleting it, so a bad deploy is
  # recoverable without a rebuild.
  $backup = "$InstallDir.prev"
  Write-Host "[deploy-windows] backing up existing install -> $backup"
  if (Test-Path -LiteralPath $backup) {
    Remove-Item -LiteralPath $backup -Recurse -Force
  }
  Move-Item -LiteralPath $InstallDir -Destination $backup -Force
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

# robocopy preserves the long Electron tree faithfully; Copy-Item is far slower
# on the 200MB+ .exe and its 8k-path limit bites on deep node trees.
# Arguments are pre-quoted because Start-Process -ArgumentList does NOT quote
# for us, and a path containing a space or an apostrophe ("Ashley's Pipeline")
# otherwise gets re-split into bogus extra parameters.
Write-Host '[deploy-windows] copying package...'
$rc = Start-Process -FilePath robocopy.exe `
  -ArgumentList @("`"$SourceDir`"", "`"$InstallDir`"", '/E', '/R:2', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP') `
  -Wait -PassThru -NoNewWindow
# robocopy uses 0-7 for success, >=8 for failure.
if ($rc.ExitCode -ge 8) {
  throw "[deploy-windows] robocopy failed with exit code $($rc.ExitCode). The previous install is preserved at '$InstallDir.prev'."
}

# --- verify what actually landed ------------------------------------------
$exe     = Join-Path $InstallDir 'Flo.exe'
$resIcon = Join-Path $InstallDir 'resources\icon.ico'

foreach ($required in @($exe, $resIcon)) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw "[deploy-windows] deploy incomplete: '$required' is missing after copy."
  }
}

$iconSize = (Get-Item -LiteralPath $resIcon).Length
Write-Host '[deploy-windows] deployed Flo.exe        :' ([math]::Round((Get-Item $exe).Length / 1MB, 1)) 'MB'
Write-Host '[deploy-windows] deployed resources/icon :' $iconSize 'bytes'

# The packaging step stamps the version resource from package.json `build`.
# If it still reports stock Electron, rcedit never ran and every Windows
# surface (taskbar, Alt+Tab, title bar) would fall back to a generic glyph.
$info = [Diagnostics.FileVersionInfo]::GetVersionInfo($exe)
Write-Host '[deploy-windows] exe ProductName        :' $info.ProductName
if ($info.ProductName -ne 'Flo') {
  throw "[deploy-windows] '$exe' reports ProductName '$($info.ProductName)' instead of 'Flo' -- the icon/version resource was not stamped. Shortcuts would show the generic application icon."
}

# --- shortcuts + icon cache ------------------------------------------------
& (Join-Path $ScriptDir 'windows-shortcuts.ps1') -InstallDir $InstallDir

Write-Host ''
Write-Host '[deploy-windows] SUCCESS -- Flo is installed and branded at:' $InstallDir
