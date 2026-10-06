import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const desktopDir = resolve(import.meta.dirname, '..')
const manifest = JSON.parse(readFileSync(resolve(desktopDir, 'package.json'), 'utf8'))
const workflow = readFileSync(resolve(desktopDir, '../../../.github/workflows/release-desktop.yml'), 'utf8')
const mainSource = readFileSync(resolve(desktopDir, 'electron/main.ts'), 'utf8')
const nsisInstaller = readFileSync(resolve(desktopDir, 'scripts/updater-installer.nsh'), 'utf8')
const hermesAuthSource = readFileSync(resolve(desktopDir, '../../hermes_cli/auth.py'), 'utf8')
const updaterStart = mainSource.indexOf('type FloAppUpdateState')
const updaterEnd = mainSource.indexOf('// Uninstall — remove the Chat GUI', updaterStart)
const updaterSource = mainSource.slice(updaterStart, updaterEnd)

describe('Flo GitHub Release update packaging', () => {
  it('uses the canonical public GitHub Releases feed without an embedded credential', () => {
    expect(manifest.build.publish).toContainEqual({
      provider: 'github',
      owner: 'jeremymac904',
      repo: 'loanflor-processing-llc-final',
      releaseType: 'release'
    })
    expect(manifest.dependencies['electron-updater']).toBeTruthy()
    expect(manifest.build.publish[0]).not.toHaveProperty('token')
  })

  it('keeps updater-supported Windows NSIS and macOS zip targets in the release workflow', () => {
    expect(workflow).toContain('npm run dist:win:nsis --workspace apps/desktop')
    expect(workflow).toContain('npm run dist:mac --workspace apps/desktop')
    expect(workflow).toContain('SHA256SUMS-windows-x64.txt')
    expect(workflow).toContain('SHA256SUMS-macos-arm64.txt')
    expect(workflow).toContain("vars.FLO_MAC_SIGNING_CONFIGURED == 'true'")
    expect(manifest.build.nsis.perMachine).toBe(false)
  })

  it('updates only the application and does not redirect or delete user data', () => {
    expect(manifest.build.appId).toBe('com.example.flo')
    expect(mainSource).toContain('autoUpdater.quitAndInstall(false, true)')
    expect(updaterSource).not.toMatch(/setPath\(['"]userData['"]|removeSync\([^\n]*userData/i)
    expect(hermesAuthSource).toContain('get_default_hermes_root() / "shared"')
    expect(hermesAuthSource).toContain('Path.home() / ".codex"')
    expect(nsisInstaller).not.toMatch(/(?:Delete|RMDir).*(?:userData|HERMES_HOME|hermes\\shared)/i)
  })

  it('repairs retained shortcut targets and relaunches the installed executable directly', () => {
    expect(manifest.build.nsis.include).toBe('scripts/updater-installer.nsh')
    expect(nsisInstaller).toContain('CreateShortCut "$newStartMenuLink" "$appExe"')
    expect(nsisInstaller).toContain('CreateShortCut "$newDesktopLink" "$appExe"')
    expect(nsisInstaller).toContain('StrCpy $launchLink "$appExe"')
  })
})
