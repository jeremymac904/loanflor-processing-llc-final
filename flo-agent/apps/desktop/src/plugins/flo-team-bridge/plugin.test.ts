import { beforeEach, describe, expect, it, vi } from 'vitest'

import plugin from './plugin'
import { runFloAction } from '@/plugins/flo/actions-api'

describe('Flo local workflow API bridge', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('binds actions to the backend plugin namespace that owns the routes', async () => {
    expect(plugin.id).toBe('flo-team')
    const rest = vi.fn().mockResolvedValue({ action: 'prep', message: 'Malcolm completed.' })
    let dispose: (() => void) | undefined

    plugin.register({
      rest,
      onDispose: (handler: () => void) => {
        dispose = handler
      }
    } as never)
    await runFloAction('prep', { workspace_id: 'smith-test' })

    expect(rest).toHaveBeenCalledWith('/actions/prep', {
      method: 'POST',
      body: { workspace_id: 'smith-test' }
    })
    dispose?.()
  })
})
