import { beforeEach, describe, expect, it, vi } from 'vitest'

const { request, openSession } = vi.hoisted(() => ({ request: vi.fn(), openSession: vi.fn() }))

vi.mock('@hermes/plugin-sdk', () => ({
  host: { openSession, request, notifyError: vi.fn() }
}))

import { startFloChat } from './chat'

describe('Flo chat startup', () => {
  beforeEach(() => {
    request.mockReset()
    openSession.mockReset()
    request.mockResolvedValueOnce({ session_id: 'runtime-1', stored_session_id: 'stored-1' })
    request.mockResolvedValue(undefined)
    openSession.mockResolvedValue(undefined)
  })

  it('hydrates the created Flo session after its first turn for follow-up prompts', async () => {
    await startFloChat('Hello', 'Hi Flo', 'flo')

    expect(openSession).toHaveBeenCalledWith('stored-1', {
      profile: 'flo',
      intent: 'in-place',
      awaitHydration: true,
      expectHistory: true,
      forceResume: true
    })
    expect(request).toHaveBeenNthCalledWith(3, 'prompt.submit', { session_id: 'runtime-1', text: 'Hi Flo' })
    expect(request).toHaveBeenLastCalledWith('prompt.submit', { session_id: 'runtime-1', text: 'Hi Flo' })
  })
})
