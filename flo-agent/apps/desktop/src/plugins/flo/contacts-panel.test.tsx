import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { runFloAction } from './actions-api'
import type { FileRecord } from './ashley'
import { ContactsPanel } from './contacts-panel'

vi.mock('./actions-api', () => ({ runFloAction: vi.fn() }))

const ws = { workspace_id: 'loan_contacts_test', display_name: 'River' } as FileRecord

describe('Customer File contacts', () => {
  beforeEach(() => vi.mocked(runFloAction).mockReset())

  it('shows Not Set fields and persists edits to the Customer File contact store', async () => {
    const reload = vi.fn()
    vi.mocked(runFloAction).mockResolvedValueOnce({ action: 'contacts-get', message: '', contacts: [] })
    vi.mocked(runFloAction).mockResolvedValueOnce({
      action: 'contacts-save', message: 'Contacts saved.',
      contacts: [{
        contact_id: 'contact-lo', role: 'loan_officer', name: 'Jordan Lee',
        preferred_communication_method: 'email',
      }],
    })

    render(<ContactsPanel onSaved={reload} ws={ws} />)
    fireEvent.click(screen.getByText(/Contacts ·/))

    expect(await screen.findByLabelText('Borrower name')).toBeTruthy()
    expect(screen.getByLabelText('Borrower mobile')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Loan Officer name'), { target: { value: 'Jordan Lee' } })
    fireEvent.change(screen.getByLabelText('Loan Officer phone'), { target: { value: '+19045550123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Contacts' }))

    await waitFor(() => expect(runFloAction).toHaveBeenLastCalledWith('contacts-save', expect.objectContaining({
      workspace_id: ws.workspace_id,
      contacts: expect.arrayContaining([expect.objectContaining({
        role: 'loan_officer', name: 'Jordan Lee', phone: '+19045550123',
      })]),
    })))
    expect(reload).toHaveBeenCalled()
  })
})
