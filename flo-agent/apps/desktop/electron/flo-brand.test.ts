/**
 * Flo downstream packaging invariants: the user-visible identity in
 * package.json's electron-builder block must agree with flo/brand.config.json, and
 * no user-visible packaging string may still say Hermes. Internal identifiers
 * (npm package name, workspace names, env vars) are deliberately not covered —
 * they stay Hermes for upstream compatibility.
 *
 * Run with: npx vitest run --project electron electron/flo-brand.test.ts
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

import { test } from 'vitest'

import { FLO_BRAND, PRESERVED_UPSTREAM_TERMS, rebrandMessages, rebrandText } from '../flo/brand'
import { isUpstreamHermesRemote } from '../flo/release-channel'

const pkg = JSON.parse(fs.readFileSync(path.resolve(__dirname, '..', 'package.json'), 'utf8'))
const build = pkg.build

test('electron-builder identity fields follow flo/brand.config.json', () => {
  assert.equal(pkg.productName, FLO_BRAND.productName)
  assert.equal(build.productName, FLO_BRAND.productName)
  assert.equal(build.executableName, FLO_BRAND.productName)
  assert.equal(build.appId, FLO_BRAND.appId)
  assert.equal(build.protocols[0].name, FLO_BRAND.protocolName)
  assert.deepEqual(build.protocols[0].schemes, [FLO_BRAND.protocolScheme])
  assert.ok(String(build.artifactName).startsWith(`${FLO_BRAND.artifactPrefix}-`), build.artifactName)
  assert.equal(build.mac.extendInfo.CFBundleDisplayName, FLO_BRAND.productName)
  assert.equal(build.mac.extendInfo.CFBundleName, FLO_BRAND.productName)
  assert.equal(build.mac.extendInfo.CFBundleExecutable, FLO_BRAND.productName)
  assert.equal(build.nsis.shortcutName, FLO_BRAND.productName)
  assert.equal(build.nsis.uninstallDisplayName, FLO_BRAND.productName)
})

test('no user-visible packaging string still says Hermes', () => {
  const visible: Array<[string, unknown]> = [
    ['productName', pkg.productName],
    ['description', pkg.description],
    ['build.productName', build.productName],
    ['build.executableName', build.executableName],
    ['build.protocols[0].name', build.protocols[0].name],
    ['build.artifactName', build.artifactName],
    ['build.dmg.title', build.dmg.title],
    ['build.win.legalTrademarks', build.win.legalTrademarks],
    ['build.linux.synopsis', build.linux.synopsis],
    ['build.nsis.shortcutName', build.nsis.shortcutName],
    ['build.nsis.uninstallDisplayName', build.nsis.uninstallDisplayName],
    ...Object.entries(build.mac.extendInfo).map(
      ([key, value]) => [`build.mac.extendInfo.${key}`, value] as [string, unknown]
    )
  ]

  for (const [label, value] of visible) {
    const text = String(value)
    const stripped = PRESERVED_UPSTREAM_TERMS.reduce((acc, term) => acc.split(term).join(''), text)

    // "built on Hermes Agent" attribution is allowed; a bare product label is not.
    assert.ok(!/^Hermes\b/.test(stripped) && !/\bHermes\b(?! Agent)/.test(stripped), `${label}: ${text}`)
  }
})

test('the deep-link scheme is not the upstream scheme', () => {
  assert.notEqual(FLO_BRAND.protocolScheme, 'hermes')
  assert.match(FLO_BRAND.protocolScheme, /^[a-z][a-z0-9-]*$/)
})

test('the release source never points at upstream', () => {
  const { source, bootstrapSource } = FLO_BRAND.updates

  assert.equal(isUpstreamHermesRemote(source), false)
  assert.ok(!bootstrapSource || !/nousresearch\/hermes-agent/i.test(bootstrapSource))
})

test('rebrandText replaces the product name but preserves internal identifiers and upstream product names', () => {
  assert.equal(rebrandText('Hermes Desktop is ready'), `${FLO_BRAND.productName} is ready`)
  assert.equal(
    rebrandText("Let's get you setup with Hermes Agent"),
    `Let's get you setup with ${FLO_BRAND.productName}`
  )
  assert.equal(rebrandText('About Hermes'), `About ${FLO_BRAND.productName}`)
  assert.equal(
    rebrandText('Run `hermes update` in ~/.hermes with HERMES_HOME set'),
    'Run `hermes update` in ~/.hermes with HERMES_HOME set'
  )
  assert.equal(rebrandText('Connect to Hermes Cloud'), 'Connect to Hermes Cloud')
  assert.equal(rebrandText('Hermes Skills Hub'), 'Hermes Skills Hub')
  assert.equal(rebrandText('Hermes Cloud and Hermes'), `Hermes Cloud and ${FLO_BRAND.productName}`)
  assert.equal(rebrandText('Hermes Cloud, 2 3 items, Hermes Cloud'), 'Hermes Cloud, 2 3 items, Hermes Cloud')
  assert.equal(rebrandText('no brand here'), 'no brand here')
})

test('rebrandMessages maps nested trees and interpolator functions', () => {
  const tree = rebrandMessages({
    a: 'Hermes',
    nested: { b: (n: number) => `${n} Hermes Desktop items`, list: ['Hermes', 'ok'] },
    keep: 42
  })

  assert.equal(tree.a, FLO_BRAND.productName)
  assert.equal(tree.nested.b(2), `2 ${FLO_BRAND.productName} items`)
  assert.deepEqual(tree.nested.list, [FLO_BRAND.productName, 'ok'])
  assert.equal(tree.keep, 42)
})
