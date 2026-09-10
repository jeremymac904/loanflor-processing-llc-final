// Inbound Documenso webhook -> forwarded (envelope id only) to Flo's private intake server.
//
// Documenso's own docs (see FLO_ESIGN.md) describe shared-secret auth via a plain `X-Documenso-Secret`
// header — not an HMAC signature — so verification here is a constant-time string compare against a
// required, non-empty configured secret. The webhook payload is never trusted for anything beyond "which
// envelope changed": no download URL, no loan mapping, no status. Flo re-fetches the authoritative status
// (and, once signed, the completed file) directly from the Documenso API. This keeps Documenso's API
// credentials off the public website entirely — only the webhook secret (to verify Documenso is really
// the sender) and the existing FLO_INTAKE_TOKEN (to reach Flo privately) live here.

import crypto from 'node:crypto';
import express, { Router } from 'express';

import { createRateLimiter } from './loanSubmissions.js';

const DEFAULT_TIMEOUT_MS = 10_000;

function secretOk(req, secret) {
  const presented = req.get('x-documenso-secret') || '';
  if (!secret || !presented || presented.length !== secret.length) return false;
  return crypto.timingSafeEqual(Buffer.from(presented), Buffer.from(secret));
}

/** Pull only the envelope id out of a Documenso webhook body; every other field is ignored. */
export function extractEnvelopeId(body) {
  const payload = (body && typeof body === 'object' && body.payload) || body || {};
  const id = payload.envelopeId || payload.id || (body && body.envelopeId);
  return typeof id === 'string' && id.trim() ? id.trim() : null;
}

/** Best-effort dedup key: same event + same envelope + same provider timestamp is the same notification. */
export function dedupKey(body) {
  const payload = (body && typeof body === 'object' && body.payload) || {};
  const event = (body && body.event) || 'unknown';
  const envelopeId = extractEnvelopeId(body) || 'unknown';
  const stamp = payload.updatedAt || payload.completedAt || payload.signedAt || '';
  return `${event}:${envelopeId}:${stamp}`;
}

export function createEsignWebhookRouter({ store, secret = process.env.DOCUMENSO_WEBHOOK_SECRET, env = process.env, fetchImpl = globalThis.fetch,
  timeoutMs = DEFAULT_TIMEOUT_MS, rateLimiter = createRateLimiter({ max: 600 }), log = console } = {}) {
  const router = Router();
  router.post('/esign-webhook', rateLimiter, express.json({ limit: '256kb' }), async (req, res) => {
    if (!secretOk(req, secret)) {
      log.error?.('[esign-webhook] rejected: missing/invalid X-Documenso-Secret');
      return res.status(401).json({ ok: false, error: 'unauthorized' });
    }
    const envelopeId = extractEnvelopeId(req.body);
    if (!envelopeId) {
      return res.status(400).json({ ok: false, error: 'no envelope id in payload' });
    }
    const key = dedupKey(req.body);
    if (store.seen(key)) {
      return res.status(200).json({ ok: true, duplicate: true });
    }
    store.markSeen(key);
    log.info?.(`[esign-webhook] ${req.body?.event || 'event'} for envelope ${envelopeId}`);
    // Forward only the envelope id, over the existing private Flo channel. Best-effort: if Flo is
    // unreachable right now, its own periodic catch-up sweep will pick this envelope up regardless.
    if (env.FLO_INTAKE_URL && env.FLO_INTAKE_TOKEN) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        await fetchImpl(`${env.FLO_INTAKE_URL.replace(/\/+$/, '')}/intake/esign-webhook`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${env.FLO_INTAKE_TOKEN}` },
          body: JSON.stringify({ envelopeId }),
          signal: controller.signal,
        });
      } catch (error) {
        log.error?.(`[esign-webhook] forward to Flo failed (non-fatal; catch-up sweep will retry): ${error.name}`);
      } finally {
        clearTimeout(timer);
      }
    } else {
      log.error?.('[esign-webhook] FLO_INTAKE_URL/TOKEN not configured; relying on Flo\'s catch-up sweep alone');
    }
    return res.status(200).json({ ok: true });
  });
  return router;
}
