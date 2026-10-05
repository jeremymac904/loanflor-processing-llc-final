import { useStore } from '@nanostores/react'
import { useEffect, useMemo, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router'

import { sessionTitle } from '@/lib/chat-runtime'
import { $sessions } from '@/store/session'
import { $activeGatewayProfile, normalizeProfileKey, selectProfile } from '@/store/profile'
import { routeSessionId, sessionRoute } from '@/app/routes'

import { PIPELINE_ROUTE } from './pipeline'
import { APPROVALS_ROUTE } from './approvals'
import floBadge from './flo-badge.png'
import { customerFileOverview, fileName, type FileRecord } from './ashley'
import { useTeamState } from './state'
import { setActiveCustomerFile } from './actions-api'

const TODAY_ROUTE = '/flo'

type FloShellProps = {
  children: React.ReactNode
  onOpenSettings: () => void
}

function dateLabel(timestamp: number): string {
  if (!timestamp) return ''
  const date = new Date(timestamp * 1000)
  const today = new Date()
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function LeafIcon({ className = '' }: { className?: string }) {
  return (
    <svg aria-hidden className={className} viewBox="0 0 24 24">
      <path
        d="M19.7 3.4C12.6 3.8 7.3 6.5 5.1 11.2c-1.4 3-.8 6.4 1.2 8.2 2.3-5.9 6-9.2 11-11.3-4.1 2.9-7 6.4-8.7 10.6 2.6.5 5.4-.5 7.1-2.7 2.7-3.4 3.6-7.8 4-12.6Z"
        fill="currentColor"
      />
    </svg>
  )
}

const NAV = [
  { label: 'Today', path: TODAY_ROUTE, glyph: '⌂' },
  { label: 'Pipeline', path: PIPELINE_ROUTE, glyph: '▤' },
  { label: 'Approvals', path: APPROVALS_ROUTE, glyph: '✓' },
  { label: 'Flo Chat', path: '/', glyph: '✦' }
] as const

export function FloAshleyShell({ children, onOpenSettings }: FloShellProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const sessions = useStore($sessions)
  const activeProfile = useStore($activeGatewayProfile)
  const { state } = useTeamState()
  const floProfileSelected = useRef(false)
  const isSettingsRoute = location.pathname.startsWith('/settings')

  useEffect(() => {
    if (floProfileSelected.current || !state?.profiles.some(profile => normalizeProfileKey(profile.name) === 'flo')) {
      return
    }

    floProfileSelected.current = true
    if (normalizeProfileKey(activeProfile) !== 'flo') {
      selectProfile('flo')
    }
  }, [activeProfile, state?.profiles])

  const recentSessions = useMemo(
    () =>
      sessions
        .filter(session => !session.archived && (!session.profile || session.profile.toLowerCase() === 'flo'))
        .sort((a, b) => Math.max(b.last_active, b.started_at) - Math.max(a.last_active, a.started_at))
        .slice(0, 5),
    [sessions]
  )

  const currentFile = useMemo(() => {
    const requested = new URLSearchParams(location.search).get('file')
    const rows = state?.workspaces ?? []
    if (requested) return rows.find(row => row.workspace_id === requested) ?? null
    return [...rows].sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))[0] ?? null
  }, [location.search, state?.workspaces])

  useEffect(() => {
    const explicitFileId = new URLSearchParams(location.search).get('file')
    setActiveCustomerFile(explicitFileId || currentFile?.workspace_id || null)
  }, [currentFile?.workspace_id, location.search])

  const currentFileRecord = currentFile as FileRecord | null
  const currentFileOverview = currentFileRecord ? customerFileOverview(currentFileRecord) : null

  return (
    <div className="flo-ashley-shell" data-flo-shell="">
      <header className="flo-window-bar">
        <span>Flo</span>
        <i aria-hidden />
        <span>Mortgage Operations</span>
      </header>

      <div className="flo-shell-body">
        <aside className="flo-primary-sidebar" aria-label="Flo navigation">
          <div className="flo-sidebar-brand">
            <img alt="Flo" draggable={false} src={floBadge} />
          </div>

          <nav className="flo-primary-nav">
            {NAV.map(item => {
              const active =
                item.path === '/'
                  ? location.pathname === '/' || routeSessionId(location.pathname) !== null
                  : location.pathname === item.path
              return (
                <button
                  aria-current={active ? 'page' : undefined}
                  className={active ? 'is-active' : undefined}
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  type="button"
                >
                  <span aria-hidden>{item.glyph}</span>
                  {item.label}
                </button>
              )
            })}
            <button
              onClick={() => document.getElementById('flo-recent-sessions')?.scrollIntoView({ behavior: 'smooth' })}
              type="button"
            >
              <span aria-hidden>◷</span>
              Sessions
            </button>
          </nav>

          <section className="flo-current-file" aria-labelledby="flo-current-file-label">
            <div className="flo-sidebar-label" id="flo-current-file-label">
              Current File
            </div>
            {currentFile ? (
              <button
                onClick={() => navigate(`${PIPELINE_ROUTE}?file=${encodeURIComponent(currentFile.workspace_id)}`)}
                type="button"
              >
                <LeafIcon className="flo-current-file-leaf" />
                <span>
                  <strong>{fileName(currentFile)}</strong>
                  <small>
                    {currentFileOverview?.loanNumber && currentFileOverview.loanNumber !== 'Not Set'
                      ? `Loan #${currentFileOverview.loanNumber}`
                      : `${currentFileOverview?.purpose ?? 'Customer File'} · ${currentFileOverview?.program ?? currentFile.program ?? ''}`}
                  </small>
                </span>
                <b aria-hidden>›</b>
              </button>
            ) : (
              <p>No active Customer File yet.</p>
            )}
          </section>

          <section className="flo-recent-sessions" id="flo-recent-sessions" aria-labelledby="flo-recent-label">
            <div className="flo-sidebar-label" id="flo-recent-label">
              Recent Sessions
            </div>
            <div className="flo-session-list">
              {recentSessions.length ? (
                recentSessions.map(session => (
                  <button key={session.id} onClick={() => navigate(sessionRoute(session.id))} type="button">
                    <span>{sessionTitle(session)}</span>
                    <time>{dateLabel(Math.max(session.last_active, session.started_at))}</time>
                  </button>
                ))
              ) : (
                <p>Your recent Flo chats will appear here.</p>
              )}
            </div>
          </section>

          <button className="flo-settings-link" onClick={onOpenSettings} type="button">
            <span aria-hidden>⚙</span> Settings &amp; Advanced
          </button>
        </aside>

        <main
          className={`flo-main-canvas${isSettingsRoute ? ' flo-main-canvas-settings' : ' flo-main-canvas-background'}`}
        >
          <div className="flo-chat-canvas">{children}</div>
        </main>
      </div>
    </div>
  )
}
