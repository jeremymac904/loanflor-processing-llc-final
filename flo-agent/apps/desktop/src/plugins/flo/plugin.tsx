/**
 * Flo — Ashley's whole app surface, as one bundled desktop plugin.
 *
 * Sidebar (Ashley-facing): Today (/flo, home) · Pipeline (/pipeline) ·
 * Approvals (/approvals). Not in the sidebar: Advanced (/flo-team) for
 * Jeremy / administration (team roster and direct bot chat, raw Deal Rooms,
 * activity log, sources, Knowledge Center, providers).
 *
 * Today answers the only questions the UI needs to: what matters right now,
 * what do I need to do, what is the team handling, what are we waiting on,
 * is anything at risk, is there anything to approve. Three primary actions
 * (Review Approval / Open Pipeline / Ask Flo). Every button anywhere goes
 * through Flo (`./chat.ts`); Ashley never picks a bot.
 *
 * Pure SDK consumer: no core edits, no new RPCs. The Today model is derived in
 * `./ashley.ts` from the same files the backend plugin writes; the backend's
 * `plugins/flo-team/today.py` applies the same rules for Flo's chat answers.
 */

import {
  Button,
  cn,
  type HermesPlugin,
  host,
  Loader,
  PALETTE_AREA,
  type PaletteContribution,
  requestTheme,
  type RouteContribution,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  type SidebarNavContribution,
  THEMES_AREA,
  Wordmark
} from '@hermes/plugin-sdk'
import { useMemo } from 'react'

import { FLO_ACTIONS } from './actions'
import { ADVANCED_ROUTE, AdvancedPage } from './advanced'
import { APPROVALS_ROUTE, ApprovalsPage } from './approvals'
import { NEXT_MOVE_PROMPT, STATUS_TONE, todayModel } from './ashley'
import { preferFloProfile, reportStartFailure, startFloChat } from './chat'
import floBadge from './flo-badge.png'
import { FLO_ONBOARDING_ROUTE, FloOnboarding } from './onboarding/FloOnboarding'
import { PIPELINE_ROUTE, PipelinePage, useAsk } from './pipeline'
import { useTeamState } from './state'
import { FLO_THEME_NAME, floTheme } from './theme'
import { Pill } from './ui'

const TODAY_ROUTE = '/flo'
// Bump the suffix when first-launch behaviour changes (e.g. a new brand theme)
// so existing installs get it once more.
const LANDED_KEY = 'landed-v3'
// Bump when Ashley's onboarding flow changes shape so existing installs
// get the new card layout once more.
const FLO_ONBOARDING_DONE_KEY = 'flo-onboarding-done-v1'

/** The two quick asks that earn a spot on Today; the rest stay in the palette. */
const QUICK_ASKS = FLO_ACTIONS.filter(a => a.id === 'morning-brief' || a.id === 'eod-recap')

function Card({ title, children, tone }: { title: string; children: React.ReactNode; tone?: 'bad' }) {
  return (
    <div className="rounded-md border border-(--ui-stroke-tertiary) p-3">
      <h2 className="m-0 text-xs font-semibold uppercase tracking-wide text-(--ui-text-tertiary)">{title}</h2>
      <p className={cn('m-0 mt-1 text-sm', tone === 'bad' && 'text-destructive')}>{children}</p>
    </div>
  )
}

function TodayPage() {
  const { state } = useTeamState()
  const { ask, busy, profile } = useAsk(state)
  const model = useMemo(() => (state ? todayModel(state) : null), [state])
  const isBusy = busy !== null

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-6 py-8">
      <header className="flex items-center gap-4">
        <img alt="" aria-hidden className="size-16 shrink-0 select-none" draggable={false} src={floBadge} />
        <div className="flex flex-col gap-1">
          <Wordmark text="FLO" />
          <p className="m-0 text-base font-medium">{model?.greeting ?? 'Hi Ash'}</p>
          <p className="m-0 text-sm text-(--ui-text-secondary)">
            {model && model.top.length > 0
              ? 'I’ve got the messy stuff sorted. Here’s what matters.'
              : 'Nothing on fire. Here’s where we are.'}
          </p>
        </div>
      </header>

      {!model ? <Loader /> : null}

      {model ? (
        <>
          {model.newLoans.length > 0 ? (
            <section className="flex flex-col gap-2">
              {model.newLoans.map(loan => (
                <div
                  className="flex flex-wrap items-center gap-4 rounded-md border border-(--ui-accent) p-4"
                  key={loan.workspaceId}
                >
                  <div className="flex min-w-0 flex-col gap-1">
                    <span className="text-[0.6875rem] font-semibold uppercase tracking-wide text-(--ui-accent)">
                      New loan
                    </span>
                    <span className="text-base font-semibold">{loan.name}</span>
                    <span className="text-sm text-(--ui-text-secondary)">
                      Submitted by {loan.submittedBy}
                      {loan.program ? ` · ${loan.program}` : ''}
                      {loan.expectedClosing ? ` · Expected closing ${loan.expectedClosing}` : ''}
                    </span>
                    <span className="text-sm">{loan.line}</span>
                    {loan.documentsReceived > 0 ? (
                      <span className="text-xs text-(--ui-text-tertiary)">
                        {loan.documentsReceived} {loan.documentsReceived === 1 ? 'document' : 'documents'} in the file
                      </span>
                    ) : null}
                  </div>
                  <Button
                    className="ml-auto"
                    onClick={() => host.navigate(`${PIPELINE_ROUTE}?file=${encodeURIComponent(loan.workspaceId)}`)}
                    size="sm"
                  >
                    Open File
                  </Button>
                </div>
              ))}
            </section>
          ) : null}

          <section className="flex flex-col gap-2">
            <h2 className="m-0 text-xs font-semibold uppercase tracking-wide text-(--ui-text-tertiary)">Top 3</h2>
            {model.top.length === 0 ? (
              <p className="m-0 text-sm text-(--ui-text-secondary)">No open files need you right now.</p>
            ) : (
              <ol className="m-0 flex list-none flex-col gap-2 p-0">
                {model.top.map((item, i) => (
                  <li className="flex gap-3 rounded-md border border-(--ui-stroke-tertiary) p-3" key={item.workspaceId}>
                    <span className="text-lg font-semibold text-(--ui-text-tertiary)">{i + 1}</span>
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{item.name}</span>
                        <Pill tone={STATUS_TONE[item.status]}>{item.status}</Pill>
                      </div>
                      {item.missingCount > 0 ? (
                        <span className="text-sm text-(--ui-text-secondary)">
                          Needs {item.missingCount} {item.missingCount === 1 ? 'item' : 'items'}
                        </span>
                      ) : null}
                      {item.waitingOn ? (
                        <span className="text-sm text-(--ui-text-secondary)">Waiting on: {item.waitingOn}</span>
                      ) : null}
                      <span className="text-sm text-(--ui-text-secondary)">Next move: {item.nextMove}</span>
                    </div>
                    <Button
                      className="ml-auto self-center"
                      onClick={() => host.navigate(`${PIPELINE_ROUTE}?file=${encodeURIComponent(item.workspaceId)}`)}
                      size="xs"
                      variant="secondary"
                    >
                      Open File
                    </Button>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Card title="Fastest win">{model.fastestWin?.line ?? 'Nothing quick on the board.'}</Card>
            <Card title="Biggest risk" tone={model.biggestRisk ? 'bad' : undefined}>
              {model.biggestRisk?.line ?? 'None. 💚'}
            </Card>
            <Card title="Needs you">
              {model.needsYou === 0
                ? 'Nothing waiting on you.'
                : `${model.needsYou} ${model.needsYou === 1 ? 'thing' : 'things'} to approve or review`}
            </Card>
            <Card title="Waiting on others">
              {model.waitingOnOthers === 0
                ? 'Nothing out with other people.'
                : `${model.waitingOnOthers} ${model.waitingOnOthers === 1 ? 'item' : 'items'}`}
            </Card>
          </section>

          <p className="m-0 text-sm text-(--ui-text-tertiary)">Everything else can wait.</p>

          <div className="flex flex-wrap gap-2">
            <Button disabled={model.needsYou === 0} onClick={() => host.navigate(APPROVALS_ROUTE)} size="sm">
              Review Approval{model.needsYou > 1 ? 's' : ''}
            </Button>
            <Button onClick={() => host.navigate(PIPELINE_ROUTE)} size="sm" variant="secondary">
              Open Pipeline
            </Button>
            <Button
              disabled={isBusy}
              onClick={() => ask('ask-flo', 'Ask Flo', NEXT_MOVE_PROMPT)}
              size="sm"
              variant="secondary"
            >
              Ask Flo
            </Button>
          </div>

          <section className="flex flex-wrap items-center gap-2 border-t border-(--ui-stroke-tertiary) pt-4">
            {QUICK_ASKS.map(action => (
              <Button
                disabled={isBusy}
                key={action.id}
                onClick={() => ask(action.id, action.title, action.prompt)}
                size="xs"
                variant="secondary"
              >
                {action.title}
              </Button>
            ))}
            <Button disabled={isBusy} onClick={() => host.newChat(profile)} size="xs" variant="secondary">
              Blank chat
            </Button>
            <button
              className="ml-auto text-xs text-(--ui-text-quaternary) hover:underline"
              onClick={() => host.navigate(ADVANCED_ROUTE)}
              type="button"
            >
              Advanced
            </button>
          </section>
        </>
      ) : null}
    </div>
  )
}

const plugin: HermesPlugin = {
  id: 'flo',
  name: 'Flo',
  description: 'Today, Pipeline and Approvals for Ashley; team, sources and providers under Advanced.',
  register(ctx) {
    ctx.registerMany([
      { id: 'theme', area: THEMES_AREA, data: floTheme },
      {
        id: 'flo-onboarding',
        area: ROUTES_AREA,
        data: { path: FLO_ONBOARDING_ROUTE } satisfies RouteContribution,
        render: () => <FloOnboarding storage={ctx.storage} />
      },
      {
        id: 'today',
        area: ROUTES_AREA,
        data: { path: TODAY_ROUTE } satisfies RouteContribution,
        render: () => <TodayPage />
      },
      {
        id: 'pipeline',
        area: ROUTES_AREA,
        data: { path: PIPELINE_ROUTE } satisfies RouteContribution,
        render: () => <PipelinePage />
      },
      {
        id: 'approvals',
        area: ROUTES_AREA,
        data: { path: APPROVALS_ROUTE } satisfies RouteContribution,
        render: () => <ApprovalsPage />
      },
      {
        id: 'advanced',
        area: ROUTES_AREA,
        data: { path: ADVANCED_ROUTE } satisfies RouteContribution,
        render: () => <AdvancedPage />
      },
      {
        id: 'nav-today',
        area: SIDEBAR_NAV_AREA,
        order: 1,
        data: { codicon: 'home', label: 'Today', path: TODAY_ROUTE } satisfies SidebarNavContribution
      },
      {
        id: 'nav-pipeline',
        area: SIDEBAR_NAV_AREA,
        order: 2,
        data: { codicon: 'list-flat', label: 'Pipeline', path: PIPELINE_ROUTE } satisfies SidebarNavContribution
      },
      {
        id: 'nav-approvals',
        area: SIDEBAR_NAV_AREA,
        order: 3,
        data: { codicon: 'check', label: 'Approvals', path: APPROVALS_ROUTE } satisfies SidebarNavContribution
      },
      {
        id: 'palette-today',
        area: PALETTE_AREA,
        data: {
          id: 'flo.open',
          label: 'Flo: Today',
          keywords: ['flo', 'home', 'today', 'brief', 'ashley'],
          run: () => host.navigate(TODAY_ROUTE)
        } satisfies PaletteContribution
      },
      {
        id: 'palette-pipeline',
        area: PALETTE_AREA,
        data: {
          id: 'flo.pipeline',
          label: 'Flo: Pipeline',
          keywords: ['flo', 'pipeline', 'files', 'deal room'],
          run: () => host.navigate(PIPELINE_ROUTE)
        } satisfies PaletteContribution
      },
      {
        id: 'palette-approvals',
        area: PALETTE_AREA,
        data: {
          id: 'flo.approvals',
          label: 'Flo: Approvals',
          keywords: ['flo', 'approve', 'approvals', 'queue'],
          run: () => host.navigate(APPROVALS_ROUTE)
        } satisfies PaletteContribution
      },
      {
        id: 'palette-advanced',
        area: PALETTE_AREA,
        data: {
          id: 'flo.advanced',
          label: 'Flo: Advanced (team, sources, providers)',
          keywords: ['flo', 'team', 'bots', 'knowledge', 'sources', 'sage', 'health', 'admin', 'advanced'],
          run: () => host.navigate(ADVANCED_ROUTE)
        } satisfies PaletteContribution
      },
      ...FLO_ACTIONS.map(action => ({
        id: `action-${action.id}`,
        area: PALETTE_AREA,
        data: {
          id: `flo.${action.id}`,
          label: `Flo: ${action.title}`,
          keywords: ['flo', ...action.title.toLowerCase().split(' ')],
          run: () => {
            void startFloChat(
              action.title,
              action.prompt,
              preferFloProfile([], (host.state.profile.get() as null | string | undefined) ?? null)
            ).catch((error: unknown) => reportStartFailure(action.title, error))
          }
        } satisfies PaletteContribution
      }))
    ])

    // Land on the Flo onboarding the first time the app opens with this
    // plugin. Ashley must complete (or skip past) the onboarding card
    // before Today/Pipeline/Approvals reveal themselves — she never sees
    // the default Hermes provider-onboarding UI.
    if (!ctx.storage.get<boolean>(LANDED_KEY, false)) {
      ctx.storage.set(LANDED_KEY, true)
      window.setTimeout(() => {
        // Brand theme on first launch only; a later manual pick in
        // Appearance is respected (never re-applied).
        requestTheme(FLO_THEME_NAME)
        const onboarded = ctx.storage.get<boolean>(FLO_ONBOARDING_DONE_KEY, false)
        host.navigate(onboarded ? TODAY_ROUTE : FLO_ONBOARDING_ROUTE)
      }, 0)
    }
  }
}

export default plugin
