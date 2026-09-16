/**
 * Flo downstream brand — typed access to `flo/brand.config.json` plus the one text
 * transform the renderer applies at the i18n boundary.
 *
 * Why a transform instead of editing ~150 catalog literals per locale: the
 * upstream catalogs (`src/i18n/*.ts`) change every release. Rewriting them
 * would put Flo in permanent merge conflict with upstream for zero product
 * value. Rebranding at the resolution boundary keeps the catalogs byte-
 * identical to upstream while every user-visible string still says Flo.
 *
 * Internal identifiers are deliberately untouched: the replacement is
 * case-sensitive on the capitalised product name, so `hermes serve`,
 * `~/.hermes`, `HERMES_HOME`, `hermes update`, package names and URLs pass
 * through unchanged. A short list of upstream product names that are NOT
 * Flo (Hermes Cloud, the Skills Hub) is preserved verbatim.
 */

import brand from './brand.config.json'

export interface FloUpdatesConfig {
  bootstrapSource: null | string
  mode: string
  source: null | string
}

export interface FloBrand {
  appId: string
  appIdIsPlaceholder: boolean
  artifactPrefix: string
  assistantName: string
  copyright: string
  displayName: string
  productName: string
  protocolName: string
  protocolScheme: string
  publisher: string
  updates: FloUpdatesConfig
  upstream: {
    engineName: string
    license: string
    pinnedTag: string
    vendor: string
  }
}

export const FLO_BRAND: FloBrand = brand as FloBrand

/** Upstream names that stay as they are — they name Nous products, not Flo. */
export const PRESERVED_UPSTREAM_TERMS: readonly string[] = ['Hermes Cloud', 'Hermes Skills Hub', 'Nous Hermes']

// Private-use-area sentinels bracket preserved terms while the generic
// replacement runs; they cannot collide with catalog text.
const HOLD_OPEN = ''
const HOLD_CLOSE = ''
const HOLD_PATTERN = /(\d+)/g

/** Replace the user-visible upstream product name with the Flo product name. */
export function rebrandText(text: string): string {
  if (!text.includes('Hermes')) {
    return text
  }

  const held: string[] = []
  let out = text

  for (const term of PRESERVED_UPSTREAM_TERMS) {
    if (out.includes(term)) {
      const index = held.push(term) - 1
      out = out.split(term).join(`${HOLD_OPEN}${index}${HOLD_CLOSE}`)
    }
  }

  out = out
    .replace(/\bHermes (?:Desktop|Agent)\b/g, FLO_BRAND.productName)
    .replace(/\bHermes\b/g, FLO_BRAND.productName)

  return out.replace(HOLD_PATTERN, (_match, index: string) => held[Number(index)] ?? '')
}

/** Deep-map a message tree (strings, interpolator functions, arrays, objects). */
export function rebrandMessages<T>(value: T): T {
  if (typeof value === 'string') {
    return rebrandText(value) as unknown as T
  }

  if (typeof value === 'function') {
    const fn = value as unknown as (...args: unknown[]) => unknown

    return ((...args: unknown[]) => {
      const result = fn(...args)

      return typeof result === 'string' ? rebrandText(result) : result
    }) as unknown as T
  }

  if (Array.isArray(value)) {
    return value.map(item => rebrandMessages(item)) as unknown as T
  }

  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {}

    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      out[key] = rebrandMessages(item)
    }

    return out as T
  }

  return value
}

/** Deep-link schemes the renderer accepts. The OS-registered scheme is Flo's;
 *  the upstream scheme stays accepted as an internal alias so plugin docs and
 *  notification payloads that still say `hermes://` keep resolving. */
export const DEEP_LINK_SCHEMES: readonly string[] = [FLO_BRAND.protocolScheme, 'hermes']
