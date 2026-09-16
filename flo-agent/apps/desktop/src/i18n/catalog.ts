import { ar } from './ar'
import { en } from './en'
import { rebrandCatalog } from './flo-rebrand'
import { ja } from './ja'
import type { Locale, Translations } from './types'
import { zh } from './zh'
import { zhHant } from './zh-hant'

// Flo downstream: the upstream catalogs stay untouched; the product name is
// rewritten once here (see src/i18n/flo-rebrand.ts and flo/brand.ts).
export const TRANSLATIONS: Record<Locale, Translations> = rebrandCatalog({
  en,
  zh,
  'zh-hant': zhHant,
  ja,
  ar
})
