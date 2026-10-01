/**
 * before-pack.mjs — electron-builder beforePack hook.
 *
 * Two responsibilities:
 *
 * 1. Removes any stale unpacked app directory (`appOutDir`) before
 *    electron-builder stages the Electron binaries into it.
 *
 * WHY THIS EXISTS
 * ---------------
 * electron-builder's final packaging step copies the stock `electron`
 * binary into `release/<platform>-unpacked/` and then renames it to the
 * product name (`Hermes`). If a PREVIOUS `npm run pack` was interrupted
 * (Ctrl-C, OOM kill, crash, full disk) the unpacked directory is left in a
 * corrupted partial state: it keeps the already-renamed `LICENSE.electron.txt`
 * and the Chromium payload (.pak/.so/icudtl.dat/chrome-sandbox) but is MISSING
 * the `electron` binary itself.
 *
 * On the next run, electron-builder sees the destination directory already
 * populated, skips re-copying the binary it thinks is present, then tries to
 * rename a `electron` file that no longer exists. The build dies with:
 *
 *   ENOENT: no such file or directory, rename
 *   '.../release/linux-unpacked/electron' -> '.../release/linux-unpacked/Hermes'
 *
 * This is a hard failure with no obvious cause for the user — `hermes desktop`
 * just prints "Desktop GUI build failed" and the only fix is to manually
 * `rm -rf` the release directory, which a normal user has no way to know.
 *
 * The packaging step is not idempotent across an interrupted run, so we make
 * it idempotent ourselves: wipe the target unpacked directory up front so
 * electron-builder always stages into a clean tree. This is safe — the
 * directory is a pure build artifact that electron-builder fully recreates
 * on every pack; nothing else depends on its prior contents.
 *
 * Cross-platform: the same partial-state trap exists on macOS
 * (the mac-unpacked Hermes.app bundle) and Windows (win-unpacked), so we
 * clean whatever `appOutDir` electron-builder hands us regardless of platform.
 *
 * Best-effort: a cleanup failure must never mask the real build. We log and
 * resolve rather than throw — worst case electron-builder hits the original
 * ENOENT, which is no worse than not having this hook at all.
 *
 * 2. Re-stages node-pty's native files for the ACTUAL target platform/arch
 *    of this pack. `npm run build` already staged node-pty once for the
 *    host machine (see scripts/stage-native-deps.mjs), which is correct for
 *    single-arch builds matching the host. But electron-builder can target
 *    a different arch than the host (cross-build), or pack multiple archs
 *    from one `npm run build` (e.g. `dist:mac` => x64 + arm64). Only this
 *    hook knows the real per-target arch, via `context.arch` /
 *    `context.electronPlatformName` — so it re-stages on top of whatever
 *    `npm run build` left behind, per target, right before files are read
 *    for packing.
 *
 * electron-builder passes a context with:
 *   - appOutDir:            the unpacked app directory about to be staged
 *   - electronPlatformName: 'win32' | 'darwin' | 'linux'
 *   - arch:                 Arch enum (0=ia32, 1=x64, 2=armv7l, 3=arm64, 4=universal)
 *
 * 3. Asserts the Windows icon assets are present and complete BEFORE staging.
 *
 * WHY THIS EXISTS
 * ---------------
 * The Flo brand icon is the single asset behind every place Windows shows
 * "Flo" as a program: the `Flo.exe` version resource (drives taskbar, Alt+Tab,
 * title-bar and the icons of any shortcut whose IconLocation is the exe), the
 * `resources/icon.ico` that `electron/app-icon.ts` hands to BrowserWindow, and
 * `package.json build.icon`, which electron-builder embeds into installers so
 * NSIS-created Desktop/Start Menu shortcuts inherit the same image.
 *
 * That chain is fail-SILENT. If `assets/icon.ico` goes missing, or is
 * regenerated with only a 256x256 frame, nothing errors: the build still
 * succeeds and still produces a `Flo.exe` — one with no icon resource at all.
 * Windows then falls back to the generic application glyph, and the user sees
 * a blank tile on the Desktop, in the Start Menu and on the taskbar. The
 * shortcut still launches correctly, so it reads as a cosmetic nit and the
 * branding regression survives indefinitely (this is exactly the state the
 * live Ashley install shipped in).
 *
 * Checking the frame table up front turns that silent cosmetic regression into
 * a loud build failure naming the exact missing sizes.
 */
import { existsSync, readFileSync, rmSync, renameSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Arch } from 'electron-builder'
import { stageNodePty, stageGetWindows } from './stage-native-deps.mjs'

/**
 * Sizes Windows actually samples for a program icon. A .ico missing any of
 * these still "builds", but Explorer/Taskbar silently upscales the nearest
 * smaller frame and the artwork goes soft — worst exactly where the logo has
 * to read fastest (16x16 taskbar, 32x32 Alt+Tab).
 */
export const REQUIRED_WINDOWS_ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]

/**
 * Parse an .ico directory table into its frame sizes (width x height, with the
 * 0 -> 256 sentinel expanded). Returns [] for a non-ico buffer rather than
 * throwing, so the caller reports one clear "unreadable icon" error instead of
 * an opaque Buffer index crash.
 */
export function readIcoSizes(buf) {
  // ICONDIR: reserved(2) type(2)=1 count(2), then count x 16-byte ICONDIRENTRY.
  if (!Buffer.isBuffer(buf) || buf.length < 6 || buf.readUInt16LE(0) !== 0 || buf.readUInt16LE(2) !== 1) {
    return []
  }
  const count = buf.readUInt16LE(4)
  const sizes = []
  for (let i = 0; i < count; i++) {
    const off = 6 + i * 16
    if (off + 16 > buf.length) break
    // A dimension byte of 0 encodes 256 (the field is 1 byte, 8 bits wide).
    const w = buf[off] === 0 ? 256 : buf[off]
    const h = buf[off + 1] === 0 ? 256 : buf[off + 1]
    sizes.push(w === h ? w : `${w}x${h}`)
  }
  return sizes
}

/**
 * Verify the Windows icon assets the packaging config depends on.
 * Returns { ok: true, sizes } or { ok: false, reason }.
 */
export function checkWindowsIconAssets(projectDir) {
  const icoPath = path.join(projectDir, 'assets', 'icon.ico')
  if (!existsSync(icoPath)) {
    return { ok: false, reason: `missing Windows icon: ${icoPath}` }
  }
  const sizes = readIcoSizes(readFileSync(icoPath))
  if (sizes.length === 0) {
    return { ok: false, reason: `assets/icon.ico is not a readable .ico (empty or bad header)` }
  }
  const missing = REQUIRED_WINDOWS_ICON_SIZES.filter((s) => !sizes.includes(s))
  if (missing.length > 0) {
    return {
      ok: false,
      reason:
        `assets/icon.ico is missing frame(s) ${missing.join(', ')} ` +
        `(has ${sizes.join(', ')}). Windows will upscale a smaller frame and the ` +
        `Flo icon will look soft in the taskbar/Alt+Tab — regenerate the .ico ` +
        `with all of: ${REQUIRED_WINDOWS_ICON_SIZES.join(', ')}.`
    }
  }
  return { ok: true, sizes }
}

export function cleanStaleAppOutDir(appOutDir) {
  if (!appOutDir || typeof appOutDir !== 'string') {
    return false
  }
  if (!existsSync(appOutDir)) {
    return false
  }
  // Recursive + force so a half-written tree (read-only bits, partial files)
  // can't block the wipe. retry/maxRetries rides out transient EBUSY on
  // Windows where an AV/indexer may briefly hold a handle.
  rmSync(appOutDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
  return true
}

/**
 * Windows rollback material (#69179): before wiping the previous unpacked
 * tree, preserve it as `<appOutDir>.bak` — but ONLY when it holds the product
 * exe (i.e. it is a previously-working build, not the corrupted partial state
 * cleanStaleAppOutDir exists to remove). If the fresh pack then produces a
 * Hermes.exe that Windows can't load (truncated PE from a corrupt cached
 * Electron zip, wrong arch), the updater's integrity gate in
 * `hermes desktop --build-only` (hermes_cli/main.py
 * `_ensure_desktop_exe_launchable`) restores this .bak instead of leaving the
 * user with "This app can't run on your computer".
 *
 * Returns true when the tree was preserved (appOutDir no longer exists), false
 * when there was nothing worth preserving (caller falls through to the wipe).
 * A rename failure (AV holding a handle) also returns false — the wipe is the
 * safe fallback and matches pre-#69179 behavior exactly.
 */
export function preserveRollbackBackup(appOutDir, productExeName = 'Hermes.exe') {
  if (!appOutDir || typeof appOutDir !== 'string' || !existsSync(appOutDir)) {
    return false
  }
  if (!existsSync(path.join(appOutDir, productExeName))) {
    // Partial/corrupt tree (interrupted prior pack) — not rollback material.
    return false
  }
  const backupDir = `${appOutDir}.bak`
  try {
    rmSync(backupDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
    renameSync(appOutDir, backupDir)
    return true
  } catch {
    return false
  }
}

export default async function beforePack(context) {
  const appOutDir = context && context.appOutDir
  const platformName = context && context.electronPlatformName
  // The hook lives in scripts/, while package-owned assets live at the
  // desktop project root. Keep projectDir rooted at apps/desktop so the
  // Windows icon validator and any package-relative checks resolve assets.
  const projectDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

  // Branding gate. Runs before ANY staging so a bad icon never reaches a
  // packaged Flo.exe. Only enforced for Windows targets — the mac/Linux
  // packaging paths use icon.icns / a different asset entirely.
  if (platformName === 'win32') {
    const iconCheck = checkWindowsIconAssets(projectDir)
    if (!iconCheck.ok) {
      throw new Error(`[before-pack] ${iconCheck.reason}`)
    }
    console.log(`[before-pack] verified Windows icon frames: ${iconCheck.sizes.join(', ')}`)
  }

  try {
    // Windows: keep the previous working build as rollback material for the
    // post-build integrity gate (#69179) instead of destroying it. Falls
    // through to the plain wipe when the old tree is partial/corrupt or the
    // rename fails.
    const productExe = `${(context && context.packager?.appInfo?.productFilename) || 'Hermes'}.exe`
    if (platformName === 'win32' && preserveRollbackBackup(appOutDir, productExe)) {
      console.log(`[before-pack] preserved previous unpacked dir for rollback: ${appOutDir}.bak`)
    } else if (cleanStaleAppOutDir(appOutDir)) {
      console.log(`[before-pack] removed stale unpacked dir before staging: ${appOutDir}`)
    }
  } catch (err) {
    // Never fail the build over cleanup; surface why so a genuinely stuck
    // directory (permissions, mount) is still diagnosable.
    console.warn(`[before-pack] could not clean ${appOutDir} (${err.message}); continuing`)
  }

  try {
    const platform = context && context.electronPlatformName
    const archName = context && typeof context.arch === 'number' ? Arch[context.arch] : undefined
    if (platform && archName) {
      if (archName === 'universal') {
        console.warn(
          '[before-pack] target arch is "universal" — node-pty has no universal prebuild; ' +
            'staged binary will be whichever single-arch copy npm run build left behind. ' +
            'lipo-merge x64/arm64 .node files manually if you need a true universal build.'
        )
      } else {
        await stageNodePty({ platform, arch: archName })
        console.log(`[before-pack] re-staged node-pty for target ${platform}-${archName}`)
      }
      // The macOS helper is universal, while Windows bindings are arch-specific.
      // Pass the target arch so an ARM64 package never stages an x64 binding.
      stageGetWindows({ platform, arch: archName })
      console.log(`[before-pack] re-staged get-windows for target ${platform}-${archName}`)
    }
  } catch (err) {
    // Cross-building from Mac to Windows, the optional native modules
    // (get-windows, node-pty) were never built for win32 on this host —
    // they're Mac-only prebuilt binaries. Skip staging if the host is
    // not Windows; Windows installer users don't need them at install
    // time (window-below.ts treats them as optionalDependencies).
    if (process.platform === 'win32') {
      throw new Error(`[before-pack] failed to stage native deps for this target: ${err.message}`)
    }
    console.warn(`[before-pack] skipped native staging on ${process.platform}→${process.env.npm_config_target_platform || 'win'}: ${err.message}`)
  }
}
