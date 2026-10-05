import {
  bindFloSession,
  getActiveCustomerFile,
  peekPendingWorkspaceBinding,
  requestPendingWorkspaceBinding,
  resolveFloTurnContext,
  runFloLocalIntake,
  takePendingWorkspaceBinding
} from '@/plugins/flo/actions-api'
import { attachedMismoPaths, intakeAcknowledgement, isMismoAttachment } from '@/plugins/flo/local-intake-intent'
import { notify, notifyError } from '@/store/notifications'
import { $selectedStoredSessionId } from '@/store/session'

import type { ChatActions, SidebarActions } from './types'

/**
 * Surfaces receive one stable `actions` object whose fields are mutated by the
 * wiring controller each render. If a memoized surface passes `actions.foo`
 * directly, the child keeps the function from the surface's last render and can
 * submit/click against a stale session closure. These adapters keep a stable
 * wrapper but dereference the latest field at call time.
 *
 * OPTIONAL handlers must stay optional. Several children gate on a handler's
 * *presence*, not just call it — `onDismissError` renders the dismiss button
 * only when it exists (assistant-message.tsx), `onRestoreToMessage` gates the
 * restore-confirm flow (thread/index.tsx), and `onTranscribeAudio` gates voice
 * recording/conversation (use-voice-recorder, use-voice-conversation). An
 * unconditional arrow wrapper is always truthy, which would render a dead
 * dismiss button and let voice recording proceed with no transcription backend.
 * So wrap an optional field only when it is currently present, and re-read the
 * latest value inside the wrapper for the stale-closure fix.
 */
function latestOptional<A extends unknown[], R>(
  read: () => ((...args: A) => R) | undefined
): ((...args: A) => R) | undefined {
  // Presence is sampled from the object identity the surface currently holds.
  // The controller mutates fields in place rather than swapping a handler
  // between defined and undefined, so presence is stable for a given actions
  // object while the *closure* is what churns — which is exactly what the
  // indirection below re-reads.
  return read() ? (...args: A) => read()!(...args) : undefined
}

export function latestChatActions(actions: ChatActions): ChatActions {
  return {
    onAddContextRef: (...args) => actions.onAddContextRef(...args),
    onAddUrl: (...args) => actions.onAddUrl(...args),
    onAttachDroppedItems: (...args) => actions.onAttachDroppedItems(...args),
    onAttachImageBlob: (...args) => actions.onAttachImageBlob(...args),
    onBranchInNewChat: latestOptional(() => actions.onBranchInNewChat),
    onCancel: (...args) => actions.onCancel(...args),
    onDeleteSelectedSession: (...args) => actions.onDeleteSelectedSession(...args),
    onDismissError: latestOptional(() => actions.onDismissError),
    onEdit: (...args) => actions.onEdit(...args),
    onPasteClipboardImage: (...args) => actions.onPasteClipboardImage(...args),
    onPickFiles: (...args) => actions.onPickFiles(...args),
    onPickFolders: (...args) => actions.onPickFolders(...args),
    onPickImages: (...args) => actions.onPickImages(...args),
    onReload: (...args) => actions.onReload(...args),
    onRemoveAttachment: (...args) => actions.onRemoveAttachment(...args),
    onRestoreToMessage: latestOptional(() => actions.onRestoreToMessage),
    onRetryResume: (...args) => actions.onRetryResume(...args),
    onSteer: (...args) => actions.onSteer(...args),
    onSubmit: async (text, options) => {
      const attachments = options?.attachments ?? []
      const mismoAttachments = attachments.filter(isMismoAttachment)
      const paths = attachedMismoPaths(text, attachments)

      if (mismoAttachments.length > 0 && /\b(add|start|review|open|load|prep|prepare|import)\b/i.test(text)) {
        if (mismoAttachments.length !== 1 || paths.length !== 1) {
          notify({ kind: 'error', title: 'Could not review this loan file', message: 'Attach one MISMO XML from a local file, then ask Flo to add or review it.' })

          return true
        }

        try {
          const supportingPaths = attachments
            .filter(item => item.path && /\.(pdf|jpe?g|png)$/i.test(item.path))
            .map(item => item.path!)

          const result = await runFloLocalIntake(paths[0], supportingPaths)
          notify({ kind: 'success', title: 'Loan added to Pipeline', message: `Customer File created or updated. ${result.document_count} new document${result.document_count === 1 ? '' : 's'} imported; Malcolm’s local prep is saved.` })

          const accepted = await actions.onSubmit(intakeAcknowledgement(), {
            ...options,
            displayText: text,
            attachments: []
          })

          const sessionId = options?.storedSessionId ?? options?.sessionId ?? $selectedStoredSessionId.get()

          if (sessionId) {await bindFloSession(result.workspace_id, sessionId)}

          return accepted
        } catch (error) {
          notifyError(error, 'Local loan intake failed')

          return true
        }
      }

      let submittedText = text
      let submittedOptions = options
      const visibleText = options?.displayText ?? text
      const sessionForContext = options?.storedSessionId ?? options?.sessionId ?? $selectedStoredSessionId.get()
      const pendingWorkspaceId = peekPendingWorkspaceBinding()
      let alreadyBoundWorkspaceId: string | null = null

      // Slash commands are application commands rather than Flo turns. All
      // natural-language turns resolve a fresh file context before reaching
      // any provider adapter, so correctness does not depend on tool choice.
      if (visibleText.trim() && !/^\s*\//.test(visibleText)) {
        let context: Awaited<ReturnType<typeof resolveFloTurnContext>>

        try {
          context = await resolveFloTurnContext(sessionForContext, visibleText, { forceWorkspaceId: pendingWorkspaceId })
        } catch (error) {
          if (getActiveCustomerFile() || pendingWorkspaceId) {
            notifyError(error, 'Could not load the current Customer File')

            return true
          }

          // An unscoped general chat remains usable if the optional local
          // workspace resolver is temporarily unavailable.
          context = { status: 'not_found' as const }
        }

        if (context.status === 'unavailable') {
          notify({ kind: 'error', title: 'Customer File unavailable', message: context.message ?? 'Flo could not load this chat’s Customer File. Your message was not sent.' })

          return true
        }

        if (context.status === 'resolved' && context.workspace_id) {
          if (context.bound) {alreadyBoundWorkspaceId = context.workspace_id}

          if (!sessionForContext) {requestPendingWorkspaceBinding(context.workspace_id)}
          const contextBlock = context.context ?? ''
          submittedText = `${contextBlock}\n\nASHLEY'S CURRENT MESSAGE (answer this):\n${text}`
          submittedOptions = { ...options, displayText: visibleText }
        } else if (context.status === 'ambiguous') {
          const candidates = (context.candidates ?? []).map(row => `- ${row.display_name}${row.loan_number ? ` · Loan #${row.loan_number}` : ''}`).join('\n')
          submittedText = `The local Customer File resolver found multiple possible files for Ashley's request. Do not choose or reveal file-specific data yet. Ask Ashley which one she means, showing these choices:\n${candidates}\n\nASHLEY'S CURRENT MESSAGE:\n${text}`
          submittedOptions = { ...options, displayText: visibleText }
        }
      }

      const workspaceToBind = takePendingWorkspaceBinding()
      const accepted = await actions.onSubmit(submittedText, submittedOptions)
      const sessionAfterSend = options?.storedSessionId ?? options?.sessionId ?? $selectedStoredSessionId.get()

      if (workspaceToBind && sessionAfterSend && accepted !== false && workspaceToBind !== alreadyBoundWorkspaceId) {
        try {
          await bindFloSession(workspaceToBind, sessionAfterSend)
        } catch (error) {
          notifyError(error, 'Could not link this chat to the Customer File')
        }
      }

      return accepted
    },
    onThreadMessagesChange: (...args) => actions.onThreadMessagesChange(...args),
    onToggleSelectedPin: (...args) => actions.onToggleSelectedPin(...args),
    onTranscribeAudio: latestOptional(() => actions.onTranscribeAudio)
  }
}

export function latestSidebarActions(actions: SidebarActions): SidebarActions {
  return {
    onArchiveSession: (...args) => actions.onArchiveSession(...args),
    onBranchSession: (...args) => actions.onBranchSession(...args),
    onDeleteSession: (...args) => actions.onDeleteSession(...args),
    onLoadMoreMessaging: latestOptional(() => actions.onLoadMoreMessaging),
    onLoadMoreSessions: (...args) => actions.onLoadMoreSessions(...args),
    onManageCronJob: (...args) => actions.onManageCronJob(...args),
    onNavigate: (...args) => actions.onNavigate(...args),
    onNewSessionInWorkspace: (...args) => actions.onNewSessionInWorkspace(...args),
    onNewSessionSplit: (...args) => actions.onNewSessionSplit(...args),
    onResumeSession: (...args) => actions.onResumeSession(...args),
    onTriggerCronJob: (...args) => actions.onTriggerCronJob(...args)
  }
}
