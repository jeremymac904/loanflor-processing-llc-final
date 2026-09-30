<#
.SYNOPSIS
  Creates (or repairs) the Flo Desktop and Start Menu shortcuts so they carry
  the real Flo brand icon.

.DESCRIPTION
  Windows shows the *generic* application glyph for a .lnk whenever the
  shortcut's target is missing, or when the target carries no icon resource.
  That is the exact failure this script exists to prevent: Ashley's Desktop and
  Start Menu entries both pointed at a `Flo.exe` that was never actually
  deployed, so Explorer fell back to the default tile.

  Two design rules keep the icon from drifting again:

  1. IconLocation points at the EXE (`<install>\Flo.exe,0`), never a loose .ico
     dropped somewhere in the repo. The executable is the single artifact that
     electron-builder stamps with `build.icon`, so the shortcut inherits the
     branding from the package itself. A separate .ico path is how the two drift
     apart -- and it silently breaks if the install directory ever moves.

  2. The script refuses to write a shortcut at all when the target exe is
     missing or has no icon resource, instead of leaving behind another generic
     tile that looks "fixed" right up until someone clicks it.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/windows-shortcuts.ps1 `
      -InstallDir "$env:LOCALAPPDATA\Programs\Flo"
#>
[CmdletBinding()]
param(
  # Where Flo.exe lives. Defaults to the canonical per-user install location
  # that electron-builder's NSIS target uses for perMachine:false.
  [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Flo'),

  # Skip the Windows icon/shell cache refresh (used when running repeatedly).
  [switch]$NoIconCacheRefresh
)

$ErrorActionPreference = 'Stop'

function Test-ExecutableHasIcon {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }

  # A PE that rcedit stamped with an icon exposes a non-empty icon group. Probe
  # by asking .NET for the associated icon and comparing against the size of
  # the stock Electron glyph: a stock electron.exe returns the default 32x32
  # application icon, a stamped one returns the real artwork.
  try {
    Add-Type -AssemblyName System.Drawing -ErrorAction Stop
    $icon = [System.Drawing.Icon]::ExtractAssociatedIcon($Path)
    if ($null -eq $icon) { return $false }
    $bmp = $icon.ToBitmap()

    # A generic/default Windows icon is a flat, low-colour placeholder. Real
    # brand art at 32x32 carries many distinct colours. Threshold is
    # deliberately low: this only has to separate "real artwork" from "blank".
    $distinct = @{}
    for ($x = 0; $x -lt $bmp.Width; $x += 2) {
      for ($y = 0; $y -lt $bmp.Height; $y += 2) {
        $distinct[$bmp.GetPixel($x, $y).ToArgb()] = $true
      }
    }
    $count = $distinct.Count
    $bmp.Dispose(); $icon.Dispose()

    Write-Verbose "[flo-shortcuts] distinct colours at 32x32: $count"
    return ($count -gt 12)
  } catch {
    Write-Warning "[flo-shortcuts] could not probe icon in $Path : $($_.Exception.Message)"
    return $false
  }
}

function New-FloShortcut {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$Target,
    [Parameter(Mandatory)][string]$WorkingDirectory
  )

  $dir = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }

  $shell = New-Object -ComObject WScript.Shell
  try {
    $sc = $shell.CreateShortcut($Path)
    $sc.TargetPath       = $Target
    $sc.WorkingDirectory = $WorkingDirectory
    # Inherit the icon from the packaged executable -- see rule 1 above.
    $sc.IconLocation     = "$Target,0"
    $sc.Description      = 'Flo'
    $sc.Save()
  } finally {
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
  }
  Write-Host "  [ok] $Path"
}

$exe = Join-Path $InstallDir 'Flo.exe'

Write-Host "[flo-shortcuts] install dir : $InstallDir"
Write-Host "[flo-shortcuts] target exe  : $exe"

# Rule 2: never mint a shortcut that would render as a generic tile.
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
  throw "[flo-shortcuts] Flo.exe not found at '$exe'. Refusing to create a shortcut that would show the generic Windows application icon. Build/deploy the app first (scripts/deploy-windows-local.ps1)."
}
if (-not (Test-ExecutableHasIcon -Path $exe)) {
  throw "[flo-shortcuts] '$exe' carries no icon resource. The build did not stamp build.icon. Refusing to create a shortcut that would show the generic Windows application icon."
}

$desktop     = [Environment]::GetFolderPath('Desktop')
$startMenu   = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$targets     = @(
  (Join-Path $desktop   'Flo.lnk'),
  (Join-Path $startMenu 'Flo.lnk')
)

Write-Host '[flo-shortcuts] (re)creating shortcuts:'
foreach ($t in $targets) { New-FloShortcut -Path $t -Target $exe -WorkingDirectory $InstallDir }

if (-not $NoIconCacheRefresh) {
  Write-Host '[flo-shortcuts] refreshing Windows icon cache...'

  # Explorer memoises icon bitmaps keyed by (path, last-write). A repaired
  # .lnk keeps its old mtime in some cases, so the stale generic glyph survives
  # a plain refresh. Dropping the cache databases forces a re-decode.
  $iconCacheDb = Join-Path $env:LOCALAPPDATA 'IconCache.db'
  if (Test-Path -LiteralPath $iconCacheDb) {
    try { Remove-Item -LiteralPath $iconCacheDb -Force -ErrorAction Stop; Write-Host '  [ok] removed IconCache.db' }
    catch { Write-Warning "  [warn] could not remove IconCache.db: $($_.Exception.Message)" }
  }

  $explorerCacheDir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Explorer'
  if (Test-Path -LiteralPath $explorerCacheDir) {
    Get-ChildItem -LiteralPath $explorerCacheDir -Filter 'iconcache*.db' -ErrorAction SilentlyContinue |
      ForEach-Object {
        try { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop }
        catch { Write-Warning "  [warn] could not remove $($_.Name): $($_.Exception.Message)" }
      }
    Write-Host '  [ok] cleared explorer iconcache*.db'
  }

  # Icon handles are also pinned by the running shell process; restarting it is
  # what actually flushes them.
  try {
    Stop-Process -Name explorer -Force -ErrorAction Stop
    Start-Sleep -Milliseconds 1200
    Start-Process explorer.exe
    Write-Host '  [ok] restarted explorer.exe'
  } catch {
    Write-Warning "  [warn] could not restart explorer.exe: $($_.Exception.Message)"
  }
}

Write-Host '[flo-shortcuts] done.'
