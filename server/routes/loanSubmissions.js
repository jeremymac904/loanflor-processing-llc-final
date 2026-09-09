// POST /api/loan-submissions — the public security boundary for loan intake.
//
//   browser → this route → (validate, dedupe, persist) → Flo intake connector → Flo
//
// - server-side validation with the shared contract (same rules as the form)
// - honeypot + origin check + per-IP rate limit
// - idempotent on submissionId: a double click or a retried request returns the
//   same record and never creates a second loan in Flo
// - if Flo is unreachable the record is persisted as pending_delivery and the
//   Loan Officer still gets "Your submission was received"
// - logs carry the submission id and status only

import { Router } from 'express';

import { documentRefsFromRecords, toPayload, validateSubmission } from '../../shared/loanSubmission.js';
import { attemptDelivery } from '../services/deliveryQueue.js';
import { deliverToFlo } from '../services/floIntake.js';
import { publicStatus } from '../services/submissionStore.js';

const ID_RE = /^sub_[0-9a-f]{24}$/;

export function createRateLimiter({ windowMs = 60 * 60_000, max = 12, now = () => Date.now() } = {}) {
  const hits = new Map();
  return (req, res, next) => {
    const key = req.ip || req.socket?.remoteAddress || 'unknown';
    const t = now();
    const entry = hits.get(key) || { start: t, count: 0 };
    if (t - entry.start > windowMs) {
      entry.start = t;
      entry.count = 0;
    }
    entry.count += 1;
    hits.set(key, entry);
    if (hits.size > 5000) hits.clear();
    if (entry.count > max) return res.status(429).json({ ok: false, error: 'Too many submissions from this network. Please wait a while and try again.' });
    return next();
  };
}

export function originAllowed(req, allowed) {
  if (!allowed || allowed.length === 0) return true;
  const origin = req.get('origin') || (req.get('referer') ? new URL(req.get('referer')).origin : '');
  return allowed.includes(origin);
}

export function createLoanSubmissionsRouter({ store, documents = null, publicApiBase = process.env.PUBLIC_API_BASE_URL || '', deliver = deliverToFlo, allowedOrigins = [], rateLimiter = createRateLimiter(), log = console } = {}) {
  const router = Router();

  router.post('/loan-submissions', rateLimiter, async (req, res) => {
    const body = req.body;
    if (!originAllowed(req, allowedOrigins)) return res.status(403).json({ ok: false, error: 'Submission origin not allowed' });
    if (!body || typeof body !== 'object' || Array.isArray(body)) return res.status(400).json({ ok: false, error: 'Invalid submission' });
    // Honeypot: a filled hidden field means a bot. Answer like a success and drop it.
    if (typeof body.website === 'string' && body.website.trim()) return res.json({ ok: true, status: 'received', submissionId: body.submissionId || null });

    const { errors } = validateSubmission(body);
    if (Object.keys(errors).length > 0) {
      return res.status(400).json({ ok: false, error: 'Please review the highlighted fields', fields: errors });
    }
    if (!ID_RE.test(String(body.submissionId))) return res.status(400).json({ ok: false, error: 'Invalid submission id' });

    let payload;
    try {
      payload = toPayload(body, { submittedAt: new Date().toISOString() });
    } catch {
      return res.status(400).json({ ok: false, error: 'Invalid submission' });
    }

    // Documents: the server's own records are authoritative (uploaded through PUT .../documents).
    if (documents) {
      const base = (publicApiBase || `${req.protocol}://${req.get('host')}`).replace(/\/+$/, '');
      const records = documents.list(payload.submissionId).filter((d) => d.status !== 'removed');
      payload.documentRefs = documentRefsFromRecords(records, { fetchUrlFor: (r) => `${base}/api/internal/documents/${r.submissionId}/${r.documentId}` });
    }

    const meta = {
      borrowerName: payload.borrowers[0]?.name || null,
      expectedClosingDate: payload.loan.expectedClosingDate,
      loanOfficer: payload.loanOfficer.name,
      documentsReceived: payload.documentRefs.filter((d) => d.status !== 'duplicate').length,
      ip: req.ip || null,
    };
    let record;
    let created;
    try {
      ({ record, created } = store.create(payload, meta));
    } catch (error) {
      log.error?.(`[loan-submissions] could not persist ${payload.submissionId}: ${error.message}`);
      return res.status(500).json({ ok: false, error: 'We could not save your submission. Please try again or call (904) 535-1902.' });
    }

    if (!created) {
      // Same submissionId again (double click, retry after timeout): one loan, one answer.
      log.info?.(`[loan-submissions] ${record.submissionId} duplicate request ignored (status ${record.status})`);
      return res.status(200).json({ ok: true, duplicate: true, ...publicStatus(record) });
    }

    log.info?.(`[loan-submissions] ${record.submissionId} received (${meta.documentsReceived} documents)`);
    documents?.markSubmitted?.(record.submissionId);
    const after = await attemptDelivery(store, record, { deliver, log });
    const status = after.status === 'delivered' ? 200 : 202;
    return res.status(status).json({ ok: true, ...publicStatus(after) });
  });

  router.get('/loan-submissions/:id', (req, res) => {
    if (!ID_RE.test(req.params.id)) return res.status(404).json({ ok: false, error: 'Not found' });
    const record = store.get(req.params.id);
    if (!record) return res.status(404).json({ ok: false, error: 'Not found' });
    return res.json({ ok: true, ...publicStatus(record) });
  });

  return router;
}
