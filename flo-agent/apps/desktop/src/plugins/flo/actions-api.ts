import type { PluginRestOptions } from '@hermes/plugin-sdk'

export type FloActionResult = {
  action: string
  message: string
  [key: string]: unknown
}

export type FloLocalIntakeResult = FloActionResult & {
  workspace_id: string
  display_name: string
  created: boolean
  document_count: number
  unsupported: string[]
  best_next_move?: string
}

type Rest = <T>(path: string, opts?: PluginRestOptions) => Promise<T>

let rest: Rest | null = null

export function bindFloActions(next: Rest): () => void {
  rest = next

  return () => {
    if (rest === next) {
      rest = null
    }
  }
}

export function runFloAction<T extends FloActionResult = FloActionResult>(
  action: string,
  body: Record<string, unknown>
): Promise<T> {
  if (!rest) {
    return Promise.reject(new Error('Flo action API is not ready'))
  }

  return rest<T>(`/actions/${encodeURIComponent(action)}`, { method: 'POST', body })
}

export function runFloLocalIntake(path: string, additionalPaths: string[] = [], sessionId?: string | null): Promise<FloLocalIntakeResult> {
  if (!rest) {
    return Promise.reject(new Error('Flo intake API is not ready'))
  }

  return rest<FloLocalIntakeResult>('/intake/local', {
    method: 'POST',
    body: { path, additional_paths: additionalPaths, ...(sessionId ? { session_id: sessionId } : {}) },
    timeoutMs: 180_000
  })
}

let pendingWorkspaceBinding: string | null = null

export function requestPendingWorkspaceBinding(workspaceId: string): void {
  pendingWorkspaceBinding = workspaceId
}

export function takePendingWorkspaceBinding(): string | null {
  const value = pendingWorkspaceBinding
  pendingWorkspaceBinding = null
  return value
}

export function bindFloSession(workspaceId: string, sessionId: string): Promise<unknown> {
  if (!rest) {
    return Promise.reject(new Error('Flo action API is not ready'))
  }

  return rest('/intake/bind-session', { method: 'POST', body: { workspace_id: workspaceId, session_id: sessionId } })
}
