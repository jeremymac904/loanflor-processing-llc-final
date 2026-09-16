/**
 * Flo desktop theme — LoanFlow Processing brand: deep forest greens, muted
 * gold, cream highlights (see .flo/assets/palette.json, sampled from the
 * supplied logo sheet). Registered by the Flo plugin under THEMES_AREA and
 * selected once on first launch; Ashley can switch themes in Appearance.
 *
 * Named `flo-desktop` so it never collides with the backend CLI skin `flo`
 * (a backend skin of the same name would shadow a contributed theme).
 */

const SANS = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
const MONO = 'ui-monospace, "Cascadia Code", "SF Mono", Menlo, Consolas, monospace'

const GREEN_DEEP = '#1f5a2d'
const GREEN_LEAF = '#3f8f3a'
const GOLD = '#b8964a'
const GOLD_LIGHT = '#d8c08a'
const CREAM = '#f7f2e6'
const CREAM_DEEP = '#efe6d0'

export const FLO_THEME_NAME = 'flo-desktop'

export const floTheme = {
  name: FLO_THEME_NAME,
  label: 'Flo',
  description: 'LoanFlow Processing greens and gold',
  colors: {
    background: '#fbf9f3',
    foreground: '#1e2a22',
    card: CREAM,
    cardForeground: '#1e2a22',
    muted: CREAM_DEEP,
    mutedForeground: '#5f6b62',
    popover: '#ffffff',
    popoverForeground: '#1e2a22',
    primary: GREEN_DEEP,
    primaryForeground: '#ffffff',
    secondary: '#e2efdf',
    secondaryForeground: '#1e2a22',
    accent: '#eef5ea',
    accentForeground: '#1e2a22',
    border: '#d9d2bf',
    input: '#ffffff',
    ring: GOLD,
    midground: GOLD,
    midgroundForeground: '#1e2a22',
    composerRing: GREEN_LEAF,
    destructive: '#b3261e',
    destructiveForeground: '#ffffff',
    sidebarBackground: CREAM,
    sidebarBorder: '#d9d2bf',
    userBubble: '#e2efdf',
    userBubbleBorder: '#c9dcc5'
  },
  darkColors: {
    background: '#0f1a13',
    foreground: '#ecefe6',
    card: '#14231a',
    cardForeground: '#ecefe6',
    muted: '#1a2b20',
    mutedForeground: '#9aa89d',
    popover: '#14231a',
    popoverForeground: '#ecefe6',
    primary: '#8fbf8a',
    primaryForeground: '#0f1a13',
    secondary: '#1f3a27',
    secondaryForeground: '#ecefe6',
    accent: '#1a2f21',
    accentForeground: '#ecefe6',
    border: '#2c3f31',
    input: '#0f1a13',
    ring: GOLD_LIGHT,
    midground: GOLD_LIGHT,
    midgroundForeground: '#0f1a13',
    composerRing: '#8fbf8a',
    destructive: '#ff6b60',
    destructiveForeground: '#ffffff',
    sidebarBackground: '#0b140e',
    sidebarBorder: '#2c3f31',
    userBubble: '#1f3a27',
    userBubbleBorder: '#2c3f31'
  },
  typography: {
    fontSans: SANS,
    fontMono: MONO
  },
  terminal: {
    foreground: '#1e2a22',
    black: '#1e2a22',
    red: '#b3261e',
    green: GREEN_DEEP,
    yellow: '#8a6a1f',
    blue: '#2b5f8a',
    magenta: '#7a4b8f',
    cyan: '#2a7a7a',
    white: '#8a9188',
    brightBlack: '#5f6b62',
    brightRed: '#d0392f',
    brightGreen: GREEN_LEAF,
    brightYellow: GOLD,
    brightBlue: '#3b7fb8',
    brightMagenta: '#9a63b5',
    brightCyan: '#3a9c9c',
    brightWhite: '#b5bcb2'
  },
  darkTerminal: {
    foreground: '#ecefe6',
    black: '#2c3f31',
    red: '#ff6b60',
    green: '#8fbf8a',
    yellow: GOLD_LIGHT,
    blue: '#7fb3e0',
    magenta: '#c39ad8',
    cyan: '#7fd0d0',
    white: '#b5bcb2',
    brightBlack: '#5f6b62',
    brightRed: '#ff8f85',
    brightGreen: '#a9d8a4',
    brightYellow: '#e8d4a6',
    brightBlue: '#9ec8ec',
    brightMagenta: '#d6b6e6',
    brightCyan: '#a0e0e0',
    brightWhite: '#ffffff'
  }
}
