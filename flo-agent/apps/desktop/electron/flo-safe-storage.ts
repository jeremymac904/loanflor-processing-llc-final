/**
 * Return Electron's OS-backed safeStorage service when it is usable.
 *
 * Keep this deliberately small and dependency-free so the persistence
 * contract can be regression-tested without importing the Electron main
 * process.  The main process must pass its imported Electron safeStorage
 * object here; reading from globalThis is not reliable in packaged builds.
 */
export function getAvailableFloSafeStorage<T extends {
  encryptString?: (value: string) => Buffer
  decryptString?: (value: Buffer) => string
  isEncryptionAvailable?: () => boolean
}>(candidate: T | null | undefined): T | null {
  if (!candidate || typeof candidate.encryptString !== 'function' || typeof candidate.decryptString !== 'function') {
    return null
  }

  try {
    if (typeof candidate.isEncryptionAvailable === 'function' && !candidate.isEncryptionAvailable()) {
      return null
    }
  } catch {
    return null
  }

  return candidate
}
