import { readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// @assistant-ui/core 0.2.23 creates a fresh ThreadListState object in
// LazyMemoizeSubject's binding while the subject is disconnected. React calls
// getSnapshot more than once before subscribing, so that violates the
// useSyncExternalStore snapshot contract and can loop forever. Keep this
// narrowly guarded until the upstream package contains the equivalent fix.
const here = dirname(fileURLToPath(import.meta.url))
const packageRoot = resolve(here, '../../../node_modules/@assistant-ui/core')
const packageJson = JSON.parse(await readFile(resolve(packageRoot, 'package.json'), 'utf8'))

if (packageJson.version !== '0.2.23') {
  throw new Error(`Expected @assistant-ui/core 0.2.23, found ${packageJson.version}`)
}

const target = resolve(packageRoot, 'dist/subscribable/subscribable.js')
let source = await readFile(target, 'utf8')
const original = 'if (!this.isConnected || this._previousStateDirty) {'
const fixed = 'if (this._previousStateDirty) {'

if (source.includes(original)) {
  source = source.replace(original, fixed)
  await writeFile(target, source)
  console.log(`[patch-assistant-ui-runtime-state] patched ${target}`)
} else if (source.includes(fixed)) {
  console.log(`[patch-assistant-ui-runtime-state] already patched ${target}`)
} else {
  throw new Error('Unexpected @assistant-ui/core LazyMemoizeSubject implementation')
}
