import { useMemo, useState } from 'react'
import { host } from '@hermes/plugin-sdk'

import { requestComposerFocus, requestComposerInsert, requestComposerSubmit } from '@/app/chat/composer/focus'
import { capitalize, normalize } from '@/lib/text'
import floBadge from '@/plugins/flo/flo-badge.png'
import { useTeamState } from '@/plugins/flo/state'

import { FLO_BRAND } from '../../../flo/brand'
import { notify, notifyError } from '@/store/notifications'
import { requestPendingWorkspaceBinding, runFloLocalIntake } from '@/plugins/flo/actions-api'

import introCopyJsonl from './intro-copy.jsonl?raw'

type IntroCopy = {
  headline: string
  body: string
}

type IntroCopyRecord = IntroCopy & {
  personality: string
}

export type IntroProps = {
  personality?: string
  seed?: number
}

const NEUTRAL_PERSONALITIES = new Set(['', 'default', 'none', 'neutral'])

const FALLBACK_COPY: IntroCopy[] = [
  {
    headline: 'What are we moving today?',
    body: "Send a bug, branch, plan, or rough idea. I'll inspect the repo and turn it into the next concrete step."
  },
  {
    headline: "What's on your mind?",
    body: "Bring the code, question, or stuck part. I'll read the room before making changes."
  },
  {
    headline: 'What should Hermes look at?',
    body: "Send the task, failing path, or half-formed plan. I'll help turn it into action."
  },
  {
    headline: 'Where should we start?',
    body: "Bring the problem, goal, or file. I'll inspect first and keep the next step concrete."
  },
  {
    headline: 'What needs attention?',
    body: "Send the context you have. I'll help sort it into a plan or a fix."
  }
]

function normalizeKey(value?: string): string {
  return normalize(value)
}

function titleize(value: string): string {
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map(capitalize)
    .join(' ')
}

function isIntroCopyRecord(value: unknown): value is IntroCopyRecord {
  if (!value || typeof value !== 'object') {
    return false
  }

  const record = value as Record<string, unknown>

  return (
    typeof record.personality === 'string' &&
    typeof record.headline === 'string' &&
    typeof record.body === 'string' &&
    Boolean(record.personality.trim()) &&
    Boolean(record.headline.trim()) &&
    Boolean(record.body.trim())
  )
}

function parseIntroCopy(raw: string): Record<string, IntroCopy[]> {
  const byPersonality: Record<string, IntroCopy[]> = {}

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim()

    if (!trimmed) {
      continue
    }

    try {
      const parsed: unknown = JSON.parse(trimmed)

      if (!isIntroCopyRecord(parsed)) {
        continue
      }

      const key = normalizeKey(parsed.personality)
      byPersonality[key] ??= []
      byPersonality[key].push({
        headline: parsed.headline.trim(),
        body: parsed.body.trim()
      })
    } catch {
      // Bad generated copy should not break the whole desktop app.
    }
  }

  return byPersonality
}

const INTRO_COPY_BY_PERSONALITY = parseIntroCopy(introCopyJsonl)

function neutralCopy(): IntroCopy[] {
  return INTRO_COPY_BY_PERSONALITY.none || INTRO_COPY_BY_PERSONALITY.default || FALLBACK_COPY
}

function fallbackCopyForPersonality(personalityKey: string): IntroCopy[] {
  if (NEUTRAL_PERSONALITIES.has(personalityKey)) {
    return neutralCopy()
  }

  const label = titleize(personalityKey)

  return [
    {
      headline: `${label} mode is on. What should we work on?`,
      body: "Send the task, file, or rough idea. I'll use your configured voice and keep the work grounded in this repo."
    },
    {
      headline: `What does ${label} Hermes need to see?`,
      body: "Bring the context or the stuck part. I'll adapt to your configured personality."
    },
    {
      headline: `${label} mode is ready.`,
      body: "Send the problem, file, or idea. I'll follow the personality you've configured."
    },
    {
      headline: `What should ${label} Hermes tackle?`,
      body: "Drop the task here. I'll keep the work grounded in the repo."
    },
    {
      headline: 'Where should we begin?',
      body: `Give me the context and I'll answer in ${label} mode.`
    }
  ]
}

function pickCopy(copies: IntroCopy[], seed = 0): IntroCopy {
  return copies[Math.abs(seed) % copies.length] || FALLBACK_COPY[0]
}

function resolveCopy(personality?: string, seed?: number): IntroCopy {
  const personalityKey = normalizeKey(personality)

  const copies = NEUTRAL_PERSONALITIES.has(personalityKey)
    ? INTRO_COPY_BY_PERSONALITY[personalityKey] || neutralCopy()
    : INTRO_COPY_BY_PERSONALITY[personalityKey] || fallbackCopyForPersonality(personalityKey)

  return pickCopy(copies, seed)
}

export function Intro({ personality, seed }: IntroProps) {
  const [mountSeed] = useState(() => Math.floor(Math.random() * 100000))
  const [intaking, setIntaking] = useState(false)
  const copy = resolveCopy(personality, mountSeed + (seed ?? 0))
  const flo = FLO_BRAND.productName.toLowerCase() === 'flo'
  const { state } = useTeamState()
  const currentFile = useMemo(
    () => [...(state?.workspaces ?? [])].sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))[0] ?? null,
    [state?.workspaces]
  )

  const reviewFolder = async () => {
    const desktop = window.hermesDesktop
    if (!desktop?.selectPaths) {
      notify({ kind: 'error', title: 'Folder picker unavailable', message: 'Flo could not open the Windows folder picker.' })
      return
    }
    setIntaking(true)
    try {
      const selected = await desktop.selectPaths({ directories: true, multiple: false, title: 'Choose a Client Folder' })
      const folder = selected[0]
      if (!folder) return
      const result = await runFloLocalIntake(folder)
      requestPendingWorkspaceBinding(result.workspace_id)
      const prompt = 'A local client-folder intake has completed. Please acknowledge briefly without repeating or requesting any borrower information.'
      if (!requestComposerSubmit(prompt, { target: 'main' })) {
        requestComposerInsert(prompt, { target: 'main' })
        requestComposerFocus('main')
      }
      notify({ kind: 'success', title: 'Client folder reviewed', message: `Customer File created or updated; ${result.document_count} new document${result.document_count === 1 ? '' : 's'} imported and Malcolm’s local prep is saved.` })
    } catch (error) {
      notifyError(error, 'Client folder intake failed')
    } finally {
      setIntaking(false)
    }
  }

  return (
    <div
      className="flex w-full min-w-0 flex-col items-center justify-center px-4 py-6 text-center text-muted-foreground sm:px-6 lg:px-8"
      data-slot="aui_intro"
    >
      {flo ? (
        <div className="flo-hero flex max-w-3xl flex-col items-center">
          <div className="flo-hero-portrait">
            <img alt="Flo" draggable={false} src={floBadge} />
          </div>
          <h1 className="flo-display m-0 text-4xl leading-tight text-foreground sm:text-5xl">Good morning, Ash ✨</h1>
          <p className="m-0 text-lg text-(--ui-text-secondary)">What are we getting done today?</p>
          <div className="flo-hero-actions">
            <button
              disabled={!currentFile}
              onClick={() => currentFile && host.navigate(`/pipeline?file=${encodeURIComponent(currentFile.workspace_id)}`)}
              type="button"
            >
              <span aria-hidden>↗</span>
              Continue Last File
            </button>
            <button disabled={intaking} onClick={() => void reviewFolder()} type="button">
              <span aria-hidden>{intaking ? '…' : '⌁'}</span>
              {intaking ? 'Reviewing folder…' : 'Review New Client Folder'}
            </button>
            <button
              onClick={() => requestComposerFocus('main')}
              type="button"
            >
              <span aria-hidden>✦</span>
              Ask Flo
            </button>
          </div>
        </div>
      ) : (
        <p className="m-0 text-center leading-normal tracking-tight">{copy.body}</p>
      )}
    </div>
  )
}
