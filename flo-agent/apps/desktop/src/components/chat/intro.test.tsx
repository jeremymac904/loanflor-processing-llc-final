import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Intro } from './intro'

describe('Flo empty chat', () => {
  it('uses the product identity even when the display name is Flo Agent', () => {
    render(<Intro />)
    expect(screen.getByRole('heading', { name: 'Good morning, Ash ✨' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Open Pipeline' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Ask Flo' })).toBeTruthy()
    expect(screen.queryByText(/Search the repo, edit files/)).toBeNull()
  })
})
