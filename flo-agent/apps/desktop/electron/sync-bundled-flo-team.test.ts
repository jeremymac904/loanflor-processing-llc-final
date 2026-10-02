import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { syncBundledFloTeamPlugin } from './sync-bundled-flo-team'

test('syncs packaged Flo Team backend files without touching workspace data', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'flo-team-sync-'))
  const bundle = path.join(root, 'bundle')
  const hermesHome = path.join(root, 'hermes')
  const destination = path.join(hermesHome, 'plugins', 'flo-team')
  const workspace = path.join(hermesHome, 'flo', 'team', 'workspaces.json')
  fs.mkdirSync(path.join(bundle, 'dashboard'), { recursive: true })
  fs.mkdirSync(path.join(destination, '__pycache__'), { recursive: true })
  fs.mkdirSync(path.dirname(workspace), { recursive: true })
  fs.writeFileSync(path.join(bundle, 'mismo.py'), 'new parser')
  fs.writeFileSync(path.join(bundle, 'dashboard', 'plugin_api.py'), 'new intake route')
  fs.mkdirSync(path.join(destination, 'dashboard'), { recursive: true })
  fs.writeFileSync(path.join(destination, 'dashboard', 'plugin_api.py'), 'old route')
  fs.writeFileSync(path.join(destination, '__pycache__', 'plugin_api.pyc'), 'stale cache')
  fs.writeFileSync(workspace, '{"preserve":"loan data"}')

  try {
    const result = syncBundledFloTeamPlugin(bundle, hermesHome)
    assert.deepEqual(result, { status: 'synced', copiedFiles: 2 })
    assert.equal(fs.readFileSync(path.join(destination, 'mismo.py'), 'utf8'), 'new parser')
    assert.equal(fs.readFileSync(path.join(destination, 'dashboard', 'plugin_api.py'), 'utf8'), 'new intake route')
    assert.equal(fs.existsSync(path.join(destination, '__pycache__')), false)
    assert.equal(fs.readFileSync(workspace, 'utf8'), '{"preserve":"loan data"}')
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('refuses to write through a Flo Team plugin symlink', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'flo-team-sync-link-'))
  const bundle = path.join(root, 'bundle')
  const hermesHome = path.join(root, 'hermes')
  const pluginParent = path.join(hermesHome, 'plugins')
  const outside = path.join(root, 'outside')
  fs.mkdirSync(bundle, { recursive: true })
  fs.mkdirSync(pluginParent, { recursive: true })
  fs.mkdirSync(outside, { recursive: true })
  fs.symlinkSync(outside, path.join(pluginParent, 'flo-team'), 'junction')

  try {
    assert.throws(() => syncBundledFloTeamPlugin(bundle, hermesHome), /symbolic link/)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})
