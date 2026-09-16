/**
 * Flo release channel — the downstream updater policy.
 *
 * Invariant (ADR-008): the Flo desktop app must never self-update from the
 * upstream NousResearch/hermes-agent repository. Doing so would overwrite the
 * downstream build with stock Hermes. Every update entry point in
 * `electron/main.ts` (`checkUpdates`, `applyUpdates`, including the
 * `connections:update-all` bypass) and the first-run runtime bootstrap
 * (`electron/bootstrap-runner.ts`) consults this module first.
 *
 * Until Flo has its own release infrastructure the channel is `disabled`.
 * Turning it on means editing `flo/brand.config.json` `updates` with a Flo-owned git
 * source; a source that canonicalises to the upstream repository is rejected
 * here and the channel stays disabled. There is intentionally no environment
 * variable that overrides this — behavioural settings belong in checked-in
 * configuration, and a runtime toggle would be one more way to point a
 * customer install at upstream.
 */

import { canonicalGitHubRemote, OFFICIAL_REPO_CANONICAL } from '../electron/update-remote'

import { FLO_BRAND } from './brand'

export type FloReleaseMode = 'disabled' | 'flo-release'

export interface FloReleaseChannel {
  bootstrapSource: null | string
  mode: FloReleaseMode
  source: null | string
}

export type FloUpdateGateReason = 'flo-updates-disabled' | 'remote-mismatch' | 'upstream-remote-refused' | null

export interface FloUpdateGateResult {
  allowed: boolean
  message: string
  reason: FloUpdateGateReason
}

const DISABLED: FloReleaseChannel = { bootstrapSource: null, mode: 'disabled', source: null }

function nonEmptyString(value: unknown): null | string {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

/** True when `url` is (any form of) the upstream Hermes repository. */
export function isUpstreamHermesRemote(url: unknown): boolean {
  const canonical = canonicalGitHubRemote(url)

  return canonical !== '' && canonical === OFFICIAL_REPO_CANONICAL
}

/** Parse the `updates` block. Anything invalid or upstream-pointing → disabled. */
export function resolveFloReleaseChannel(raw: unknown = FLO_BRAND.updates): FloReleaseChannel {
  if (!raw || typeof raw !== 'object') {
    return DISABLED
  }

  const record = raw as Record<string, unknown>
  const mode = nonEmptyString(record.mode)
  const source = nonEmptyString(record.source)
  const bootstrapSource = nonEmptyString(record.bootstrapSource)

  if (mode !== 'flo-release') {
    return DISABLED
  }

  if (!source || isUpstreamHermesRemote(source)) {
    return DISABLED
  }

  if (
    bootstrapSource &&
    /github\.com\/nousresearch\/hermes-agent|raw\.githubusercontent\.com\/nousresearch\/hermes-agent/i.test(
      bootstrapSource
    )
  ) {
    return { bootstrapSource: null, mode: 'flo-release', source }
  }

  return { bootstrapSource, mode: 'flo-release', source }
}

/** Decide whether a self-update may check or apply against `originUrl`. */
export function floUpdateGate(
  originUrl: unknown,
  channel: FloReleaseChannel = resolveFloReleaseChannel()
): FloUpdateGateResult {
  if (channel.mode === 'disabled') {
    return {
      allowed: false,
      message: `${FLO_BRAND.productName} updates are not enabled in this build. ${FLO_BRAND.productName} never updates itself from the upstream ${FLO_BRAND.upstream.engineName} repository; a ${FLO_BRAND.productName}-owned release channel has to be configured first.`,
      reason: 'flo-updates-disabled'
    }
  }

  if (isUpstreamHermesRemote(originUrl)) {
    return {
      allowed: false,
      message: `This checkout tracks the upstream ${FLO_BRAND.upstream.engineName} repository. ${FLO_BRAND.productName} refuses to self-update from it.`,
      reason: 'upstream-remote-refused'
    }
  }

  const origin = canonicalGitHubRemote(originUrl)
  const expected = canonicalGitHubRemote(channel.source)

  if (!origin || !expected || origin !== expected) {
    return {
      allowed: false,
      message: `This checkout's git remote does not match the configured ${FLO_BRAND.productName} release source.`,
      reason: 'remote-mismatch'
    }
  }

  return { allowed: true, message: '', reason: null }
}

/** Raw-content base URL for first-run install scripts, or null (refuse). */
export function floBootstrapSource(channel: FloReleaseChannel = resolveFloReleaseChannel()): null | string {
  return channel.mode === 'flo-release' ? channel.bootstrapSource : null
}
