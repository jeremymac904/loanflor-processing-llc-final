import { cn } from '@hermes/plugin-sdk'

export const AGO = {
  ageNow: 'now',
  ageSeconds: (s: number) => `${s}s ago`,
  ageMinutes: (m: number) => `${m}m ago`,
  ageHours: (h: number) => `${h}h ago`,
  ageDays: (d: number) => `${d}d ago`
}

export function Pill({ children, tone = 'muted' }: { children: React.ReactNode; tone?: 'muted' | 'warn' | 'bad' | 'good' }) {
  return (
    <span
      className={cn(
        'rounded px-1.5 py-px text-[0.6875rem]',
        tone === 'muted' && 'bg-(--ui-bg-quaternary) text-(--ui-text-secondary)',
        tone === 'warn' && 'bg-(--ui-bg-quaternary) text-(--ui-accent)',
        tone === 'bad' && 'text-destructive',
        tone === 'good' && 'text-(--ui-accent)'
      )}
    >
      {children}
    </span>
  )
}

/** A plain label + value line ("Income: Complete"). */
export function Fact({ label, value, tone }: { label: string; value: React.ReactNode; tone?: 'muted' | 'warn' | 'bad' | 'good' }) {
  return (
    <div className="flex flex-col">
      <span className="text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)">{label}</span>
      <span className={cn('text-sm', tone === 'bad' && 'text-destructive', tone === 'good' && 'text-(--ui-accent)')}>{value}</span>
    </div>
  )
}
