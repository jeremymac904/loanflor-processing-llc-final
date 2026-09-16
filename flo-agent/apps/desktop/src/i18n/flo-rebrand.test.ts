import { afterEach, describe, expect, it } from 'vitest'

import { FLO_BRAND } from '../../flo/brand'

import { TRANSLATIONS } from './catalog'
import { registerPluginLocales, translatePlugin } from './plugin-i18n'
import { setRuntimeI18nLocale, translateNow } from './runtime'
import type { Locale } from './types'

function walkStrings(value: unknown, visit: (text: string, path: string) => void, path = ''): void {
  if (typeof value === 'string') {
    visit(value, path)
  } else if (typeof value === 'function') {
    // Interpolators are checked by calling them with representative string
    // args; interpolators with other arg shapes are skipped (they still go
    // through rebrandText at render time — see runtime.ts).
    try {
      const rendered = (value as (...args: unknown[]) => unknown)('2', '2', '2')

      if (typeof rendered === 'string') {
        visit(rendered, path)
      }
    } catch {
      // arg-shape mismatch; not a brand assertion failure
    }
  } else if (Array.isArray(value)) {
    value.forEach((item, index) => walkStrings(item, visit, `${path}[${index}]`))
  } else if (value && typeof value === 'object') {
    for (const [key, item] of Object.entries(value)) {
      walkStrings(item, visit, path ? `${path}.${key}` : key)
    }
  }
}

describe('Flo rebrand at the i18n boundary', () => {
  afterEach(() => {
    setRuntimeI18nLocale('en')
  })

  it('leaves no bare upstream product name in any locale catalog', () => {
    const offenders: string[] = []

    for (const locale of Object.keys(TRANSLATIONS) as Locale[]) {
      walkStrings(TRANSLATIONS[locale], (text, path) => {
        const stripped = text
          .split('Hermes Cloud')
          .join('')
          .split('Hermes Skills Hub')
          .join('')
          .split('Nous Hermes')
          .join('')

        if (/\bHermes\b/.test(stripped)) {
          offenders.push(`${locale}:${path}: ${text}`)
        }
      })
    }

    expect(offenders).toEqual([])
  })

  it('shows the Flo product name in headline user-facing strings', () => {
    expect(translateNow('boot.ready')).toContain(FLO_BRAND.productName)
    expect(TRANSLATIONS.en.settings.about.heading).toContain(FLO_BRAND.productName)
    expect(TRANSLATIONS.en.settings.about.heading).not.toContain('Hermes')
  })

  it('keeps internal identifiers such as commands, paths and env vars intact', () => {
    const offenders: string[] = []

    walkStrings(TRANSLATIONS.en, (text, path) => {
      if (/\bflo (serve|update|dashboard|setup)\b|~\/\.flo\b|FLO_HOME/.test(text)) {
        offenders.push(`${path}: ${text}`)
      }
    })

    expect(offenders).toEqual([])
  })

  it('applies to plugin locale bundles too', () => {
    const dispose = registerPluginLocales('flo-test-plugin', {
      en: { title: 'Hermes Agent panel', count: (n: number) => `${n} Hermes items` }
    })

    try {
      expect(translatePlugin('flo-test-plugin', 'en', 'title', [])).toBe(`${FLO_BRAND.productName} panel`)
      expect(translatePlugin('flo-test-plugin', 'en', 'count', [3])).toBe(`3 ${FLO_BRAND.productName} items`)
    } finally {
      dispose()
    }
  })
})
