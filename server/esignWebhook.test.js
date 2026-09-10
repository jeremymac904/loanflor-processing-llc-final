import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import express from 'express';

import { createEsignWebhookRouter, dedupKey, extractEnvelopeId } from './routes/esignWebhook.js';
import { createEsignWebhookStore } from './services/esignWebhookStore.js';

const quiet = { info() {}, error() {} };
const SECRET = 'unit-test-webhook-secret-0123456789';

async function withApp(run, { fetchImpl } = {}) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-esign-'));
  const store = createEsignWebhookStore(path.join(tmp, 'seen.json'));
  const calls = [];
  const app = express();
  app.use('/api', createEsignWebhookRouter({
    store, secret: SECRET, env: { FLO_INTAKE_URL: 'http://127.0.0.1:9', FLO_INTAKE_TOKEN: 'flo-token-0123456789abcdef' },
    fetchImpl: fetchImpl || (async (url, opts) => { calls.push({ url, body: JSON.parse(opts.body) }); return { ok: true }; }),
    log: quiet,
  }));
  const server = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const post = (body, headers = {}) => fetch(`${base}/api/esign-webhook`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
  try {
    await run({ post, calls, store });
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

test('extractEnvelopeId / dedupKey read only what we trust from a webhook body', () => {
  const body = { event: 'DOCUMENT_COMPLETED', payload: { envelopeId: 'envelope_abc123', status: 'COMPLETED', completedAt: '2026-09-10T00:00:00Z', downloadUrl: 'https://evil.example/steal.pdf' } };
  assert.equal(extractEnvelopeId(body), 'envelope_abc123');
  assert.equal(dedupKey(body), 'DOCUMENT_COMPLETED:envelope_abc123:2026-09-10T00:00:00Z');
  // the extractor never returns anything from a 'downloadUrl'-shaped field, and there is no code path anywhere that reads one
  assert.equal(JSON.stringify({ id: extractEnvelopeId(body) }).includes('evil.example'), false);
});

test('a request without a valid X-Documenso-Secret is rejected before anything else runs', async () => {
  await withApp(async ({ post, calls }) => {
    const missing = await post({ event: 'DOCUMENT_COMPLETED', payload: { envelopeId: 'envelope_x' } });
    assert.equal(missing.status, 401);
    const wrong = await post({ event: 'DOCUMENT_COMPLETED', payload: { envelopeId: 'envelope_x' } }, { 'X-Documenso-Secret': 'not-it' });
    assert.equal(wrong.status, 401);
    assert.equal(calls.length, 0); // never forwarded to Flo
  });
});

test('a verified webhook forwards only the envelope id to Flo, nothing else from the payload', async () => {
  await withApp(async ({ post, calls }) => {
    const res = await post(
      { event: 'DOCUMENT_COMPLETED', payload: { envelopeId: 'envelope_real1', status: 'COMPLETED', completedAt: '2026-09-10T00:00:00Z', signingUrl: 'https://app.documenso.com/sign/x' } },
      { 'X-Documenso-Secret': SECRET },
    );
    assert.equal(res.status, 200);
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0].body, { envelopeId: 'envelope_real1' }); // status/signingUrl never forwarded
    assert.ok(calls[0].url.endsWith('/intake/esign-webhook'));
  });
});

test('the identical event is deduplicated (retried delivery, or re-delivery of the same notification)', async () => {
  await withApp(async ({ post, calls }) => {
    const body = { event: 'DOCUMENT_SIGNED', payload: { envelopeId: 'envelope_dup1', updatedAt: '2026-09-10T01:00:00Z' } };
    const first = await post(body, { 'X-Documenso-Secret': SECRET });
    const second = await post(body, { 'X-Documenso-Secret': SECRET }); // Documenso's own at-least-once redelivery
    assert.equal(first.status, 200);
    assert.equal((await first.json()).duplicate, undefined);
    assert.equal(second.status, 200);
    assert.equal((await second.json()).duplicate, true);
    assert.equal(calls.length, 1); // forwarded to Flo exactly once
  });
});

test('out-of-order delivery (OPENED after COMPLETED) is harmless: each is just a hint to re-check', async () => {
  await withApp(async ({ post, calls }) => {
    await post({ event: 'DOCUMENT_COMPLETED', payload: { envelopeId: 'envelope_ooo', completedAt: '2026-09-10T02:00:00Z' } }, { 'X-Documenso-Secret': SECRET });
    await post({ event: 'DOCUMENT_OPENED', payload: { envelopeId: 'envelope_ooo', updatedAt: '2026-09-10T01:00:00Z' } }, { 'X-Documenso-Secret': SECRET });
    assert.equal(calls.length, 2);
    assert.ok(calls.every((c) => Object.keys(c.body).length === 1 && c.body.envelopeId === 'envelope_ooo'));
  });
});

test('a missing envelope id is refused before any forward is attempted', async () => {
  await withApp(async ({ post, calls }) => {
    const bad = await post({ event: 'DOCUMENT_COMPLETED', payload: {} }, { 'X-Documenso-Secret': SECRET });
    assert.equal(bad.status, 400);
    assert.equal(calls.length, 0);
  });
});

test('Flo being unreachable does not fail the webhook response (its own catch-up sweep is the safety net)', async () => {
  await withApp(async ({ post }) => {
    const res = await post({ event: 'DOCUMENT_COMPLETED', payload: { envelopeId: 'envelope_unreachable' } }, { 'X-Documenso-Secret': SECRET });
    assert.equal(res.status, 200);
  }, { fetchImpl: async () => { throw new Error('ECONNREFUSED'); } });
});
