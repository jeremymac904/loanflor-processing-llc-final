/**
 * Shared team-state loader for the Ashley-facing pages (Today, Pipeline,
 * Approvals) and the Advanced page. Pure SDK consumer: reads the files the
 * backend plugin writes through the existing preview-read IPC.
 */

import { host } from '@hermes/plugin-sdk'
import { useEffect, useState } from 'react'

import {
  type ActivityRow,
  type ApprovalCard,
  type KnowledgeCenterData,
  type KnowledgeSource,
  parseJsonl,
  rosterFromProfiles,
  type TaskRow,
  type TeamMember,
  teamRootFromHome,
  type WorkspaceRow
} from './data'

export interface TeamState {
  root: null | string
  roster: TeamMember[]
  workspaces: WorkspaceRow[]
  tasks: TaskRow[]
  approvals: ApprovalCard[]
  activity: ActivityRow[]
  sources: KnowledgeSource[]
  center: KnowledgeCenterData | null
  profiles: Array<{ name: string; model?: string; provider?: string }>
}

export const EMPTY_STATE: TeamState = {
  root: null,
  roster: [],
  workspaces: [],
  tasks: [],
  approvals: [],
  activity: [],
  sources: [],
  center: null,
  profiles: []
}

async function readJsonDir<T>(dir: string): Promise<T[]> {
  const desktop = window.hermesDesktop

  if (!desktop?.readDir || !desktop.readFileText) {
    return []
  }

  const listing = await desktop.readDir(dir).catch(() => null)
  const files = (listing?.entries ?? []).filter(e => e.name.endsWith('.json'))
  const out: T[] = []

  for (const file of files) {
    const text = await desktop.readFileText(file.path).catch(() => null)

    if (!text?.text) {
      continue
    }

    try {
      out.push(JSON.parse(text.text) as T)
    } catch {
      // partial write; skip
    }
  }

  return out
}

async function readJsonl<T>(dir: string, limitFiles = 3): Promise<T[]> {
  const desktop = window.hermesDesktop

  if (!desktop?.readDir || !desktop.readFileText) {
    return []
  }

  const listing = await desktop.readDir(dir).catch(() => null)

  const files = (listing?.entries ?? [])
    .filter(e => e.name.endsWith('.jsonl'))
    .sort((a, b) => b.name.localeCompare(a.name))
    .slice(0, limitFiles)

  const out: T[] = []

  for (const file of files) {
    const text = await desktop.readFileText(file.path).catch(() => null)

    if (text?.text) {
      out.push(...parseJsonl<T>(text.text))
    }
  }

  return out
}

export async function loadTeamState(): Promise<TeamState> {
  const status = await host.status().catch(() => null)
  const home = (status as { hermes_home?: string } | null)?.hermes_home

  const rows = await host
    .request<{ profiles?: Array<{ name: string; model?: string; provider?: string }> }>('profiles.list', {
      include_sessions: true
    })
    .catch(() => ({ profiles: [] }))

  const profiles = rows.profiles ?? []
  const roster = rosterFromProfiles(profiles as Parameters<typeof rosterFromProfiles>[0])

  if (!home) {
    return { ...EMPTY_STATE, roster, profiles }
  }

  const root = teamRootFromHome(home)
  const sep = root.includes('\\') ? '\\' : '/'

  const [workspaces, tasks, approvals, activity, registry, centerFile] = await Promise.all([
    readJsonDir<WorkspaceRow>(`${root}${sep}workspaces`),
    readJsonDir<TaskRow>(`${root}${sep}tasks`),
    readJsonDir<ApprovalCard>(`${root}${sep}approvals`),
    readJsonl<ActivityRow>(`${root}${sep}activity`),
    window.hermesDesktop?.readFileText?.(`${root}${sep}knowledge-registry.json`).catch(() => null) ??
      Promise.resolve(null),
    window.hermesDesktop?.readFileText?.(`${root}${sep}knowledge${sep}center.json`).catch(() => null) ??
      Promise.resolve(null)
  ])

  let sources: KnowledgeSource[] = []

  try {
    sources = registry?.text ? ((JSON.parse(registry.text) as { sources?: KnowledgeSource[] }).sources ?? []) : []
  } catch {
    sources = []
  }

  let center: KnowledgeCenterData | null = null

  try {
    center = centerFile?.text ? (JSON.parse(centerFile.text) as KnowledgeCenterData) : null
  } catch {
    center = null
  }

  return { root, roster, workspaces, tasks, approvals, activity, sources, center, profiles }
}

export function useTeamState(intervalMs = 20_000): { state: TeamState | null; reload: () => void } {
  const [state, setState] = useState<TeamState | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let cancelled = false
    void loadTeamState().then(next => {
      if (!cancelled) {
        setState(next)
      }
    })
    const timer = window.setInterval(() => setTick(t => t + 1), intervalMs)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [tick, intervalMs])

  return { state, reload: () => setTick(t => t + 1) }
}
