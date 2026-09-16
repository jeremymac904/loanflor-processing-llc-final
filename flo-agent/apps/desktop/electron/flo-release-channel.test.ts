/**
 * Flo downstream invariant: the desktop app can never self-update from the
 * upstream NousResearch/hermes-agent repository (ADR-008).
 *
 * Run with: npx vitest run --project electron electron/flo-release-channel.test.ts
 */

import assert from 'node:assert/strict'

import { test } from 'vitest'

import { FLO_BRAND } from '../flo/brand'
import {
  floBootstrapSource,
  floUpdateGate,
  isUpstreamHermesRemote,
  resolveFloReleaseChannel
} from '../flo/release-channel'

import { OFFICIAL_REPO_HTTPS_URL } from './update-remote'

const UPSTREAM_FORMS = [
  OFFICIAL_REPO_HTTPS_URL,
  'https://github.com/NousResearch/hermes-agent',
  'git@github.com:NousResearch/hermes-agent.git',
  'ssh://git@github.com/nousresearch/hermes-agent.git',
  'https://github.com/nousresearch/hermes-agent/'
]

test('the shipped brand configuration keeps updates disabled', () => {
  const channel = resolveFloReleaseChannel()

  assert.equal(channel.mode, 'disabled')
  assert.equal(channel.source, null)
  assert.equal(channel.bootstrapSource, null)
  assert.equal(floBootstrapSource(channel), null)
})

test('every form of the upstream remote is recognised', () => {
  for (const url of UPSTREAM_FORMS) {
    assert.equal(isUpstreamHermesRemote(url), true, url)
  }

  assert.equal(isUpstreamHermesRemote('https://github.com/example-org/flo-agent.git'), false)
  assert.equal(isUpstreamHermesRemote(''), false)
  assert.equal(isUpstreamHermesRemote(null), false)
})

test('a disabled channel blocks checks and applies for every remote, including a Flo-owned one', () => {
  const channel = resolveFloReleaseChannel({ mode: 'disabled' })

  for (const url of [...UPSTREAM_FORMS, 'https://github.com/example-org/flo-agent.git', '']) {
    const gate = floUpdateGate(url, channel)

    assert.equal(gate.allowed, false, url)
    assert.equal(gate.reason, 'flo-updates-disabled')
    assert.match(gate.message, new RegExp(FLO_BRAND.productName))
  }
})

test('a release channel pointing at upstream is refused and collapses to disabled', () => {
  for (const url of UPSTREAM_FORMS) {
    const channel = resolveFloReleaseChannel({ mode: 'flo-release', source: url })

    assert.equal(channel.mode, 'disabled', url)
  }
})

test('an enabled Flo channel still refuses an upstream origin and mismatched remotes', () => {
  const channel = resolveFloReleaseChannel({
    mode: 'flo-release',
    source: 'https://github.com/example-org/flo-agent.git'
  })

  assert.equal(channel.mode, 'flo-release')

  for (const url of UPSTREAM_FORMS) {
    assert.equal(floUpdateGate(url, channel).reason, 'upstream-remote-refused', url)
  }

  assert.equal(floUpdateGate('git@github.com:someone-else/flo-agent.git', channel).reason, 'remote-mismatch')
  assert.equal(floUpdateGate('', channel).reason, 'remote-mismatch')

  const ok = floUpdateGate('git@github.com:example-org/flo-agent.git', channel)

  assert.equal(ok.allowed, true)
  assert.equal(ok.reason, null)
})

test('bootstrap source is null unless a non-upstream Flo source is configured', () => {
  assert.equal(floBootstrapSource(resolveFloReleaseChannel({ mode: 'disabled', bootstrapSource: 'https://x' })), null)

  const upstreamRaw = resolveFloReleaseChannel({
    mode: 'flo-release',
    source: 'https://github.com/example-org/flo-agent.git',
    bootstrapSource: 'https://raw.githubusercontent.com/NousResearch/hermes-agent'
  })

  assert.equal(floBootstrapSource(upstreamRaw), null)

  const floRaw = resolveFloReleaseChannel({
    mode: 'flo-release',
    source: 'https://github.com/example-org/flo-agent.git',
    bootstrapSource: 'https://raw.githubusercontent.com/example-org/flo-agent'
  })

  assert.equal(floBootstrapSource(floRaw), 'https://raw.githubusercontent.com/example-org/flo-agent')
})

test('malformed configuration fails closed', () => {
  for (const raw of [
    null,
    undefined,
    'flo-release',
    42,
    {},
    { mode: 'flo-release' },
    { mode: 'flo-release', source: '' }
  ]) {
    assert.equal(resolveFloReleaseChannel(raw).mode, 'disabled')
  }
})
