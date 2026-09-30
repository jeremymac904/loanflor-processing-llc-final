import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CUSTOM_REACTIONS, CustomReactionAsset, customReaction } from './custom-reactions'
import { ReactionBadge } from './message-reactions'

describe('Flo and team reactions', () => {
  it('keeps replaceable custom ids stable and locally renderable', () => {
    expect(new Set(CUSTOM_REACTIONS.map(([id]) => id)).size).toBe(CUSTOM_REACTIONS.length)
    expect(customReaction(':ctc-boom:')?.agent).toBe('Flo')
    render(<CustomReactionAsset id=":flo-heart:" />)
    expect(screen.getByRole('img', { name: 'Flo Heart' })).toBeTruthy()
  })

  it('shows two different bot identities on Ashley’s message', () => {
    render(
      <ReactionBadge
        reactions={[
          { author: 'agent', agent_id: 'flo', emoji: '💚', at: 1 },
          { author: 'agent', agent_id: 'malcolm', emoji: ':malcolm-approved:', at: 2 }
        ]}
      />
    )
    expect(screen.getByTitle('Reacted by Flo')).toBeTruthy()
    expect(screen.getByTitle('Reacted by Malcolm')).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Malcolm Approved' })).toBeTruthy()
  })

  it('allows Ashley’s reaction to a bot message', () => {
    render(<ReactionBadge onRetract={() => {}} reactions={[{ author: 'user', emoji: '✨', at: 1 }]} />)
    expect(screen.getByRole('button', { name: 'Remove ✨ reaction' })).toBeTruthy()
  })
})
