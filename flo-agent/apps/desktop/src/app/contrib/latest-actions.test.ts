import { afterEach, describe, expect, it, vi } from 'vitest'

import { bindFloActions, setActiveCustomerFile } from '@/plugins/flo/actions-api'
import { $selectedStoredSessionId } from '@/store/session'

import type { SidebarNavItem } from '../types'

import { latestChatActions, latestSidebarActions } from './latest-actions'
import type { ChatActions, SidebarActions } from './types'

afterEach(() => {
  setActiveCustomerFile(null)
  $selectedStoredSessionId.set(null)
})

function makeChatActions(): ChatActions {
  return {
    onAddContextRef: vi.fn(),
    onAddUrl: vi.fn(),
    onAttachDroppedItems: vi.fn(),
    onAttachImageBlob: vi.fn(),
    onBranchInNewChat: vi.fn(),
    onCancel: vi.fn(),
    onDeleteSelectedSession: vi.fn(),
    onDismissError: vi.fn(),
    onEdit: vi.fn(),
    onPasteClipboardImage: vi.fn(),
    onPickFiles: vi.fn(),
    onPickFolders: vi.fn(),
    onPickImages: vi.fn(),
    onReload: vi.fn(),
    onRemoveAttachment: vi.fn(),
    onRestoreToMessage: vi.fn(),
    onRetryResume: vi.fn(),
    onSteer: vi.fn(),
    onSubmit: vi.fn(),
    onThreadMessagesChange: vi.fn(),
    onToggleSelectedPin: vi.fn(),
    onTranscribeAudio: vi.fn()
  }
}

function makeSidebarActions(): SidebarActions {
  return {
    onArchiveSession: vi.fn(),
    onBranchSession: vi.fn(),
    onDeleteSession: vi.fn(),
    onLoadMoreMessaging: vi.fn(),
    onLoadMoreSessions: vi.fn(),
    onManageCronJob: vi.fn(),
    onNavigate: vi.fn(),
    onNewSessionInWorkspace: vi.fn(),
    onNewSessionSplit: vi.fn(),
    onResumeSession: vi.fn(),
    onTriggerCronJob: vi.fn()
  }
}

describe('latestActions adapters', () => {
  it('dereferences the latest steer handler from a stable actions object', async () => {
    const staleSteer = vi.fn(async () => false)
    const latestSteer = vi.fn(async () => true)
    const actions = makeChatActions()
    actions.onSteer = staleSteer
    const adapted = latestChatActions(actions)

    actions.onSteer = latestSteer

    await expect(adapted.onSteer('continue in selected session')).resolves.toBe(true)
    expect(staleSteer).not.toHaveBeenCalled()
    expect(latestSteer).toHaveBeenCalledWith('continue in selected session')
  })

  it('dereferences the latest sidebar handler from a stable actions object', () => {
    const staleNavigate = vi.fn()
    const latestNavigate = vi.fn()
    const item = { id: 'settings', icon: vi.fn(), label: 'Settings', route: '/settings' } satisfies SidebarNavItem
    const actions = makeSidebarActions()
    actions.onNavigate = staleNavigate
    const adapted = latestSidebarActions(actions)

    actions.onNavigate = latestNavigate
    adapted.onNavigate(item)

    expect(staleNavigate).not.toHaveBeenCalled()
    expect(latestNavigate).toHaveBeenCalledWith(item)
  })

  // An absent optional handler must stay absent through the adapter. Children
  // gate on PRESENCE, not just invocation: onDismissError renders the dismiss
  // button only when defined, onRestoreToMessage gates the restore-confirm
  // flow, and onTranscribeAudio gates voice recording. Wrapping an undefined
  // field in an arrow function makes it unconditionally truthy, which would
  // paint a dead dismiss button and let voice recording run with no
  // transcription backend.
  it('leaves absent optional handlers undefined instead of always-truthy wrappers', () => {
    const chat = makeChatActions()
    chat.onDismissError = undefined
    chat.onRestoreToMessage = undefined
    chat.onTranscribeAudio = undefined

    const adaptedChat = latestChatActions(chat)

    expect(adaptedChat.onDismissError).toBeUndefined()
    expect(adaptedChat.onRestoreToMessage).toBeUndefined()
    expect(adaptedChat.onTranscribeAudio).toBeUndefined()

    const sidebar = makeSidebarActions()
    sidebar.onLoadMoreMessaging = undefined

    const adaptedSidebar = latestSidebarActions(sidebar)

    expect(adaptedSidebar.onLoadMoreMessaging).toBeUndefined()
  })

  it('still late-binds a PRESENT optional handler to the latest closure', async () => {
    const staleTranscribe = vi.fn(async () => 'stale')
    const latestTranscribe = vi.fn(async () => 'latest')
    const actions = makeChatActions()
    actions.onTranscribeAudio = staleTranscribe

    const adapted = latestChatActions(actions)

    actions.onTranscribeAudio = latestTranscribe

    expect(adapted.onTranscribeAudio).toBeTypeOf('function')
    await expect(adapted.onTranscribeAudio!(new Blob())).resolves.toBe('latest')
    expect(staleTranscribe).not.toHaveBeenCalled()
  })

  it('imports an attached MISMO file locally before sending only a safe acknowledgement to Flo', async () => {
    const rest = vi.fn(async (path: string) => {
      if (path === '/intake/local') {return { workspace_id: 'loan_synthetic', display_name: 'Smith', created: true, document_count: 1, unsupported: [] }}

      return { workspace_id: 'loan_synthetic', session_id: 'session-synthetic' }
    })

    const dispose = bindFloActions(rest as never)
    const actions = makeChatActions()
    actions.onSubmit = vi.fn(async () => true)
    $selectedStoredSessionId.set('session-synthetic')
    const adapted = latestChatActions(actions)
    const attachment = { id: 'mismo', kind: 'file' as const, label: 'Smith_3.4.xml', path: 'C:/Synthetic/Smith_3.4.xml' }

    await expect(adapted.onSubmit('Add this loan to the pipeline.', { attachments: [attachment] })).resolves.toBe(true)

    expect(rest).toHaveBeenNthCalledWith(1, '/intake/local', expect.objectContaining({
      method: 'POST', body: { path: attachment.path, additional_paths: [] }
    }))
    expect(actions.onSubmit).toHaveBeenCalledWith(expect.stringContaining('local loan intake is complete'), {
      attachments: [], displayText: 'Add this loan to the pipeline.'
    })
    expect(rest).toHaveBeenNthCalledWith(2, '/intake/bind-session', {
      method: 'POST', body: { workspace_id: 'loan_synthetic', session_id: 'session-synthetic' }
    })

    dispose()
    $selectedStoredSessionId.set(null)
  })

  it('injects freshly resolved active Customer File context before a normal Flo provider turn', async () => {
    const rest = vi.fn(async (path: string) => {
      if (path === '/context/turn') {
        return {
          status: 'resolved', workspace_id: 'loan-jason-synthetic', display_name: 'Jason Lathrop', bound: true,
          context: 'CURRENT CUSTOMER FILE DATA: {"contacts":[{"role":"borrower","phone":"555-0101"}],"mismo":{"loan":{"total_loan_amount":185500}},"stored_documents":[{"original_filename":"Jason_3.4.xml"}]}'
        }
      }

      return {}
    })

    const dispose = bindFloActions(rest as never)
    const actions = makeChatActions()
    const submit = vi.fn(async (..._args: Parameters<ChatActions['onSubmit']>) => true)
    actions.onSubmit = submit
    $selectedStoredSessionId.set('session-jason')
    setActiveCustomerFile('loan-jason-synthetic')

    const adapted = latestChatActions(actions)
    await expect(adapted.onSubmit("What's Jason's phone number?", { storedSessionId: 'session-jason' })).resolves.toBe(true)

    expect(rest).toHaveBeenCalledWith('/context/turn', expect.objectContaining({
      method: 'POST', body: expect.objectContaining({
        session_id: 'session-jason', active_workspace_id: 'loan-jason-synthetic',
        query: "What's Jason's phone number?"
      })
    }))
    expect(submit).toHaveBeenCalledWith(expect.stringContaining('"phone":"555-0101"'), {
      storedSessionId: 'session-jason', displayText: "What's Jason's phone number?"
    })
    expect(submit.mock.calls[0][0]).toContain('ASHLEY\'S CURRENT MESSAGE (answer this):')
    expect(submit.mock.calls[0][0]).toContain('Jason_3.4.xml')

    dispose()
    setActiveCustomerFile(null)
    $selectedStoredSessionId.set(null)
  })

  it('keeps Customer File context independent of the selected model/profile adapter', async () => {
    const rest = vi.fn(async () => ({
      status: 'resolved', workspace_id: 'loan-jason-synthetic', display_name: 'Jason Lathrop', bound: true,
      context: 'CURRENT CUSTOMER FILE DATA: {"contacts":[{"role":"borrower","phone":"555-0101"}]}'
    }))

    const dispose = bindFloActions(rest as never)
    const actions = makeChatActions()
    actions.onSubmit = vi.fn(async () => true)
    setActiveCustomerFile('loan-jason-synthetic')

    await latestChatActions(actions).onSubmit('Hello Flo')

    expect(rest).toHaveBeenCalledWith('/context/turn', expect.objectContaining({
      method: 'POST', body: expect.objectContaining({ active_workspace_id: 'loan-jason-synthetic' })
    }))
    expect(actions.onSubmit).toHaveBeenCalledWith(expect.stringContaining('"phone":"555-0101"'), {
      displayText: 'Hello Flo'
    })

    dispose()
    setActiveCustomerFile(null)
  })
})
