/**
 * One door into Flo: mint a session for the Flo profile, open it, submit a
 * prompt. Every Ashley-facing button (Ask Flo, Request From Borrower, Order
 * Title, Why?) goes through here, so Ashley never has to pick a bot — Flo
 * delegates to Malcolm / Sage / Whisper / Chadwick behind the scenes.
 */

import { host } from '@hermes/plugin-sdk'

interface SessionCreateResult {
  session_id?: string
  stored_session_id?: string
}

const TEAM_LEADER = 'flo'

/** Talk to the team leader profile when it is installed; otherwise the active profile. */
export function preferFloProfile(profiles: Array<{ name: string }>, active: null | string | undefined): null | string {
  if (profiles.some(p => p.name === TEAM_LEADER)) {
    return TEAM_LEADER
  }

  return active ?? null
}

export async function startFloChat(title: string, prompt: string, profile: null | string): Promise<void> {
  const created = await host.request<SessionCreateResult>('session.create', {
    ...(profile ? { profile } : {}),
    title,
    hidden: false,
    follow_profile_config: true
  })

  const runtime = created.session_id
  const stored = created.stored_session_id

  if (!runtime || !stored) {
    throw new Error('The backend did not return a session to start in.')
  }

  await host.request('session.title', { session_id: runtime, title }).catch(() => undefined)
  await host.openSession(stored, {
    ...(profile ? { profile } : {}),
    intent: 'in-place',
    awaitHydration: true,
    expectHistory: false
  })
  await host.request('prompt.submit', { session_id: runtime, text: prompt })
}

/** Run a Flo-owned follow-up without moving Ashley away from the loan. */
export async function runFloInBackground(title: string, prompt: string, profile: null | string): Promise<void> {
  const created = await host.request<SessionCreateResult>('session.create', {
    ...(profile ? { profile } : {}),
    title,
    hidden: true,
    follow_profile_config: true
  })

  if (!created.session_id) {
    throw new Error('The backend did not return a session to start in.')
  }

  await host.request('prompt.submit', { session_id: created.session_id, text: prompt })
}

export function reportStartFailure(title: string, error: unknown): void {
  host.notifyError(error, `Could not start "${title}"`)
}
