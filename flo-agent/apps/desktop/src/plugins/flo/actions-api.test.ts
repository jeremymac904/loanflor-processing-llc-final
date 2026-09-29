import { beforeEach, describe, expect, it, vi } from 'vitest'

import { bindFloActions, runFloAction } from './actions-api'

describe('Flo deterministic actions', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('posts an explicit action through the bound plugin API', async () => {
    const rest = vi.fn().mockResolvedValue({ action: 'prep', message: 'Malcolm completed.' })
    const dispose = bindFloActions(rest)

    await expect(runFloAction('prep', { workspace_id: 'johnson-test' })).resolves.toEqual({
      action: 'prep',
      message: 'Malcolm completed.'
    })
    expect(rest).toHaveBeenCalledWith('/actions/prep', {
      method: 'POST',
      body: { workspace_id: 'johnson-test' }
    })

    dispose()
    await expect(runFloAction('prep', {})).rejects.toThrow('Flo action API is not ready')
  })
})
