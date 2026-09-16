/**
 * Flo downstream: rebrand the i18n catalogs at the resolution boundary.
 *
 * The upstream locale files stay byte-identical (mergeable); every string
 * that reaches the UI — via `useI18n().t.*`, `translateNow`, or plugin
 * translators — has the upstream product name replaced with Flo's. See
 * `flo/brand.ts` for what is and is not rewritten.
 */

import { rebrandMessages, rebrandText } from '../../flo/brand'

import type { Locale, Translations } from './types'

export function rebrandCatalog(catalog: Record<Locale, Translations>): Record<Locale, Translations> {
  const out = {} as Record<Locale, Translations>

  for (const [locale, translations] of Object.entries(catalog) as [Locale, Translations][]) {
    out[locale] = rebrandMessages(translations)
  }

  return out
}

export { rebrandText }
