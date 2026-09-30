import type { FC } from 'react'

import floBadge from '@/plugins/flo/flo-badge.png'

/** Local, replaceable reaction assets. The stable id is persisted on the
 * message; changing the illustration later never rewrites history. */
export const CUSTOM_REACTIONS = [
  ['flo-happy', 'Flo Happy', 'Flo', '💚'],
  ['flo-heart', 'Flo Heart', 'Flo', '💚'],
  ['flo-thinking', 'Flo Thinking', 'Flo', '🤔'],
  ['flo-coffee', 'Flo Coffee', 'Flo', '☕'],
  ['flo-side-eye', 'Flo Side-Eye', 'Flo', '👀'],
  ['flo-celebration', 'Flo Celebration', 'Flo', '🎉'],
  ['flo-on-it', 'Flo On It', 'Flo', '🌿'],
  ['ctc-boom', 'CTC Boom', 'Flo', '✨'],
  ['malcolm-approved', 'Malcolm Approved', 'Malcolm', '✅'],
  ['malcolm-checking', 'Malcolm Checking', 'Malcolm', '🔎'],
  ['malcolm-found-it', 'Malcolm Found It', 'Malcolm', '🧾'],
  ['sage-thinking', 'Sage Thinking', 'Sage', '🧠'],
  ['sage-hmm', 'Sage Hmm', 'Sage', '👀'],
  ['sage-source-found', 'Sage Source Found', 'Sage', '📚'],
  ['chadwick-on-it', 'Chadwick On It', 'Chadwick', '🫡'],
  ['chadwick-ordered', 'Chadwick Ordered', 'Chadwick', '📦'],
  ['chadwick-waiting', 'Chadwick Waiting', 'Chadwick', '⏳'],
  ['whisper-drafted', 'Whisper Drafted', 'Whisper', '💌'],
  ['whisper-sent', 'Whisper Sent', 'Whisper', '✨'],
  ['whisper-heart', 'Whisper Heart', 'Whisper', '💚'],
  ['franklin-fire', 'Franklin Fire', 'Franklin', '🔥'],
  ['franklin-idea', 'Franklin Idea', 'Franklin', '💡'],
  ['franklin-nice', 'Franklin Nice', 'Franklin', '🙌']
] as const

export type CustomReactionId = (typeof CUSTOM_REACTIONS)[number][0]
const byId = new Map(CUSTOM_REACTIONS.map(([id, label, agent, glyph]) => [`:${id}:`, { label, agent, glyph }]))

export function customReaction(id: string) {
  return byId.get(id)
}

const AGENT_COLORS: Record<string, string> = {
  Malcolm: 'bg-emerald-100 text-emerald-900',
  Sage: 'bg-teal-100 text-teal-900',
  Chadwick: 'bg-amber-100 text-amber-900',
  Whisper: 'bg-rose-100 text-rose-900',
  Franklin: 'bg-lime-100 text-lime-900'
}

export const CustomReactionAsset: FC<{ id: string; size?: 'normal' | 'small' }> = ({ id, size = 'normal' }) => {
  const reaction = customReaction(id)
  if (!reaction) return <span>{id}</span>

  const dimensions = size === 'small' ? 'size-5' : 'size-8'
  return (
    <span
      aria-label={reaction.label}
      className={`relative inline-grid ${dimensions} shrink-0 place-items-center rounded-full ${reaction.agent === 'Flo' ? 'bg-[#e6f0e3]' : AGENT_COLORS[reaction.agent]}`}
      role="img"
      title={reaction.label}
    >
      {reaction.agent === 'Flo' ? (
        <img alt="" className="size-full object-contain" src={floBadge} />
      ) : (
        <span className="text-xs font-bold">{reaction.agent[0]}</span>
      )}
      <span aria-hidden className="absolute -bottom-1 -right-1 text-[0.65rem] leading-none">
        {reaction.glyph}
      </span>
    </span>
  )
}
