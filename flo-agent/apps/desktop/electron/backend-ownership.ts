export interface BackendIdentity {
  nonce: string
  pid: number
  profile: string
  startMarker: string
}

export interface BackendOwnershipEntry extends BackendIdentity {
  command?: string
  /** PID of the Electron parent that spawned this backend, when known. */
  parentPid?: number
  /** Start marker of that parent, so a reused PID is not mistaken for it. */
  parentStartMarker?: string
}

export interface BackendOwnershipStore {
  read: () => string | null
  write: (contents: string) => void
  /** Move an unreadable ownership file aside (e.g. rename to `.corrupt`) so
   *  its contents survive for inspection instead of being rewritten away.
   *  Optional: stores that can't quarantine simply skip the sweep. */
  quarantine?: () => void
}

export interface BackendOwnershipDeps {
  matchesIdentity: (identity: BackendIdentity) => Promise<boolean | undefined>
  /** True when the recorded parent is still running; undefined when unknown. */
  matchesParent: (entry: BackendOwnershipEntry) => Promise<boolean | undefined>
  stop: (identity: BackendIdentity) => Promise<void> | void
  store: BackendOwnershipStore
}

export interface BackendClaim extends BackendIdentity {
  command?: string
  parentPid?: number
  parentStartMarker?: string
}

const REAP_PROBE_CONCURRENCY = 8

async function mapConcurrent<T, R>(items: T[], limit: number, work: (item: T) => Promise<R>): Promise<R[]> {
  const results = new Array<R>(items.length)
  let nextIndex = 0
  const workerCount = Math.min(items.length, Math.max(1, limit))

  await Promise.all(
    Array.from({ length: workerCount }, async () => {
      while (true) {
        const index = nextIndex++

        if (index >= items.length) {
          return
        }

        results[index] = await work(items[index])
      }
    })
  )

  return results
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function isCompleteIdentity(value: unknown): value is BackendIdentity {
  if (!value || typeof value !== 'object') {
    return false
  }

  const candidate = value as Partial<BackendIdentity>

  return (
    Number.isInteger(candidate.pid) &&
    Number(candidate.pid) > 0 &&
    isNonEmptyString(candidate.startMarker) &&
    isNonEmptyString(candidate.nonce) &&
    isNonEmptyString(candidate.profile)
  )
}

function identitiesMatch(left: BackendIdentity, right: BackendIdentity): boolean {
  return (
    left.pid === right.pid &&
    left.startMarker === right.startMarker &&
    left.nonce === right.nonce &&
    left.profile === right.profile
  )
}

export function parseBackendOwnership(contents: unknown): BackendOwnershipEntry[] {
  return parseBackendOwnershipDetailed(contents).entries
}

/** Parse result that distinguishes "empty/valid" from "unreadable". A corrupt
 *  ownership file must NOT read as an empty roster: `reapOrphans` rewrites the
 *  file with its survivors, so treating garbage as `[]` permanently erased the
 *  records of still-running backends — the exact shape of the #89298 report
 *  (ownership file gone, 28 leaked serve processes nothing will ever reap). */
export function parseBackendOwnershipDetailed(contents: unknown): {
  corrupt: boolean
  entries: BackendOwnershipEntry[]
} {
  const text = String(contents ?? '')

  if (!text.trim()) {
    return { corrupt: false, entries: [] }
  }

  let parsed: unknown

  try {
    parsed = JSON.parse(text)
  } catch {
    return { corrupt: true, entries: [] }
  }

  const values = Array.isArray(parsed)
    ? parsed
    : parsed && typeof parsed === 'object' && Array.isArray((parsed as { backends?: unknown }).backends)
      ? (parsed as { backends: unknown[] }).backends
      : []

  const entries: BackendOwnershipEntry[] = []

  for (const value of values) {
    if (!isCompleteIdentity(value)) {
      continue
    }

    const candidate = value as BackendOwnershipEntry

    const entry: BackendOwnershipEntry = {
      nonce: candidate.nonce,
      pid: candidate.pid,
      profile: candidate.profile,
      startMarker: candidate.startMarker
    }

    if (typeof candidate.command === 'string') {
      entry.command = candidate.command
    }

    if (Number.isInteger(candidate.parentPid) && Number(candidate.parentPid) > 0) {
      entry.parentPid = candidate.parentPid
    }

    if (isNonEmptyString(candidate.parentStartMarker)) {
      entry.parentStartMarker = candidate.parentStartMarker
    }

    if (!entries.some(existing => identitiesMatch(existing, entry))) {
      entries.push(entry)
    }
  }

  return { corrupt: false, entries }
}

export function serializeBackendOwnership(entries: BackendOwnershipEntry[]): string {
  return `${JSON.stringify({ backends: entries }, null, 2)}\n`
}

/**
 * Persistent ownership for local backend roots.
 *
 * Claiming is asynchronous so a failed persistence transaction can await child
 * cleanup before reporting failure to the caller.
 */
export function createBackendOwnership(deps: BackendOwnershipDeps) {
  const readDetailed = () => parseBackendOwnershipDetailed(deps.store.read())
  const read = () => readDetailed().entries
  const write = (entries: BackendOwnershipEntry[]) => deps.store.write(serializeBackendOwnership(entries))

  return {
    async claim(claim: BackendClaim): Promise<BackendOwnershipEntry> {
      if (!isCompleteIdentity(claim)) {
        throw new Error('Cannot own a backend without a complete process identity.')
      }

      const entry: BackendOwnershipEntry = {
        nonce: claim.nonce,
        pid: claim.pid,
        profile: claim.profile,
        startMarker: claim.startMarker
      }

      if (typeof claim.command === 'string') {
        entry.command = claim.command
      }

      if (Number.isInteger(claim.parentPid) && Number(claim.parentPid) > 0) {
        entry.parentPid = claim.parentPid
      }

      if (isNonEmptyString(claim.parentStartMarker)) {
        entry.parentStartMarker = claim.parentStartMarker
      }

      try {
        const entries = read().filter(candidate => candidate.pid !== entry.pid)
        write([...entries, entry])
      } catch (error) {
        try {
          await deps.stop(entry)
        } catch {
          // Persistence remains the claim failure even if cleanup also fails.
        }

        throw error
      }

      return entry
    },

    release(identity: BackendIdentity): void {
      if (!isCompleteIdentity(identity)) {
        throw new Error('Cannot release a backend without a complete process identity.')
      }

      const entries = read()
      const next = entries.filter(entry => !identitiesMatch(entry, identity))

      if (next.length !== entries.length) {
        write(next)
      }
    },

    async reapOrphans(): Promise<number[]> {
      const { corrupt, entries } = readDetailed()

      // An unreadable ownership file yields zero parsed entries — rewriting
      // survivors ([]) here would DESTROY the only record of any backends the
      // corrupt file described, guaranteeing they leak forever (#89298).
      // Preserve the evidence for inspection and skip the sweep.
      if (corrupt) {
        try {
          deps.store.quarantine?.()
        } catch {
          // Quarantine is best-effort; the important part is not rewriting.
        }

        return []
      }

      // Most records belong to the same few Electron launches. Probe each
      // parent identity once instead of spawning a PowerShell process for
      // every backend record (Windows start-marker probes are comparatively
      // expensive). Run independent probes with a small concurrency bound so
      // a large stale ownership file cannot exceed the renderer's cold-boot
      // budget while still avoiding an unbounded process storm.
      const parentKey = (entry: BackendOwnershipEntry) =>
        Number.isInteger(entry.parentPid) && isNonEmptyString(entry.parentStartMarker)
          ? `${entry.parentPid}\u0000${entry.parentStartMarker}`
          : null
      const uniqueParents = new Map<string, BackendOwnershipEntry>()

      for (const entry of entries) {
        const key = parentKey(entry)

        if (key !== null && !uniqueParents.has(key)) {
          uniqueParents.set(key, entry)
        }
      }

      const parentProbeResults = await mapConcurrent(
        [...uniqueParents.entries()],
        REAP_PROBE_CONCURRENCY,
        async ([key, entry]) => {
          try {
            return { key, ok: true as const, alive: await deps.matchesParent(entry) }
          } catch {
            return { key, ok: false as const, alive: undefined }
          }
        }
      )
      const parentState = new Map(parentProbeResults.map(result => [result.key, result]))
      const survivors: BackendOwnershipEntry[] = []
      const candidates: BackendOwnershipEntry[] = []

      for (const entry of entries) {
        const key = parentKey(entry)
        const parent = key === null ? null : parentState.get(key)

        if (parent?.ok === false || parent?.alive === true) {
          // A failed parent probe is uncertain, and a live parent definitively
          // owns this backend. In either case retain without probing the child.
          survivors.push(entry)
        } else {
          // A missing parent marker (legacy entries) keeps the previous
          // identity-only behavior; a confirmed-dead parent is eligible for
          // exact child identity validation below.
          candidates.push(entry)
        }
      }

      const reapResults = await mapConcurrent(candidates, REAP_PROBE_CONCURRENCY, async entry => {
        let matches: boolean | undefined

        try {
          matches = await deps.matchesIdentity(entry)
        } catch {
          return { entry, reaped: false, keep: true }
        }

        if (matches === false) {
          return { entry, reaped: false, keep: false }
        }

        if (matches !== true) {
          return { entry, reaped: false, keep: true }
        }

        try {
          await deps.stop(entry)

          return { entry, reaped: true, keep: false }
        } catch {
          // Preserve failed ownership so a later launch can retry.
          return { entry, reaped: false, keep: true }
        }
      })
      const reaped: number[] = []

      for (const result of reapResults) {
        if (result.keep) {
          survivors.push(result.entry)
        } else if (result.reaped) {
          reaped.push(result.entry.pid)
        }
      }

      write(survivors)

      return reaped
    },

    clear(): void {
      write([])
    }
  }
}

export function backendCommandMatches(command: unknown): boolean {
  return /(?:^|[\s/\\"])(?:hermes(?:\.exe)?|hermes_cli\.main|hermes_cli[/\\]main\.py)"?(?:\s+(?:--profile|-p)\s+\S+)?\s+(?:serve|dashboard)(?:\s|$)/i.test(
    String(command ?? '')
  )
}

/** Coordinates all quit paths so asynchronous backend teardown runs once. */
export function createBackendShutdownCoordinator(teardown: () => Promise<void> | void) {
  let completion: Promise<void> | undefined

  return {
    run(): Promise<void> {
      if (!completion) {
        completion = Promise.resolve().then(teardown)
      }

      return completion
    },
    hasStarted(): boolean {
      return completion !== undefined
    }
  }
}
