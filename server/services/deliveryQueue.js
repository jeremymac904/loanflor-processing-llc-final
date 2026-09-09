// Server-side retry for submissions Flo could not receive at submit time.
//
// The Loan Officer already got "Your submission was received"; this worker keeps
// trying in the background with exponential backoff (1 min → 15 min cap) until
// the intake accepts it. Attempts and errors are recorded on the submission
// record; logs carry ids and statuses only, never the payload.

import { deliverToFlo } from './floIntake.js';
import { appendSubmissionSummary } from './googleSheets.js';

const BASE_DELAY_MS = 60_000;
const MAX_DELAY_MS = 15 * 60_000;

export function backoffMs(attempts) {
  return Math.min(MAX_DELAY_MS, BASE_DELAY_MS * 2 ** Math.max(0, attempts - 1));
}

/** Try to deliver one record now; updates the store and returns the new record. */
export async function attemptDelivery(store, record, { deliver = deliverToFlo, now = () => new Date(), log = console } = {}) {
  const attempts = (record.deliveryAttempts || 0) + 1;
  const outcome = await deliver(record.payload);
  if (outcome.ok) {
    const next = store.update(record.submissionId, {
      status: 'delivered',
      deliveryAttempts: attempts,
      lastDeliveryError: null,
      nextAttemptAt: null,
      delivered: { at: now().toISOString(), workspaceId: outcome.result?.workspaceId || null, duplicate: Boolean(outcome.result?.duplicate) },
    });
    log.info?.(`[loan-submissions] ${record.submissionId} delivered to Flo (attempt ${attempts})`);
    // Best-effort summary row in the existing Google Sheet (no borrower payload).
    appendSubmissionSummary(next).catch(() => undefined);
    return next;
  }
  const next = store.update(record.submissionId, {
    status: outcome.retryable ? 'pending_delivery' : 'delivery_failed',
    deliveryAttempts: attempts,
    lastDeliveryError: String(outcome.error || 'unknown').slice(0, 300),
    nextAttemptAt: outcome.retryable ? new Date(now().getTime() + backoffMs(attempts)).toISOString() : null,
  });
  log.warn?.(`[loan-submissions] ${record.submissionId} not delivered (attempt ${attempts}): ${next.lastDeliveryError}`);
  return next;
}

export async function retryPending(store, opts = {}) {
  const now = opts.now ? opts.now() : new Date();
  const due = store.pending().filter((r) => !r.nextAttemptAt || Date.parse(r.nextAttemptAt) <= now.getTime());
  const results = [];
  for (const record of due) results.push(await attemptDelivery(store, record, opts));
  return results;
}

export function startDeliveryWorker(store, { intervalMs = 60_000, ...opts } = {}) {
  const timer = setInterval(() => {
    retryPending(store, opts).catch((error) => (opts.log || console).error?.(`[loan-submissions] retry worker error: ${error.message}`));
  }, intervalMs);
  timer.unref?.();
  return () => clearInterval(timer);
}
