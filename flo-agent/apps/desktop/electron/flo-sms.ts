import { randomUUID } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

export const FLO_SMS_NUMBER = '+19046829414'
export const FLO_SMS_POLL_INTERVAL_MS = 90_000
const MAX_CATCHUP_DAYS = 7
const MAX_PAGES_PER_SYNC = 8
const PAGE_SIZE = 100
const OVERLAP_MS = 2 * 60_000
const E164 = /^\+[1-9]\d{7,14}$/

export type SmsRole =
  'Borrower' | 'Co-Borrower' | 'Loan Officer' | 'Processor' | 'Title Contact' | 'Insurance Contact' | 'Other' | 'Ashley'
export type SmsConsent = 'unknown' | 'opted_in' | 'opted_out'
export type SmsDelivery = 'queued' | 'sending' | 'sent' | 'delivered' | 'failed' | 'undelivered' | 'received'

export interface SmsContact {
  contactId: string
  displayName: string
  role: SmsRole
  mobile: string
  communicationStatus: 'available' | 'needs_review'
  smsConsent: SmsConsent
}

export interface SmsMedia {
  sid: string
  contentType: string | null
}

export interface SmsMessage {
  sid: string
  workspaceId: string | null
  contactId: string | null
  to: string
  from: string
  direction: 'inbound' | 'outbound'
  timestamp: string
  body: string
  status: SmsDelivery | string
  source: 'Twilio'
  approvedBy?: string
  approvedAt?: string
  matchStatus?: 'matched' | 'unmatched' | 'needs_review'
  candidates?: Array<{ workspaceId: string; contactId: string; displayName: string }>
  media?: SmsMedia[]
}

export interface SmsStore {
  version: 1
  cursor: string | null
  inboundNextPage: string | null
  outboundNextPage: string | null
  contacts: Record<string, SmsContact[]>
  messages: SmsMessage[]
  ashleyMobile: string | null
  lastSyncAt: string | null
  lastSyncError: string | null
  connection: 'not_connected' | 'connected' | 'needs_attention'
  connectionCheckedAt: string | null
}

export interface SmsCredentials {
  accountSid: string
  apiKeySid: string
  apiKeySecret: string
  fromNumber?: string
}
type Fetcher = (input: string | URL | Request, init?: RequestInit) => Promise<Response>

export function normalizeE164(value: string): string | null {
  const compact = String(value ?? '')
    .trim()
    .replace(/[\s().-]/g, '')

  if (/^\d{10}$/.test(compact)) {
    return `+1${compact}`
  }

  if (/^1\d{10}$/.test(compact)) {
    return `+${compact}`
  }

  return E164.test(compact) ? compact : null
}

function emptyStore(): SmsStore {
  return {
    version: 1,
    cursor: null,
    inboundNextPage: null,
    outboundNextPage: null,
    contacts: {},
    messages: [],
    ashleyMobile: null,
    lastSyncAt: null,
    lastSyncError: null,
    connection: 'not_connected',
    connectionCheckedAt: null
  }
}

function readStore(filePath: string): SmsStore {
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8')) as Partial<SmsStore>

    return {
      ...emptyStore(),
      ...parsed,
      contacts: parsed.contacts && typeof parsed.contacts === 'object' ? parsed.contacts : {},
      messages: Array.isArray(parsed.messages) ? parsed.messages : []
    }
  } catch {
    return emptyStore()
  }
}

function safeStore(filePath: string, store: SmsStore): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  const tmp = `${filePath}.tmp`
  fs.writeFileSync(tmp, JSON.stringify(store), { encoding: 'utf8', mode: 0o600 })
  fs.renameSync(tmp, filePath)
}

function normalizeStatus(value: unknown, direction: 'inbound' | 'outbound'): string {
  if (direction === 'inbound') {
    return 'received'
  }

  return typeof value === 'string' && value ? value.toLowerCase() : 'queued'
}

function twilioDate(value: unknown): string {
  if (typeof value !== 'string') {
    return new Date(0).toISOString()
  }
  const parsed = new Date(value)

  return Number.isNaN(parsed.getTime()) ? new Date(0).toISOString() : parsed.toISOString()
}

function deliveryIsPending(status: string): boolean {
  return ['accepted', 'queued', 'sending', 'sent'].includes(status.toLowerCase())
}

function isOptOut(body: string): 'stop' | 'start' | 'help' | null {
  const command = body
    .trim()
    .toUpperCase()
    .replace(/[.!?]+$/g, '')

  if (/^(STOP|STOPALL|UNSUBSCRIBE|CANCEL|END|QUIT)$/.test(command)) {
    return 'stop'
  }

  if (/^(START|UNSTOP|SUBSCRIBE)$/.test(command)) {
    return 'start'
  }

  if (/^HELP$/.test(command)) {
    return 'help'
  }

  return null
}

export function createFloSmsService(options: {
  filePath: string
  credentials: () => SmsCredentials | null
  fetch?: Fetcher
  now?: () => Date
  log?: (event: string, metadata: Record<string, unknown>) => void
}) {
  const fetcher = options.fetch ?? fetch
  const now = options.now ?? (() => new Date())
  const log = options.log ?? (() => undefined)
  let syncInFlight = false

  const store = () => readStore(options.filePath)
  const save = (data: SmsStore) => safeStore(options.filePath, data)

  const credentials = (): SmsCredentials => {
    const config = options.credentials()

    if (!config) {
      throw new Error('Twilio is not connected. Add the Flo Twilio credentials in Communications settings.')
    }

    if (
      !/^AC[\da-f]{32}$/i.test(config.accountSid) ||
      !/^SK[\da-f]{32}$/i.test(config.apiKeySid) ||
      !config.apiKeySecret
    ) {
      throw new Error('Twilio credentials need attention. Check the Account SID, API Key SID, and API Key Secret.')
    }

    return { ...config, fromNumber: FLO_SMS_NUMBER }
  }

  async function api<T>(config: SmsCredentials, url: string, init: RequestInit = {}): Promise<T> {
    const target = new URL(url, 'https://api.twilio.com')

    if (target.protocol !== 'https:' || target.hostname !== 'api.twilio.com') {
      throw new Error('Twilio returned an unexpected API address.')
    }
    const auth = Buffer.from(`${config.apiKeySid}:${config.apiKeySecret}`, 'utf8').toString('base64')

    const response = await fetcher(target, {
      ...init,
      headers: {
        Accept: 'application/json',
        Authorization: `Basic ${auth}`,
        ...(init.body ? { 'Content-Type': 'application/x-www-form-urlencoded' } : {}),
        ...init.headers
      },
      signal: AbortSignal.timeout(15_000)
    })

    const data = (await response.json().catch(() => ({ media_list: [] as Array<Record<string, unknown>> }))) as Record<string, unknown>

    if (!response.ok) {
      const code = typeof data.code === 'number' || typeof data.code === 'string' ? String(data.code) : 'unknown'
      const error = new Error(`Twilio request failed (${response.status}, code ${code}).`)
      Object.assign(error, { httpStatus: response.status, twilioCode: code })
      log('twilio.request_failed', { status: response.status, code })
      throw error
    }

    return data as T
  }

  function allContacts(data = store()): Array<{ workspaceId: string; contact: SmsContact }> {
    return Object.entries(data.contacts).flatMap(([workspaceId, contacts]) =>
      contacts.map(contact => ({ workspaceId, contact }))
    )
  }

  async function fetchPage(
    config: SmsCredentials,
    url: string
  ): Promise<{ messages: Array<Record<string, unknown>>; next: string | null }> {
    const response = await api<{ messages?: Array<Record<string, unknown>>; next_page_uri?: string | null }>(
      config,
      url
    )

    return { messages: response.messages ?? [], next: response.next_page_uri ?? null }
  }

  async function collectDirection(data: SmsStore, config: SmsCredentials, direction: 'inbound' | 'outbound') {
    const nextKey = direction === 'inbound' ? 'inboundNextPage' : 'outboundNextPage'
    let nextPage = data[nextKey]

    if (!nextPage) {
      const savedCursor = data.cursor ? Date.parse(data.cursor) : 0
      const boundedStart = now().getTime() - MAX_CATCHUP_DAYS * 24 * 60 * 60_000
      const since = new Date(Math.max(boundedStart, (savedCursor || boundedStart) - OVERLAP_MS))
        .toISOString()
        .slice(0, 10)
      const fromOrTo = direction === 'inbound' ? 'To' : 'From'
      const url = new URL(`/2010-04-01/Accounts/${config.accountSid}/Messages.json`, 'https://api.twilio.com')
      url.searchParams.set(fromOrTo, FLO_SMS_NUMBER)
      url.searchParams.set('DateSent>=', since)
      url.searchParams.set('PageSize', String(PAGE_SIZE))
      nextPage = url.toString()
    }

    let pages = 0
    let hadMore = false

    while (nextPage && pages < MAX_PAGES_PER_SYNC) {
      const page = await fetchPage(config, nextPage)

      for (const record of page.messages) {
        await importMessage(data, config, record)
      }
      nextPage = page.next
      pages += 1

      if (!nextPage) {
        break
      }
      hadMore = true
    }

    data[nextKey] = nextPage

    return { complete: !nextPage, pages, hadMore: Boolean(nextPage) || hadMore }
  }

  async function importMessage(data: SmsStore, config: SmsCredentials, item: Record<string, unknown>) {
    const sid = typeof item.sid === 'string' ? item.sid : ''

    if (!/^SM[0-9a-f]{32}$/i.test(sid)) {
      return
    }
    const existing = data.messages.find(message => message.sid === sid)
    const from = normalizeE164(String(item.from ?? '')) ?? String(item.from ?? '')
    const to = normalizeE164(String(item.to ?? '')) ?? String(item.to ?? '')
    const direction: 'inbound' | 'outbound' = to === FLO_SMS_NUMBER ? 'inbound' : 'outbound'
    const status = normalizeStatus(item.status, direction)

    if (existing) {
      existing.status = status

      return
    }

    let media: SmsMedia[] = []
    const mediaCount = Math.min(10, Number(item.num_media) || 0)

    if (mediaCount > 0) {
      const result = await api<{ media_list?: Array<Record<string, unknown>> }>(
        config,
        `/2010-04-01/Accounts/${config.accountSid}/Messages/${sid}/Media.json?PageSize=10`
      ).catch(() => ({ media_list: [] as Array<Record<string, unknown>> }))

      media = (result.media_list ?? [])
        .slice(0, mediaCount)
        .map(entry => ({
          sid: String(entry.sid ?? ''),
          contentType: typeof entry.content_type === 'string' ? entry.content_type : null
        }))
        .filter(entry => entry.sid)
    }

    const sender = direction === 'inbound' ? from : to

    const matched = direction === 'inbound' ? allContacts(data).filter(({ contact }) => contact.mobile === sender) : []

    let workspaceId: string | null = null
    let contactId: string | null = null
    let matchStatus: SmsMessage['matchStatus'] = undefined
    let candidates: SmsMessage['candidates']

    if (direction === 'inbound') {
      if (matched.length === 1) {
        workspaceId = matched[0].workspaceId
        contactId = matched[0].contact.contactId
        matchStatus = 'matched'
      } else if (matched.length > 1) {
        matchStatus = 'needs_review'
        candidates = matched.map(({ workspaceId: wid, contact }) => ({
          workspaceId: wid,
          contactId: contact.contactId,
          displayName: contact.displayName
        }))
      } else {
        matchStatus = 'unmatched'
      }
    }

    const body = typeof item.body === 'string' ? item.body : ''

    const message: SmsMessage = {
      sid,
      workspaceId,
      contactId,
      to,
      from,
      direction,
      timestamp: twilioDate(item.date_created),
      body,
      status,
      source: 'Twilio',
      ...(matchStatus ? { matchStatus } : {}),
      ...(candidates ? { candidates } : {}),
      ...(media.length ? { media } : mediaCount ? { media: [{ sid: 'metadata-only', contentType: null }] } : {})
    }

    data.messages.push(message)

    if (direction === 'inbound') {
      const command = isOptOut(body)

      if (command === 'stop' || command === 'start') {
        const consent: SmsConsent = command === 'stop' ? 'opted_out' : 'opted_in'

        for (const { contact } of allContacts(data)) {
          if (contact.mobile === from) {
            contact.smsConsent = consent
          }
        }
      }
    }

    log('twilio.message_imported', {
      message_sid: sid,
      customer_file_id: workspaceId,
      status,
      direction,
      match_status: matchStatus ?? 'outbound'
    })
  }

  async function refreshPending(data: SmsStore, config: SmsCredentials) {
    const pending = data.messages
      .filter(message => message.direction === 'outbound' && deliveryIsPending(message.status))
      .slice(-100)

    for (const message of pending) {
      try {
        const current = await api<Record<string, unknown>>(
          config,
          `/2010-04-01/Accounts/${config.accountSid}/Messages/${message.sid}.json`
        )

        message.status = normalizeStatus(current.status, 'outbound')
        message.timestamp = twilioDate(current.date_updated ?? current.date_created)
        log('twilio.delivery_updated', {
          message_sid: message.sid,
          status: message.status,
          customer_file_id: message.workspaceId
        })
      } catch {
        // A failed status lookup must not change the last known delivery result.
      }
    }
  }

  return {
    getStatus() {
      const data = store()

      return {
        state: data.connection,
        sendingNumber: FLO_SMS_NUMBER,
        configured: data.connection !== 'not_connected',
        accountSid: options.credentials()?.accountSid ?? null,
        apiKeySid: options.credentials()?.apiKeySid ?? null,
        lastSyncAt: data.lastSyncAt,
        lastSyncError: data.lastSyncError,
        pollIntervalMs: FLO_SMS_POLL_INTERVAL_MS,
        a2pStatus: 'unknown' as const
      }
    },
    markNeedsAttention() {
      const data = store()
      data.connection = 'needs_attention'
      data.connectionCheckedAt = now().toISOString()
      save(data)
    },
    saveAshleyMobile(value: string) {
      const mobile = value.trim() ? normalizeE164(value) : null

      if (value.trim() && !mobile) {
        throw new Error('Enter Ashley’s mobile number in a valid international format.')
      }
      const data = store()
      data.ashleyMobile = mobile
      save(data)

      return { mobile }
    },
    getAshleyMobile() {
      return store().ashleyMobile
    },
    getContacts(workspaceId: string) {
      return store().contacts[workspaceId] ?? []
    },
    getMessages(workspaceId: string) {
      return store()
        .messages.filter(message => message.workspaceId === workspaceId)
        .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
    },
    getUnmatchedMessages() {
      return store()
        .messages.filter(message => message.direction === 'inbound' && message.matchStatus !== 'matched')
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
    },
    setContacts(workspaceId: string, contacts: Array<Partial<SmsContact>>) {
      if (!/^[a-zA-Z0-9_.-]{1,80}$/.test(workspaceId)) {
        throw new Error('Choose a valid Customer File first.')
      }
      const ids = new Set<string>()

      const normalized = contacts.map(contact => {
        const displayName = String(contact.displayName ?? '')
          .trim()
          .slice(0, 120)
        const mobile = normalizeE164(String(contact.mobile ?? ''))

        if (!displayName || !mobile) {
          throw new Error('Every contact needs a name and a valid mobile number.')
        }
        const contactId = String(contact.contactId ?? randomUUID())

        if (ids.has(contactId)) {
          throw new Error('Contact IDs must be unique in this Customer File.')
        }
        ids.add(contactId)
        const previous = store().contacts[workspaceId]?.find(row => row.contactId === contactId)

        return {
          contactId,
          displayName,
          role: (contact.role ?? 'Other') as SmsRole,
          mobile,
          communicationStatus: 'available' as const,
          smsConsent: previous?.mobile === mobile ? previous.smsConsent : ('unknown' as SmsConsent)
        }
      })

      const data = store()
      data.contacts[workspaceId] = normalized
      save(data)

      return normalized
    },
    assignMessage(sid: string, workspaceId: string, contactId: string) {
      const data = store()
      const message = data.messages.find(row => row.sid === sid && row.direction === 'inbound')

      if (!message) {
        throw new Error('That incoming message is no longer available.')
      }
      const contact = (data.contacts[workspaceId] ?? []).find(row => row.contactId === contactId)

      if (!contact || contact.mobile !== (normalizeE164(message.from) ?? message.from)) {
        throw new Error('Choose a contact whose number matches this incoming text.')
      }
      message.workspaceId = workspaceId
      message.contactId = contactId
      message.matchStatus = 'matched'
      delete message.candidates
      save(data)

      return { ok: true }
    },
    async checkCredentials() {
      const config = credentials()
      const url = new URL(
        `/2010-04-01/Accounts/${config.accountSid}/IncomingPhoneNumbers.json`,
        'https://api.twilio.com'
      )
      url.searchParams.set('PhoneNumber', FLO_SMS_NUMBER)
      url.searchParams.set('PageSize', '5')
      const result = await api<{ incoming_phone_numbers?: Array<Record<string, unknown>> }>(config, url.toString())
      const number = (result.incoming_phone_numbers ?? []).find(
        item => normalizeE164(String(item.phone_number ?? '')) === FLO_SMS_NUMBER
      )

      if (!number) {
        throw new Error('Twilio connected, but the Flo sending number was not found in that account.')
      }
      const data = store()
      data.connection = 'connected'
      data.connectionCheckedAt = now().toISOString()
      data.lastSyncError = null
      save(data)
      log('twilio.connection_checked', { state: data.connection, sending_number: FLO_SMS_NUMBER })

      return { ok: true, state: data.connection, sendingNumber: FLO_SMS_NUMBER }
    },
    async sendMessage(input: {
      workspaceId: string
      contactId: string
      to: string
      body: string
      approvedBy: string
      approvedAt: string
    }) {
      const config = credentials()
      const to = normalizeE164(input.to)

      if (!to) {
        throw new Error('This recipient’s mobile number is not valid. Update the contact in this Customer File.')
      }

      if (
        !input.approvedBy?.trim() ||
        !Number.isFinite(Date.parse(input.approvedAt)) ||
        Math.abs(now().getTime() - Date.parse(input.approvedAt)) > 120_000
      ) {
        throw new Error('Ashley’s send approval is missing or has expired. Review the draft and choose Send again.')
      }

      const data = store()
      const contact = (data.contacts[input.workspaceId] ?? []).find(row => row.contactId === input.contactId)

      if (!contact || contact.mobile !== to) {
        throw new Error('That recipient is not in the current Customer File. Select a saved contact.')
      }

      if (allContacts(data).some(({ contact: row }) => row.mobile === to && row.smsConsent === 'opted_out')) {
        throw new Error('Sending is blocked because this number is marked SMS Opted Out.')
      }

      const body = String(input.body ?? '').trim()

      if (!body || body.length > 1600) {
        throw new Error('Enter a message between 1 and 1,600 characters.')
      }
      const url = `/2010-04-01/Accounts/${config.accountSid}/Messages.json`
      const payload = new URLSearchParams({ To: to, From: FLO_SMS_NUMBER, Body: body })
      let sent: Record<string, unknown>

      try {
        sent = await api<Record<string, unknown>>(config, url, { method: 'POST', body: payload.toString() })
      } catch (error) {
        if (String((error as { twilioCode?: string })?.twilioCode ?? '') === '21610') {
          for (const { contact: row } of allContacts(data)) {
            if (row.mobile === to) {
              row.smsConsent = 'opted_out'
            }
          }
          save(data)
          throw new Error(
            'Twilio blocked this message because the recipient opted out. Flo marked this number SMS Opted Out.'
          )
        }

        throw error
      }

      if (typeof sent.sid !== 'string' || !/^SM[\da-f]{32}$/i.test(sent.sid)) {
        throw new Error('Twilio did not return a message record; no Sent status was recorded.')
      }

      const message: SmsMessage = {
        sid: sent.sid,
        workspaceId: input.workspaceId,
        contactId: input.contactId,
        to,
        from: FLO_SMS_NUMBER,
        direction: 'outbound',
        timestamp: twilioDate(sent.date_created),
        body,
        status: normalizeStatus(sent.status, 'outbound'),
        source: 'Twilio',
        approvedBy: input.approvedBy.trim().slice(0, 80),
        approvedAt: new Date(input.approvedAt).toISOString(),
        matchStatus: 'matched'
      }

      data.messages = data.messages.filter(row => row.sid !== message.sid)
      data.messages.push(message)
      save(data)
      log('twilio.message_sent', {
        message_sid: message.sid,
        customer_file_id: message.workspaceId,
        status: message.status,
        approved_by: message.approvedBy,
        approved_at: message.approvedAt
      })

      return { message }
    },
    async sync() {
      if (syncInFlight) {
        return { ok: true, skipped: true }
      }
      const config = options.credentials()

      if (!config) {
        return { ok: true, skipped: true }
      }
      syncInFlight = true
      const data = store()

      try {
        const [incoming, outgoing] = await Promise.all([
          collectDirection(data, config, 'inbound'),
          collectDirection(data, config, 'outbound')
        ])

        await refreshPending(data, config)

        if (incoming.complete && outgoing.complete) {
          data.cursor = now().toISOString()
          data.inboundNextPage = null
          data.outboundNextPage = null
        }

        data.lastSyncAt = now().toISOString()
        data.lastSyncError = null
        save(data)

        return { ok: true, imported: data.messages.length, lastSyncAt: data.lastSyncAt }
      } catch (error) {
        const status = Number((error as { httpStatus?: number })?.httpStatus ?? 0)
        const dataError = store()
        dataError.connection = status === 401 || status === 403 ? 'needs_attention' : dataError.connection
        dataError.connectionCheckedAt =
          status === 401 || status === 403 ? now().toISOString() : dataError.connectionCheckedAt
        dataError.lastSyncAt = data.lastSyncAt
        dataError.lastSyncError = error instanceof Error ? error.message : 'Twilio could not be reached.'
        save(dataError)
        log('twilio.sync_failed', { status, customer_file_id: null })

        return { ok: false, error: dataError.lastSyncError }
      } finally {
        syncInFlight = false
      }
    },
    startPolling() {
      const timer = setInterval(() => {
        void this.sync()
      }, FLO_SMS_POLL_INTERVAL_MS)
      timer.unref?.()
      void this.sync()

      return () => clearInterval(timer)
    }
  }
}
