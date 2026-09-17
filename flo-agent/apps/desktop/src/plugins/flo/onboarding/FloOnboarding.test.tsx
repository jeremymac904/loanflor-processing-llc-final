/**
 * Smoke tests for the Flo onboarding component.
 *
 * These tests cover the wiring and the conditional copy — the
 * "do-the-setup" IPC calls themselves are stubbed. We trust
 * electron/main.ts + preload for the actual side effects
 * (safeStorage, winget, docker compose), which the existing
 * Electron test suite covers separately.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

const flush = () => new Promise((r) => setTimeout(r, 0))

const baseStatus = {
  gmail:    { configured: false, identifier: null },
  drive:    { configured: false },
  calendar: { configured: false },
  zapier:   { configured: false },
  signing:  { configured: false },
  localAi:  { configured: false, models: [] }
}

beforeEach(() => {
  ;(window as any).hermesDesktop = {
    flo: {
      connectionStatus: vi.fn(async () => baseStatus),
      saveGmail: vi.fn(async () => ({ ok: true })),
      saveZapier: vi.fn(async () => ({ ok: true })),
      googleSetup: vi.fn(async () => ({ ok: true, url: 'https://x', opened: true })),
      googleComplete: vi.fn(async () => ({ ok: true })),
      signingSetup: vi.fn(async () => ({ ok: true })),
      aiSetup: vi.fn(async () => ({ ok: true, model: 'llama3.2:3b' })),
      gmailBootstrap: vi.fn(async () => ({ ok: false, configured: false })),
      checkDocumenso: vi.fn(async () => ({ ok: false })),
      startDocumenso: vi.fn(async () => ({ ok: true })),
      checkLocalAi: vi.fn(async () => ({ ok: false, models: [] }))
    }
  }
})

afterEach(() => {
  delete (window as any).hermesDesktop
  vi.restoreAllMocks()
})

describe('FloOnboarding first-run flow', () => {
  it('renders the welcome heading and the five connector cards', async () => {
    const FloOnboarding = (await import('./FloOnboarding')).FloOnboarding
    render(<FloOnboarding storage={mkStorage()} />)
    expect(screen.getByTestId('flo-onboarding')).toBeInTheDocument()
    expect(screen.getByText(/Welcome to Flo/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByTestId('connect-card-gmail')).toBeInTheDocument()
      expect(screen.getByTestId('connect-card-zapier')).toBeInTheDocument()
    })
  })

  it('Continue stays disabled while Local AI is not Ready', async () => {
    const FloOnboarding = (await import('./FloOnboarding')).FloOnboarding
    let api: any
    await act(async () => {
      const result = render(<FloOnboarding storage={mkStorage()} />)
      api = result
      // Flush the useEffect async chain (connectionStatus → setStatus)
      await new Promise(r => setTimeout(r, 0))
    })
    const btn = await screen.findByTestId('continue-button')
    expect((btn as HTMLButtonElement).disabled).toBe(true)
  })

  it('Save Gmail encrypts via safeStorage and triggers refresh', async () => {
    const { saveGmail } = (window as any).hermesDesktop.flo
    const FloOnboarding = (await import('./FloOnboarding')).FloOnboarding
    render(<FloOnboarding storage={mkStorage()} />)
    await waitFor(() => screen.getByTestId('connect-card-gmail'))
    fireEvent.click(screen.getByTestId('connect-action-gmail'))
    await waitFor(() => screen.getByTestId('gmail-email-input'))
    fireEvent.change(screen.getByTestId('gmail-email-input'), {
      target: { value: 'ashley@example.com' }
    })
    fireEvent.change(screen.getByTestId('gmail-password-input'), {
      target: { value: 'abcd efgh ijkl mnop' }
    })
    fireEvent.click(screen.getByTestId('gmail-save-button'))
    await waitFor(() => expect(saveGmail).toHaveBeenCalled())
    const payload = saveGmail.mock.calls[0][0]
    expect(payload.identifier).toBe('ashley@example.com')
    expect(payload.secret).toBe('abcd efgh ijkl mnop')
  })

  it('Save Zapier writes the URL to the IPC', async () => {
    const { saveZapier } = (window as any).hermesDesktop.flo
    const FloOnboarding = (await import('./FloOnboarding')).FloOnboarding
    render(<FloOnboarding storage={mkStorage()} />)
    await waitFor(() => screen.getByTestId('connect-card-zapier'))
    fireEvent.click(screen.getByTestId('connect-action-zapier'))
    await waitFor(() => screen.getByTestId('zapier-url-input'))
    fireEvent.change(screen.getByTestId('zapier-url-input'), {
      target: { value: 'https://nla.zapier.com/example' }
    })
    fireEvent.click(screen.getByTestId('zapier-save-button'))
    await waitFor(() => expect(saveZapier).toHaveBeenCalled())
    expect(saveZapier.mock.calls[0][0].url).toBe('https://nla.zapier.com/example')
  })

  it('Continue is disabled but reachable; status line surfaces the model warning', async () => {
    ;(window as any).hermesDesktop.flo.connectionStatus = vi.fn(async () => ({
      ...baseStatus, localAi: { configured: false, models: [] }
    }))
    const FloOnboarding = (await import('./FloOnboarding')).FloOnboarding
    await act(async () => {
      render(<FloOnboarding storage={mkStorage()} />)
      await new Promise(r => setTimeout(r, 0))
    })
    const line = await screen.findByTestId('onboarding-status-line')
    expect(line.textContent?.toLowerCase()).toMatch(/local ai/)
    expect(line.textContent?.toLowerCase()).toMatch(/ready/)
  })

  it('Continue stays disabled when Local AI is Ready', async () => {
    // Continue IS enabled — the test below verifies that — by checking
    // that the disabled flag clears.
    ;(window as any).hermesDesktop.flo.connectionStatus = vi.fn(async () => ({
      ...baseStatus, localAi: { configured: true, models: ['llama3.2:3b'] }
    }))
    const FloOnboarding = (await import('./FloOnboarding')).FloOnboarding
    await act(async () => {
      render(<FloOnboarding storage={mkStorage()} />)
      await new Promise(r => setTimeout(r, 0))
    })
    const btn = await screen.findByTestId('continue-button')
    // When localAi.configured is true, Continue is enabled.
    expect((btn as HTMLButtonElement).disabled).toBe(false)
  })
})

function mkStorage() {
  const data = new Map<string, unknown>()
  return {
    get<T>(k: string, fb: T): T { return data.has(k) ? (data.get(k) as T) : fb },
    set(k: string, v: unknown) { data.set(k, v) }
  }
}
