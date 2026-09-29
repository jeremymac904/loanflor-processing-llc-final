import { describe, expect, it } from 'vitest'

import {
  deleteProviderCredentialRecord,
  isProviderCredentialEnvKey,
  providerCredentialEnvironment,
  saveProviderCredentialRecord
} from './flo-provider-secrets'

const safeStorage = {
  encryptString: (value: string) => Buffer.from(`dpapi:${value}`, 'utf8'),
  decryptString: (value: Buffer) => {
    const decoded = value.toString('utf8')
    if (!decoded.startsWith('dpapi:')) throw new Error('invalid encrypted payload')
    return decoded.slice('dpapi:'.length)
  }
}

describe('Flo provider credential storage', () => {
  it('stores only an encrypted payload and restores it into the backend environment', () => {
    const secret = 'synthetic-provider-secret'
    const saved = saveProviderCredentialRecord({}, 'OPENAI_API_KEY', secret, safeStorage, 'flo')
    const serialized = JSON.stringify(saved)

    expect(serialized).not.toContain(secret)
    expect(saved.providerCredentials?.flo?.OPENAI_API_KEY.encryptedSecret).toBeTruthy()
    expect(providerCredentialEnvironment(saved, safeStorage, 'flo')).toEqual({ OPENAI_API_KEY: secret })
  })

  it('inherits global credentials and applies a profile-specific override', () => {
    const global = saveProviderCredentialRecord({}, 'GEMINI_API_KEY', 'global', safeStorage)
    const profile = saveProviderCredentialRecord(global, 'GEMINI_API_KEY', 'flo-only', safeStorage, 'flo')
    expect(providerCredentialEnvironment(profile, safeStorage, 'flo').GEMINI_API_KEY).toBe('flo-only')
    expect(providerCredentialEnvironment(profile, safeStorage, 'sage').GEMINI_API_KEY).toBe('global')
  })

  it('removes only the selected profile credential', () => {
    const global = saveProviderCredentialRecord({}, 'OPENAI_API_KEY', 'global', safeStorage)
    const profile = saveProviderCredentialRecord(global, 'OPENAI_API_KEY', 'profile', safeStorage, 'flo')
    const removed = deleteProviderCredentialRecord(profile, 'OPENAI_API_KEY', 'flo')
    expect(providerCredentialEnvironment(removed, safeStorage, 'flo').OPENAI_API_KEY).toBe('global')
  })

  it('rejects non-provider or arbitrary credential field names', () => {
    expect(isProviderCredentialEnvKey('OPENAI_API_KEY')).toBe(true)
    expect(isProviderCredentialEnvKey('ANTHROPIC_TOKEN')).toBe(true)
    expect(isProviderCredentialEnvKey('PATH')).toBe(false)
    expect(() => saveProviderCredentialRecord({}, 'PATH', 'value', safeStorage)).toThrow()
  })
})
