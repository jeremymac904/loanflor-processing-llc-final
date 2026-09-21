import floPetSpritesheetUrl from './assets/flo-pet-spritesheet.png'

import { persistBoolean, storedBoolean } from '@/lib/storage'
import type { PetInfo } from '@/store/pet'

export const FLO_PET_ENABLED_KEY = 'flo.pet.enabled'

/**
 * Flo uses Hermes' existing Petdex renderer and activity state machine. This
 * bundled fallback keeps the assistant visible before a local Petdex gallery
 * is configured; the normal gateway pet still wins whenever one is active.
 */
export const FLO_PET_INFO: PetInfo = {
  displayName: 'Flo',
  enabled: true,
  frameH: 208,
  frameW: 192,
  framesPerState: 6,
  loopMs: 1100,
  mime: 'image/png',
  scale: 0.33,
  slug: 'flo',
  spritesheetUrl: floPetSpritesheetUrl,
  stateRows: ['idle', 'running-right', 'running-left', 'waving', 'jumping', 'failed', 'waiting', 'running', 'review']
}

export function isFloPetEnabled(): boolean {
  return storedBoolean(FLO_PET_ENABLED_KEY, true)
}

export function setFloPetEnabled(enabled: boolean): void {
  persistBoolean(FLO_PET_ENABLED_KEY, enabled)
}
