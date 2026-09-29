type SafeStorageLike = {
  decryptString: (value: Buffer) => string
  encryptString: (value: string) => Buffer
}

type StoredProviderCredential = {
  encryptedSecret: string
  storage: 'safeStorage'
  storedAt: string
}

type FloSecretStore = {
  providerCredentials?: Record<string, Record<string, StoredProviderCredential>>
  [key: string]: unknown
}

const GLOBAL_SCOPE = '__global__'
const PROVIDER_ENV_KEY = /^[A-Z][A-Z0-9_]*(?:_API_KEY|_TOKEN)$/

export function isProviderCredentialEnvKey(key: string): boolean {
  return PROVIDER_ENV_KEY.test(key)
}

function scopeFor(profile?: string): string {
  return profile?.trim() || GLOBAL_SCOPE
}

export function saveProviderCredentialRecord(
  store: FloSecretStore,
  key: string,
  value: string,
  safeStorage: SafeStorageLike,
  profile?: string
): FloSecretStore {
  if (!isProviderCredentialEnvKey(key)) throw new Error('Unsupported provider credential field')
  if (!value.trim()) throw new Error('A provider credential is required')

  const scope = scopeFor(profile)
  const current = store.providerCredentials ?? {}
  return {
    ...store,
    providerCredentials: {
      ...current,
      [scope]: {
        ...(current[scope] ?? {}),
        [key]: {
          encryptedSecret: safeStorage.encryptString(value).toString('base64'),
          storage: 'safeStorage',
          storedAt: new Date().toISOString()
        }
      }
    }
  }
}

export function deleteProviderCredentialRecord(store: FloSecretStore, key: string, profile?: string): FloSecretStore {
  if (!isProviderCredentialEnvKey(key)) throw new Error('Unsupported provider credential field')
  const scope = scopeFor(profile)
  const current = store.providerCredentials ?? {}
  const nextScope = { ...(current[scope] ?? {}) }
  delete nextScope[key]
  const next = { ...current }
  if (Object.keys(nextScope).length) next[scope] = nextScope
  else delete next[scope]
  return { ...store, providerCredentials: next }
}

export function providerCredentialEnvironment(
  store: FloSecretStore,
  safeStorage: SafeStorageLike,
  profile?: string
): Record<string, string> {
  if (!safeStorage) return {}
  const all = store.providerCredentials ?? {}
  const rows = { ...(all[GLOBAL_SCOPE] ?? {}), ...(profile ? (all[scopeFor(profile)] ?? {}) : {}) }
  const env: Record<string, string> = {}
  for (const [key, row] of Object.entries(rows)) {
    if (!isProviderCredentialEnvKey(key) || row?.storage !== 'safeStorage' || !row.encryptedSecret) continue
    try {
      env[key] = safeStorage.decryptString(Buffer.from(row.encryptedSecret, 'base64'))
    } catch {
      // Keep an unreadable credential out of the backend environment; never
      // log the ciphertext or plaintext. The UI will show the provider as not
      // connected until the credential is re-entered.
    }
  }
  return env
}
