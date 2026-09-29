import type { PluginRestOptions } from '@hermes/plugin-sdk'

export type FloActionResult = {
  action: string
  message: string
  [key: string]: unknown
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
