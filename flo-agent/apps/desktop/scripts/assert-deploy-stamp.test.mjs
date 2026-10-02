import assert from 'node:assert/strict'
import test from 'node:test'

import { validateDeployStamp } from './assert-deploy-stamp.mjs'

const commit = 'a'.repeat(40)
const stamp = { schemaVersion: 1, commit, dirty: false }

test('accepts a fresh clean package stamped from canonical HEAD', () => {
  assert.equal(validateDeployStamp({ stamp, head: commit, canonicalHead: commit, trackedChanges: false }), null)
})

test('rejects a stale package stamp', () => {
  assert.match(validateDeployStamp({ stamp: { ...stamp, commit: 'b'.repeat(40) }, head: commit, canonicalHead: commit }), /does not match source HEAD/)
})

test('rejects a source revision that is not the fetched canonical head', () => {
  assert.match(validateDeployStamp({ stamp, head: commit, canonicalHead: 'c'.repeat(40) }), /does not match origin\/flo\/codex-polish/)
})

test('rejects dirty build stamps and tracked source changes', () => {
  assert.match(validateDeployStamp({ stamp: { ...stamp, dirty: true }, head: commit, canonicalHead: commit }), /marked dirty/)
  assert.match(validateDeployStamp({ stamp, head: commit, canonicalHead: commit, trackedChanges: true }), /tracked modifications/)
})
