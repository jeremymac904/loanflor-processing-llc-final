// Durable, file-based store for loan submissions.
//
// One JSON file per submission under SUBMISSIONS_DIR (default server/data/submissions,
// git-ignored). The file is the idempotency record AND the pending-delivery queue:
// a submission is never lost because Flo was unreachable — it sits here as
// `pending_delivery` until the retry worker delivers it.
//
// Status lifecycle (internal, never shown to the LO):
//   received -> delivered
//   received -> pending_delivery (Flo connector not configured) -> delivered
//   received -> failed_retrying (Flo unreachable / error, retried with backoff) -> delivered

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_DIR = path.resolve(HERE, '..', 'data', 'submissions');
const ID_RE = /^sub_[0-9a-f]{24}$/;

export function createSubmissionStore(dir = process.env.SUBMISSIONS_DIR || DEFAULT_DIR) {
  fs.mkdirSync(dir, { recursive: true });

  const fileFor = (id) => {
    if (!ID_RE.test(id)) throw new Error('invalid submission id');
    return path.join(dir, `${id}.json`);
  };

  const read = (id) => {
    try {
      return JSON.parse(fs.readFileSync(fileFor(id), 'utf8'));
    } catch (error) {
      if (error.code === 'ENOENT') return null;
      throw error;
    }
  };

  const write = (record) => {
    const file = fileFor(record.submissionId);
    const tmp = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(record, null, 2), { mode: 0o600 });
    fs.renameSync(tmp, file);
    return record;
  };

  return {
    dir,
    get: read,
    /** Create the record once; returns { record, created }. A repeat of the same id returns the existing record. */
    create(payload, meta = {}) {
      const existing = read(payload.submissionId);
      if (existing) return { record: existing, created: false };
      const now = new Date().toISOString();
      const record = {
        submissionId: payload.submissionId,
        status: 'received',
        receivedAt: now,
        updatedAt: now,
        deliveryAttempts: 0,
        lastDeliveryError: null,
        nextAttemptAt: null,
        delivered: null,
        meta,
        payload,
      };
      write(record);
      return { record, created: true };
    },
    update(id, patch) {
      const record = read(id);
      if (!record) return null;
      const next = { ...record, ...patch, updatedAt: new Date().toISOString() };
      write(next);
      return next;
    },
    pending() {
      return fs
        .readdirSync(dir)
        .filter((f) => f.endsWith('.json'))
        .map((f) => read(f.replace(/\.json$/, '')))
        .filter((r) => r && (r.status === 'pending_delivery' || r.status === 'failed_retrying'))
        .sort((a, b) => a.receivedAt.localeCompare(b.receivedAt));
    },
  };
}

/** What the API returns to the browser (never the payload, never internals). */
export function publicStatus(record) {
  return {
    submissionId: record.submissionId,
    status: record.status === 'delivered' ? 'delivered' : 'received',
    receivedAt: record.receivedAt,
    borrowerName: record.meta?.borrowerName || null,
    expectedClosingDate: record.meta?.expectedClosingDate || null,
  };
}
