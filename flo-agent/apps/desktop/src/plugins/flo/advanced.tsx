/**
 * Advanced — for Jeremy / administration, never in Ashley's sidebar.
 * Team (bot roster + direct chat), raw Deal Rooms, the activity log, Sage's
 * source registry, the Knowledge Center (source lifecycle) and provider
 * routing. Reached from the small "Advanced" link on Today or the palette.
 */

import { Button, cn, Codicon, formatAgo, host, Loader, useValue } from '@hermes/plugin-sdk'
import { useState } from 'react'

import { availableActions, effectiveLabel, freshnessLabel, KNOWLEDGE_CENTER_ACTIONS, openTasksByAgent, recentActivity } from './data'
import { type TeamState, useTeamState } from './state'
import { AGO, Pill } from './ui'

export const ADVANCED_ROUTE = '/flo-team'
/** Static approved portraits (apps/desktop/public/team/<name>-<size>.png, circular crops of the owner-approved masters). */
const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`
const portrait = (name: string, size: 64 | 128 | 256 = 128) => assetPath(`team/${name}-${size}.png`)

const TABS = ['floor', 'rooms', 'activity', 'knowledge', 'center', 'health'] as const
type Tab = (typeof TABS)[number]

const LABEL: Record<Tab, string> = {
  floor: 'Team',
  rooms: 'Deal Rooms (raw)',
  activity: 'Activity log',
  knowledge: 'Sources',
  center: 'Knowledge Center',
  health: 'Providers'
}

function Floor({ state }: { state: TeamState }) {
  const open = openTasksByAgent(state.tasks)

  if (state.roster.length === 0) {
    return (
      <p className="text-xs text-(--ui-text-tertiary)">
        No Flo Team profiles installed yet. Run <code>python scripts/flo/install_flo_team.py</code> and restart the
        backend.
      </p>
    )
  }

  return (
    <ul className="m-0 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
      {state.roster.map(member => {
        const tasks = open[member.name] ?? []
        const attention = tasks.some(t => t.status === 'sent')

        return (
          <li className="flex flex-col gap-2 rounded-md border border-(--ui-stroke-tertiary) p-3" key={member.name}>
            <div className="flex items-center gap-2">
              <img
                alt=""
                aria-hidden
                className="size-10 shrink-0 select-none rounded-full"
                draggable={false}
                src={portrait(member.name, 128)}
                style={{ boxShadow: `0 0 0 2px ${member.color}` }}
              />
              <div className="flex min-w-0 flex-col">
                <span className="text-sm font-medium">{member.displayName}</span>
                <span className="text-xs text-(--ui-text-secondary)">{member.title}</span>
              </div>
              {member.pinned ? <Codicon className="ml-auto text-(--ui-text-quaternary)" name="pinned" /> : null}
            </div>
            <p className="m-0 text-xs text-(--ui-text-secondary)">{member.description}</p>
            <div className="flex flex-wrap gap-1 text-xs">
              <Pill tone={member.busy ? 'good' : 'muted'}>{member.busy ? 'working' : 'idle'}</Pill>
              <Pill>{tasks.length} open</Pill>
              {attention ? <Pill tone="warn">needs attention</Pill> : null}
              {member.lastSessionAt ? <Pill>last {formatAgo(member.lastSessionAt, AGO)}</Pill> : null}
            </div>
            {tasks[0] ? <p className="m-0 truncate text-xs text-(--ui-text-tertiary)">↳ {tasks[0].objective}</p> : null}
            <Button onClick={() => host.newChat(member.name)} size="xs" variant="secondary">
              Chat with {member.displayName}
            </Button>
          </li>
        )
      })}
    </ul>
  )
}

function Rooms({ state }: { state: TeamState }) {
  const [selected, setSelected] = useState<null | string>(null)
  const ws = state.workspaces.find(w => w.workspace_id === selected) ?? null

  if (state.workspaces.length === 0) {
    return <p className="text-xs text-(--ui-text-tertiary)">No Deal Rooms yet.</p>
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-[16rem_1fr]">
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {state.workspaces.map(w => (
          <li key={w.workspace_id}>
            <button
              className={cn(
                'w-full rounded px-2 py-1 text-left text-xs hover:bg-(--chrome-action-hover)',
                selected === w.workspace_id && 'bg-(--ui-bg-quaternary)'
              )}
              onClick={() => setSelected(w.workspace_id)}
              type="button"
            >
              <span className="font-medium">{w.display_name ?? w.workspace_id}</span>
              <span className="ml-2 text-(--ui-text-tertiary)">{w.milestone}</span>
            </button>
          </li>
        ))}
      </ul>
      {ws ? (
        <div className="flex flex-col gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{ws.display_name}</span>
            <Pill>{ws.workspace_id}</Pill>
            <Pill>{ws.milestone}</Pill>
            {ws.program ? <Pill>{ws.program}</Pill> : null}
            {ws.readiness ? (
              <Pill tone="warn">
                readiness {ws.readiness.score} · {ws.readiness.status}
              </Pill>
            ) : null}
          </div>
          <p className="m-0 text-(--ui-text-secondary)">{ws.status_summary ?? 'No status summary yet.'}</p>
          <div>
            <span className="text-(--ui-text-tertiary)">Deal Room: </span>
            {(ws.members ?? []).join(', ')} <span className="text-(--ui-text-quaternary)">(Franklin excluded)</span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Pill>{(ws.blockers ?? []).length} blockers</Pill>
            <Pill>{(ws.orders ?? []).length} orders</Pill>
            <Pill>{(ws.drafts ?? []).length} drafts</Pill>
            <Pill>{(ws.agent_tasks ?? []).length} tasks</Pill>
          </div>
          <ul className="m-0 flex list-none flex-col gap-1 p-0">
            {(ws.activity ?? [])
              .slice(-12)
              .reverse()
              .map((a, i) => (
                <li className="flex gap-2 text-(--ui-text-secondary)" key={`${a.timestamp}-${i}`}>
                  <span className="w-16 shrink-0 text-(--ui-text-tertiary)">{formatAgo(Date.parse(a.timestamp), AGO)}</span>
                  <span className="font-mono">{a.actor}</span>
                  <span>{a.event}</span>
                </li>
              ))}
          </ul>
        </div>
      ) : (
        <p className="text-xs text-(--ui-text-tertiary)">Pick a file.</p>
      )}
    </div>
  )
}

function Activity({ state }: { state: TeamState }) {
  const rows = recentActivity(state.activity)

  if (rows.length === 0) {
    return <p className="text-xs text-(--ui-text-tertiary)">No team activity yet.</p>
  }

  return (
    <ul className="m-0 flex list-none flex-col gap-1 p-0 text-xs">
      {rows.map((row, i) => (
        <li className="flex items-center gap-2 text-(--ui-text-secondary)" key={`${row.timestamp}-${i}`}>
          <span className="w-16 shrink-0 text-(--ui-text-tertiary)">{row.timestamp ? formatAgo(Date.parse(row.timestamp), AGO) : ''}</span>
          <span className="font-mono">{row.actor ?? '?'}</span>
          <span>{row.event ?? row.tool}</span>
          {row.decision ? (
            <Pill tone={row.decision === 'deny' ? 'bad' : row.decision === 'confirm' ? 'warn' : 'muted'}>{row.decision}</Pill>
          ) : null}
          {row.workspace_id ? <span className="ml-auto text-(--ui-text-tertiary)">{row.workspace_id}</span> : null}
        </li>
      ))}
    </ul>
  )
}

function Knowledge({ state }: { state: TeamState }) {
  if (state.sources.length === 0) {
    return <p className="text-xs text-(--ui-text-tertiary)">No knowledge registry found (the installer copies it).</p>
  }

  return (
    <div className="flex flex-col gap-2 text-xs">
      <p className="m-0 text-(--ui-text-secondary)">
        Official sources Sage knows about. Nothing is “current” until an administrator moves a revision to active; until
        then every guideline answer is SOURCE_GAP with the official link.
      </p>
      <table className="w-full border-collapse">
        <thead>
          <tr className="text-left text-(--ui-text-tertiary)">
            <th className="py-1 font-normal">Source</th>
            <th className="py-1 font-normal">Program</th>
            <th className="py-1 font-normal">Published</th>
            <th className="py-1 font-normal">Checked</th>
            <th className="py-1 font-normal">Lifecycle</th>
          </tr>
        </thead>
        <tbody>
          {state.sources.map(s => (
            <tr className="border-t border-(--ui-stroke-tertiary)" key={s.source_id}>
              <td className="py-1">{s.title ?? s.source_id}</td>
              <td className="py-1">{s.program}</td>
              <td className="py-1">{s.publication_date ?? '—'}</td>
              <td className="py-1">{s.checked_at ?? '—'}</td>
              <td className="py-1">
                <Pill tone={freshnessLabel(s) === 'active' ? 'good' : 'warn'}>{freshnessLabel(s)}</Pill>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function KnowledgeCenter({ state }: { state: TeamState }) {
  const [program, setProgram] = useState<string>('all')
  const [selected, setSelected] = useState<null | string>(null)
  const [copied, setCopied] = useState<null | string>(null)
  const data = state.center

  if (!data) {
    return (
      <p className="text-xs text-(--ui-text-tertiary)">
        No Knowledge Center data yet. An administrator builds it with <code>python scripts/flo/knowledge_center.py --build</code>{' '}
        (it reads the private source cache and this install’s activation state).
      </p>
    )
  }

  const programs = Array.from(new Set(data.rows.map(r => r.program)))
  const rows = data.rows.filter(r => program === 'all' || r.program === program)
  const row = rows.find(r => r.revision_id === selected) ?? null

  const copy = (label: string, command: string) => {
    void navigator.clipboard?.writeText(command).catch(() => undefined)
    setCopied(label)
    window.setTimeout(() => setCopied(null), 1500)
  }

  return (
    <div className="flex flex-col gap-3 text-xs">
      <p className="m-0 text-(--ui-text-secondary)">
        Administrator view of the source lifecycle (detected → pending review → regression → approval → active). Every
        action below is a command run by a human with a structured approver identity; nothing here is available in
        ordinary chat. Generated {formatAgo(Date.parse(data.generated_at), AGO)}.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-(--ui-text-tertiary)">Program</span>
        {['all', ...programs].map(p => (
          <button
            className={cn('rounded px-2 py-0.5 hover:bg-(--chrome-action-hover)', program === p && 'bg-(--ui-bg-quaternary) font-medium')}
            key={p}
            onClick={() => setProgram(p)}
            type="button"
          >
            {p}
          </button>
        ))}
        <span className="ml-auto text-(--ui-text-tertiary)">
          {data.guidance_pending.length} guidance item(s) pending · {data.overlays.length} overlay record(s)
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left text-(--ui-text-tertiary)">
              <th className="py-1 font-normal">Program</th>
              <th className="py-1 font-normal">Section</th>
              <th className="py-1 font-normal">Version</th>
              <th className="py-1 font-normal">Published</th>
              <th className="py-1 font-normal">Effective</th>
              <th className="py-1 font-normal">Status</th>
              <th className="py-1 font-normal">Rules</th>
              <th className="py-1 font-normal">Regression</th>
              <th className="py-1 font-normal">Approval</th>
              <th className="py-1 font-normal">Pending update</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr
                className={cn(
                  'cursor-pointer border-t border-(--ui-stroke-tertiary) hover:bg-(--chrome-action-hover)',
                  selected === r.revision_id && 'bg-(--ui-bg-quaternary)'
                )}
                key={r.revision_id}
                onClick={() => setSelected(r.revision_id)}
              >
                <td className="py-1">{r.program_display}</td>
                <td className="py-1 font-mono">{r.section}</td>
                <td className="py-1">{r.version ?? '—'}</td>
                <td className="py-1">{r.published ?? '—'}</td>
                <td className="py-1">
                  {r.effective ?? '—'}{' '}
                  <Pill tone={effectiveLabel(r).startsWith('FUTURE') ? 'warn' : effectiveLabel(r) === 'CURRENT' ? 'good' : 'muted'}>
                    {effectiveLabel(r)}
                  </Pill>
                </td>
                <td className="py-1">
                  <Pill tone={r.status === 'active' ? 'good' : r.status === 'STALE_SOURCE' ? 'bad' : 'warn'}>{r.status}</Pill>
                </td>
                <td className="py-1">{r.rules_extracted}</td>
                <td className="py-1">
                  {r.regression.ok === null ? '—' : r.regression.ok ? `ok (${r.regression.checked})` : `FAILED ${r.regression.failed.length}`}
                </td>
                <td className="py-1">{r.human_approval?.approved_by_display_name ?? '—'}</td>
                <td className="py-1">{r.pending_update.length > 0 ? r.pending_update.map(p => p.status).join('; ') : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {row ? (
        <div className="flex flex-col gap-2 rounded-md border border-(--ui-stroke-tertiary) p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">
              {row.program_display} · {row.section}
            </span>
            <Pill>{row.title}</Pill>
            <Pill>checksum {row.checksum}</Pill>
            <Pill>{row.revision_id}</Pill>
          </div>
          <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
            <span>
              <span className="text-(--ui-text-tertiary)">Source: </span>
              {row.source}
            </span>
            <span>
              <span className="text-(--ui-text-tertiary)">Current version: </span>
              {row.current_version ?? row.section} ({effectiveLabel(row)})
            </span>
            <span>
              <span className="text-(--ui-text-tertiary)">Supersedes: </span>
              {row.supersedes.length > 0 ? row.supersedes.join(', ') : '—'}
            </span>
            <span>
              <span className="text-(--ui-text-tertiary)">Human approval: </span>
              {row.human_approval
                ? `${row.human_approval.approved_by_display_name} (${row.human_approval.approved_by_user_id}, ${row.human_approval.identity_source}) ${row.human_approval.approved_at ?? ''}`
                : 'none'}
            </span>
            <span className="sm:col-span-2">
              <span className="text-(--ui-text-tertiary)">Impact: </span>
              {row.impact.summary}
            </span>
            {row.official_url ? (
              <span className="sm:col-span-2">
                <span className="text-(--ui-text-tertiary)">Official: </span>
                <a href={row.official_url} rel="noreferrer" target="_blank">
                  {row.official_url}
                </a>
              </span>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-1">
            {KNOWLEDGE_CENTER_ACTIONS.filter(([key]) => availableActions(row).includes(key)).map(([key, label]) => (
              <Button key={key} onClick={() => copy(label, row.actions[key] ?? '')} size="xs" variant="secondary">
                {copied === label ? 'Copied' : label}
              </Button>
            ))}
          </div>
          <p className="m-0 text-(--ui-text-quaternary)">
            Each button copies the exact administrator command; run it in a terminal with your approver identity
            (FLO_APPROVER_ID / FLO_APPROVER_NAME or --approver-name). The lifecycle is enforced by the command, not by this page.
          </p>
        </div>
      ) : (
        <p className="m-0 text-(--ui-text-tertiary)">Pick a section revision to see metadata, rules, impact and actions.</p>
      )}
      {data.guidance_pending.length > 0 ? (
        <details>
          <summary className="cursor-pointer text-(--ui-text-secondary)">Guidance pending review ({data.guidance_pending.length})</summary>
          <ul className="m-0 mt-2 flex list-none flex-col gap-1 p-0">
            {data.guidance_pending.map(g => (
              <li className="flex flex-wrap gap-2" key={g.guidance_id}>
                <Pill tone="warn">{g.scope}</Pill>
                <span>{g.text}</span>
                <span className="font-mono text-(--ui-text-tertiary)">{g.source_ref}</span>
                <span className="font-mono text-(--ui-text-quaternary)">{g.guidance_id}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  )
}

function Health({ state }: { state: TeamState }) {
  const byName = new Map(state.profiles.map(p => [p.name, p] as const))

  return (
    <div className="flex flex-col gap-2 text-xs">
      <p className="m-0 text-(--ui-text-secondary)">
        Configured provider per bot. Ask any bot to run <code>flo_model_health</code> or <code>flo_workflow action=preflight</code>{' '}
        for the live check. Sensitive work never falls back to cloud.
      </p>
      <ul className="m-0 list-none p-0">
        {state.roster.map(m => {
          const p = byName.get(m.name)
          const local = (p?.provider ?? '') === 'custom' || (p?.provider ?? '').includes('ollama') || (p?.provider ?? '').includes('local')

          return (
            <li className="flex items-center gap-2 border-t border-(--ui-stroke-tertiary) py-1" key={m.name}>
              <span className="w-24 font-medium">{m.displayName}</span>
              <span className="text-(--ui-text-secondary)">{p?.provider ?? 'not configured'}</span>
              <span className="font-mono text-(--ui-text-tertiary)">{p?.model ?? ''}</span>
              <Pill tone={local ? 'good' : 'muted'}>{local ? 'local' : 'cloud'}</Pill>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function AdvancedPage() {
  const profile = useValue(host.state.profile) as null | string | undefined
  const { state, reload } = useTeamState()
  const [tab, setTab] = useState<Tab>('floor')

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-6 py-8">
      <header className="flex items-center gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 text-lg font-semibold tracking-wide">Advanced</h1>
          <p className="m-0 text-sm text-(--ui-text-secondary)">
            Team, sources and providers for administration. Ashley’s day lives on Today, Pipeline and Approvals.
          </p>
        </div>
        <div className="ml-auto flex gap-2">
          <Button onClick={() => host.navigate('/flo')} size="xs" variant="secondary">
            Back to Today
          </Button>
          <Button onClick={reload} size="xs" variant="secondary">
            Refresh
          </Button>
        </div>
      </header>
      <nav className="flex flex-wrap gap-1 border-b border-(--ui-stroke-tertiary) pb-2">
        {TABS.map(t => (
          <button
            className={cn('rounded px-2 py-1 text-xs hover:bg-(--chrome-action-hover)', tab === t && 'bg-(--ui-bg-quaternary) font-medium')}
            key={t}
            onClick={() => setTab(t)}
            type="button"
          >
            {LABEL[t]}
          </button>
        ))}
        <span className="ml-auto text-xs text-(--ui-text-quaternary)">viewing as {profile ?? 'default'}</span>
      </nav>
      {!state ? <Loader /> : null}
      {state && tab === 'floor' ? <Floor state={state} /> : null}
      {state && tab === 'rooms' ? <Rooms state={state} /> : null}
      {state && tab === 'activity' ? <Activity state={state} /> : null}
      {state && tab === 'knowledge' ? <Knowledge state={state} /> : null}
      {state && tab === 'center' ? <KnowledgeCenter state={state} /> : null}
      {state && tab === 'health' ? <Health state={state} /> : null}
    </div>
  )
}
