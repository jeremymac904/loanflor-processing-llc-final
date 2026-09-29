import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { afterEach, describe, expect, it, vi } from 'vitest'

import { createFloSmsService, FLO_SMS_NUMBER, normalizeE164 } from './flo-sms'

const credentials = {
  accountSid: `AC${'a'.repeat(32)}`,
  apiKeySid: `SK${'b'.repeat(32)}`,
  apiKeySecret: 'synthetic-api-key-secret'
}

const to = '+19045550123'
const messageSid = `SM${'c'.repeat(32)}`
const files: string[] = []

function createService(fetch: typeof globalThis.fetch, now = new Date('2026-09-29T16:00:00.000Z'), log = vi.fn()) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'flo-sms-test-'))
  const filePath = path.join(dir, 'flo-communications.json')
  files.push(dir)

  return {
    service: createFloSmsService({ filePath, credentials: () => credentials, fetch, now: () => new Date(now), log }),
    filePath,
    log
  }
}

afterEach(() => {
  for (const directory of files.splice(0)) {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})

function jsonResponse(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } })
}

describe('Flo local Twilio messaging', () => {
  it('normalizes complete US numbers and rejects partial or invalid values', () => {
    expect(normalizeE164('(904) 555-0123')).toBe(to)
    expect(normalizeE164('1 904 555 0123')).toBe(to)
    expect(normalizeE164('555-0123')).toBeNull()
    expect(normalizeE164('+0 222 333 4444')).toBeNull()
  })

  it('sends only to the saved contact after a fresh approval and stores Twilio’s real status', async () => {
    let requestUrl = ''
    let requestInit: RequestInit | undefined

    const mockFetch = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      requestUrl = String(input)
      requestInit = init

      return jsonResponse({ sid: messageSid, status: 'accepted', date_created: '2026-09-29T15:59:00Z' })
    }) as unknown as typeof fetch

    const { service, filePath, log } = createService(mockFetch)
    const [contact] = service.setContacts('loan_johnson_test', [
      { displayName: 'Johnson Test', role: 'Borrower', mobile: to }
    ])

    const sent = await service.sendMessage({
      workspaceId: 'loan_johnson_test',
      contactId: contact.contactId,
      to,
      body: 'Please send the updated bank statement.',
      approvedBy: 'Ashley',
      approvedAt: '2026-09-29T15:59:30Z'
    })

    expect(new URL(requestUrl).pathname).toContain('/Messages.json')
    expect(new URLSearchParams(String(requestInit?.body))).toEqual(
      new URLSearchParams({
        To: to,
        From: FLO_SMS_NUMBER,
        Body: 'Please send the updated bank statement.'
      })
    )
    expect(sent.message).toMatchObject({
      sid: messageSid,
      status: 'accepted',
      workspaceId: 'loan_johnson_test',
      contactId: contact.contactId,
      approvedBy: 'Ashley'
    })
    expect(fs.readFileSync(filePath, 'utf8')).not.toContain(credentials.apiKeySecret)
    expect(JSON.stringify(log.mock.calls)).not.toContain('Please send the updated bank statement.')
    await expect(
      service.sendMessage({
        workspaceId: 'loan_johnson_test',
        contactId: contact.contactId,
        to,
        body: 'Another message',
        approvedBy: 'Ashley',
        approvedAt: '2026-09-29T15:00:00Z'
      })
    ).rejects.toThrow('approval is missing or has expired')
    await expect(
      service.sendMessage({
        workspaceId: 'loan_johnson_test',
        contactId: contact.contactId,
        to: '+19045550124',
        body: 'Wrong contact',
        approvedBy: 'Ashley',
        approvedAt: '2026-09-29T15:59:30Z'
      })
    ).rejects.toThrow('not in the current Customer File')
  })

  it('deduplicates history, marks ambiguous STOP messages for review, opts every matching contact out, and refreshes delivery', async () => {
    const incomingSid = `SM${'d'.repeat(32)}`
    const sentSid = `SM${'e'.repeat(32)}`
    const calls: string[] = []

    const mockFetch = vi.fn(async (input: string | URL | Request) => {
      const url = new URL(String(input))
      calls.push(url.pathname)

      if (url.pathname.endsWith(`/${sentSid}.json`)) {
        return jsonResponse({ sid: sentSid, status: 'delivered', date_updated: '2026-09-29T15:30:00Z' })
      }

      if (url.pathname.endsWith('/Messages.json') && url.searchParams.has('To')) {
        return jsonResponse({
          messages: [
            {
              sid: incomingSid,
              from: to,
              to: FLO_SMS_NUMBER,
              body: 'STOP',
              status: 'received',
              date_created: '2026-09-29T15:20:00Z',
              num_media: '0'
            }
          ]
        })
      }

      if (url.pathname.endsWith('/Messages.json') && url.searchParams.has('From')) {
        return jsonResponse({
          messages: [
            {
              sid: sentSid,
              from: FLO_SMS_NUMBER,
              to,
              body: 'Synthetic pending message',
              status: 'sent',
              date_created: '2026-09-29T15:10:00Z',
              num_media: '0'
            }
          ]
        })
      }

      return jsonResponse({})
    }) as unknown as typeof fetch

    const { service, filePath } = createService(mockFetch)
    const [one] = service.setContacts('loan_johnson_test', [
      { displayName: 'Johnson Test', role: 'Borrower', mobile: to }
    ])
    const [two] = service.setContacts('loan_smith_test', [{ displayName: 'Smith Test', role: 'Borrower', mobile: to }])

    await expect(service.sync()).resolves.toMatchObject({ ok: true })
    await expect(service.sync()).resolves.toMatchObject({ ok: true })

    const review = service.getUnmatchedMessages()
    expect(review).toHaveLength(1)
    expect(review[0]).toMatchObject({
      sid: incomingSid,
      matchStatus: 'needs_review',
      candidates: [
        { workspaceId: 'loan_johnson_test', contactId: one.contactId },
        { workspaceId: 'loan_smith_test', contactId: two.contactId }
      ]
    })
    expect(service.getMessages('loan_johnson_test')).toEqual([])
    expect(service.getStatus().lastSyncAt).toBe('2026-09-29T16:00:00.000Z')
    const saved = JSON.parse(fs.readFileSync(filePath, 'utf8'))
    expect(saved.messages.filter((row: { sid: string }) => row.sid === incomingSid)).toHaveLength(1)
    expect(saved.contacts.loan_johnson_test[0].smsConsent).toBe('opted_out')
    expect(saved.contacts.loan_smith_test[0].smsConsent).toBe('opted_out')
    expect(saved.messages.find((row: { sid: string }) => row.sid === sentSid).status).toBe('delivered')
    await expect(
      service.sendMessage({
        workspaceId: 'loan_johnson_test',
        contactId: one.contactId,
        to,
        body: 'blocked',
        approvedBy: 'Ashley',
        approvedAt: '2026-09-29T15:59:30Z'
      })
    ).rejects.toThrow('SMS Opted Out')
    expect(calls.some(url => url.endsWith(`/${sentSid}.json`))).toBe(true)
    expect(service.getUnmatchedMessages().map(row => row.sid)).toEqual([incomingSid])
  })
})
