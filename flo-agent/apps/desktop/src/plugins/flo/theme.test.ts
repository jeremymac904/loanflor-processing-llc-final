import { describe, expect, it } from 'vitest'

import { FLO_THEME_NAME, floTheme } from './theme'

const REQUIRED = [
  'background',
  'foreground',
  'card',
  'cardForeground',
  'muted',
  'mutedForeground',
  'popover',
  'popoverForeground',
  'primary',
  'primaryForeground',
  'secondary',
  'secondaryForeground',
  'accent',
  'accentForeground',
  'border',
  'input',
  'ring',
  'destructive',
  'destructiveForeground'
] as const

describe('Flo desktop theme', () => {
  it('is a complete light + dark theme with a distinct name', () => {
    expect(floTheme.name).toBe(FLO_THEME_NAME)
    expect(floTheme.name).not.toBe('flo') // would be shadowed by the backend CLI skin of that name
    expect(floTheme.description).toBeTruthy()

    for (const key of REQUIRED) {
      expect(floTheme.colors[key]).toMatch(/^#[0-9a-f]{6}$/)
      expect(floTheme.darkColors[key]).toMatch(/^#[0-9a-f]{6}$/)
    }
  })

  it('uses the LoanFlow brand: green primary, gold accent stroke', () => {
    expect(floTheme.colors.primary).toBe('#1f5a2d')
    expect(floTheme.colors.midground).toBe('#b8964a')
    expect(floTheme.darkColors.midground).toBe('#d8c08a')
  })
})
