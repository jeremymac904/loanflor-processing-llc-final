import fs from 'node:fs'
import path from 'node:path'

export type FloTeamSyncResult = { status: 'missing-bundle' | 'synced'; copiedFiles: number }

/**
 * Refresh the first-party Flo Team backend plugin from the version shipped with
 * Flo before Hermes profile servers are spawned. The plugin source is managed
 * separately from Electron userData; keeping it in the app package prevents a
 * new renderer from calling routes that an older Hermes plugin does not have.
 * Loan/workspace data remains under HERMES_HOME/flo and is never touched here.
 */
export function syncBundledFloTeamPlugin(bundleDir: string, hermesHome: string): FloTeamSyncResult {
  const sourceRoot = path.resolve(bundleDir)
  const homeRoot = path.resolve(hermesHome)
  const sourceStat = safeLstat(sourceRoot)

  if (!sourceStat?.isDirectory() || sourceStat.isSymbolicLink()) {
    return { status: 'missing-bundle', copiedFiles: 0 }
  }

  const pluginsRoot = path.join(homeRoot, 'plugins')
  ensureDirectoryWithoutSymlink(homeRoot)
  ensureDirectoryWithoutSymlink(pluginsRoot)
  const destinationRoot = path.join(pluginsRoot, 'flo-team')
  ensureDirectoryWithoutSymlink(destinationRoot)

  // Bytecode caches can shadow a same-size/same-timestamp Python update. They
  // are generated files only; remove just this plugin's __pycache__ folders.
  removeBytecodeCaches(destinationRoot)

  let copiedFiles = 0
  copyTree(destinationRoot, sourceRoot, destinationRoot, () => copiedFiles++)
  return { status: 'synced', copiedFiles }
}

function safeLstat(target: string): fs.Stats | null {
  try {
    return fs.lstatSync(target)
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null
    throw error
  }
}

function ensureDirectoryWithoutSymlink(directory: string): void {
  const existing = safeLstat(directory)
  if (existing?.isSymbolicLink()) throw new Error(`Refusing to update Flo Team through a symbolic link: ${directory}`)
  if (existing && !existing.isDirectory()) throw new Error(`Flo Team runtime path is not a directory: ${directory}`)
  if (!existing) fs.mkdirSync(directory)
}

function copyTree(destinationRoot: string, source: string, destination: string, copied: () => void): void {
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    if (entry.name === '__pycache__' || entry.name.endsWith('.pyc')) continue
    const from = path.join(source, entry.name)
    const to = path.join(destination, entry.name)
    const sourceStat = fs.lstatSync(from)
    if (sourceStat.isSymbolicLink()) continue
    if (sourceStat.isDirectory()) {
      ensureDirectoryWithin(destinationRoot, to)
      copyTree(destinationRoot, from, to, copied)
      continue
    }
    if (!sourceStat.isFile()) continue

    ensureDirectoryWithin(destinationRoot, path.dirname(to))
    const existing = safeLstat(to)
    if (existing?.isSymbolicLink()) throw new Error(`Refusing to overwrite a symbolic link in the Flo Team plugin: ${to}`)
    if (existing && !existing.isFile()) throw new Error(`Unexpected Flo Team plugin path: ${to}`)
    if (existing && existing.size === sourceStat.size && fs.readFileSync(from).equals(fs.readFileSync(to))) continue
    fs.copyFileSync(from, to)
    copied()
  }
}

function ensureDirectoryWithin(root: string, directory: string): void {
  const relative = path.relative(root, directory)
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error('Bundled Flo Team file escaped its destination directory.')
  }
  const chain: string[] = []
  let current = directory
  while (current !== root && path.dirname(current) !== current) {
    chain.unshift(current)
    current = path.dirname(current)
  }
  if (current !== root) throw new Error('Flo Team destination is outside the plugin directory.')
  for (const item of chain) ensureDirectoryWithoutSymlink(item)
}

function removeBytecodeCaches(root: string): void {
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const target = path.join(root, entry.name)
    if (entry.isSymbolicLink()) continue
    if (entry.isDirectory() && entry.name === '__pycache__') {
      fs.rmSync(target, { recursive: true, force: true })
    } else if (entry.isDirectory()) {
      removeBytecodeCaches(target)
    }
  }
}
