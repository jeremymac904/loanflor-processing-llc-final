import type { ComposerAttachment } from '@/store/composer'

const INTAKE_INTENT = /\b(add|start|review|open|load|prep|prepare|import)\b.{0,50}\b(loan|file|pipeline|client|this)\b|\b(add|start|review|open|load|prep|prepare|import)\s+(this|it)\b/i

export function attachedMismoPaths(text: string, attachments: ComposerAttachment[] = []): string[] {
  if (!INTAKE_INTENT.test(text)) return []

  return attachments
    .filter(isMismoAttachment)
    .filter(item => Boolean(item.path))
    .map(item => item.path!)
}

export function isMismoAttachment(item: ComposerAttachment): boolean {
  return [item.path, item.label, item.detail].some(value => Boolean(value && /\.(xml|mismo)$/i.test(value)))
}

export function intakeAcknowledgement(): string {
  return 'The requested local loan intake is complete. The Customer File is in Pipeline and Malcolm’s deterministic file review is saved. Acknowledge briefly; do not request the file or repeat personal details.'
}
