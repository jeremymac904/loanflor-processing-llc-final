import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import express from 'express';

import { documentRefsFromRecords, submissionReference } from '../shared/loanSubmission.js';
import { createDocumentsRouter } from './routes/documents.js';
import { createLoanSubmissionsRouter } from './routes/loanSubmissions.js';
import { LocalDiskStorage, SupabaseStorage, assertSafeKey } from './services/documentStorage.js';
import { createDocumentStore, validateUpload } from './services/documentStore.js';
import { createSubmissionStore } from './services/submissionStore.js';
import { syntheticSubmission } from './synthetic.js';

const quiet = { info() {}, warn() {}, error() {} };
const TOKEN = 'unit-test-token-0123456789abcdef';

function pdf(text = 'Synthetic paystub') {
  return Buffer.from(`%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n% ${text}\n%%EOF\n`);
}

async function withApp(run) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'lf-docs-'));
  const submissions = createSubmissionStore(path.join(tmp, 'subs'));
  const store = createDocumentStore(path.join(tmp, 'meta'));
  const storage = new LocalDiskStorage(path.join(tmp, 'blobs'));
  const app = express();
  app.use(express.json({ limit: '512kb' }));
  app.use('/api', createLoanSubmissionsRouter({ store: submissions, documents: store, publicApiBase: 'https://lfprocessing.net', deliver: async () => ({ ok: true, result: { status: 201 } }), log: quiet }));
  app.use('/api', createDocumentsRouter({ store, storage, submissions, intakeToken: TOKEN, log: quiet }));
  const server = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const upload = (sid, q, body, headers = {}) =>
    fetch(`${base}/api/loan-submissions/${sid}/documents?${new URLSearchParams(q)}`, { method: 'PUT', headers: { 'Content-Type': 'application/octet-stream', ...headers }, body });
  try {
    await run({ base, upload, store, storage, submissions, tmp });
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

test('validateUpload enforces type, magic bytes, size, html and unsafe names', () => {
  assert.equal(validateUpload({ originalFilename: 'a.pdf', sizeBytes: 10, buffer: pdf() }).mimeType, 'application/pdf');
  assert.throws(() => validateUpload({ originalFilename: 'a.exe', sizeBytes: 10, buffer: pdf() }), /not accepted/);
  assert.throws(() => validateUpload({ originalFilename: 'a.pdf', sizeBytes: 10, buffer: Buffer.from('hello') }), /does not match/);
  assert.throws(() => validateUpload({ originalFilename: 'a.jpg', sizeBytes: 10, buffer: Buffer.from('<html><script>') }), /does not match|not accepted/);
  assert.throws(() => validateUpload({ originalFilename: 'ssn 123-45-6789.pdf', sizeBytes: 10, buffer: pdf() }), /SSN/);
  assert.throws(() => validateUpload({ originalFilename: 'acct 1234567890.pdf', sizeBytes: 10, buffer: pdf() }), /SSN or account/);
  assert.throws(() => validateUpload({ originalFilename: 'big.pdf', sizeBytes: 26 * 1024 * 1024, buffer: pdf() }), /25 MB/);
  assert.throws(() => assertSafeKey('../etc/passwd'));
  assert.throws(() => assertSafeKey('/abs/path.pdf'));
  assert.equal(assertSafeKey('submissions/sub_x/income/2026-09-09_paystub_01.pdf'), 'submissions/sub_x/income/2026-09-09_paystub_01.pdf');
  assert.equal(submissionReference('sub_0694e236a2c5d51a5fe30301'), 'LF-0694E236A2');
});

test('upload → clean key + display name, duplicate detection, list, remove, internal fetch with token', async () => {
  await withApp(async ({ upload, base, store, storage }) => {
    const sid = syntheticSubmission().submissionId;
    const a = await upload(sid, { category: 'income', subcategory: 'paystub', borrower: 'borrower', filename: 'scan0042.PDF' }, pdf('paystub one'));
    assert.equal(a.status, 201);
    const docA = (await a.json()).document;
    assert.equal(docA.displayName, `${new Date().toISOString().slice(0, 10)}_paystub_01.pdf`);
    assert.equal(docA.fileName, 'scan0042.PDF');
    assert.equal(docA.status, 'received');
    const recA = store.get(sid, docA.id);
    assert.equal(recA.storageKey, `submissions/${sid}/income/${docA.displayName}`);
    assert.ok(await storage.exists(recA.storageKey));
    // second paystub numbers _02; a bank statement lands under assets/
    const b = await (await upload(sid, { category: 'income', subcategory: 'paystub', filename: 'scan0043.pdf' }, pdf('paystub two'))).json();
    assert.equal(b.document.displayName.endsWith('_paystub_02.pdf'), true);
    const c = await (await upload(sid, { category: 'assets', subcategory: 'bank_statement', filename: 'stmt.pdf' }, pdf('bank'))).json();
    assert.ok(store.get(sid, c.document.id).storageKey.includes('/assets/'));
    // same bytes again → duplicate record, no second object
    const dup = await (await upload(sid, { category: 'income', subcategory: 'paystub', filename: 'scan0042 copy.pdf' }, pdf('paystub one'))).json();
    assert.equal(dup.document.status, 'duplicate');
    assert.equal(store.get(sid, dup.document.id).storageKey, recA.storageKey);
    assert.equal(store.get(sid, dup.document.id).duplicateOf, docA.id);
    // bad type refused, nothing stored
    assert.equal((await upload(sid, { category: 'other', filename: 'evil.html' }, Buffer.from('<html>'))).status, 415);
    assert.equal((await upload(sid, { category: 'nope', filename: 'x.pdf' }, pdf())).status, 400);
    // list + remove
    let list = (await (await fetch(`${base}/api/loan-submissions/${sid}/documents`)).json()).documents;
    assert.equal(list.length, 4);
    assert.equal((await fetch(`${base}/api/loan-submissions/${sid}/documents/${b.document.id}`, { method: 'DELETE' })).status, 200);
    list = (await (await fetch(`${base}/api/loan-submissions/${sid}/documents`)).json()).documents;
    assert.equal(list.length, 3);
    // internal fetch: token required, bytes + sha header
    assert.equal((await fetch(`${base}/api/internal/documents/${sid}/${docA.id}`)).status, 401);
    const got = await fetch(`${base}/api/internal/documents/${sid}/${docA.id}`, { headers: { Authorization: `Bearer ${TOKEN}` } });
    assert.equal(got.status, 200);
    const bytes = Buffer.from(await got.arrayBuffer());
    assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), got.headers.get('x-document-sha256'));
    assert.equal(bytes.toString(), pdf('paystub one').toString());
    // no raw content in a Supabase key path either
    const refs = documentRefsFromRecords(store.list(sid), { fetchUrlFor: (r) => `https://lfprocessing.net/api/internal/documents/${r.submissionId}/${r.documentId}` });
    assert.equal(refs.length, 3);
    assert.ok(refs.every((r) => r.fetchUrl.startsWith('https://lfprocessing.net/api/internal/documents/')));
    assert.ok(refs.every((r) => !('content' in r)));
  });
});

test('submitting attaches the server-side document records and blocks further uploads', async () => {
  await withApp(async ({ upload, base, submissions }) => {
    const s = syntheticSubmission();
    await upload(s.submissionId, { category: 'loan_application', filename: '1003.pdf' }, pdf('1003'));
    await upload(s.submissionId, { category: 'aus_findings', filename: 'du.pdf' }, pdf('du'));
    s.documents = [{ id: 'doc_ffffffffffffffffffffffff', category: 'other', fileName: 'ignored.pdf', sizeBytes: 1, contentType: 'application/pdf', status: 'received' }];
    const res = await fetch(`${base}/api/loan-submissions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(s) });
    const body = await res.json();
    assert.equal(res.status, 200);
    assert.equal(body.documentsReceived, 2);
    const record = submissions.get(s.submissionId);
    assert.equal(record.payload.documentRefs.length, 2);
    assert.equal(record.payload.documentRefs[0].category, 'loan_application');
    assert.ok(record.payload.documentRefs[0].fetchUrl.startsWith('https://lfprocessing.net/api/internal/documents/'));
    assert.equal(record.payload.documentRefs[0].uploadedBy, 'loan_officer');
    // after submit the upload door closes
    assert.equal((await upload(s.submissionId, { category: 'other', filename: 'late.pdf' }, pdf('late'))).status, 409);
  });
});

test('SupabaseStorage talks to the private bucket with the service key only', async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, method: init.method || 'GET', auth: init.headers.Authorization });
    if (init.method === 'POST' && url.includes('/object/sign/')) return { ok: true, status: 200, json: async () => ({ signedURL: '/object/sign/loan-documents/k?token=abc' }) };
    return { ok: true, status: 200, arrayBuffer: async () => new Uint8Array([1, 2, 3]).buffer };
  };
  const s = new SupabaseStorage({ url: 'https://proj.supabase.co', serviceKey: 'service-secret', bucket: 'loan-documents', fetchImpl });
  await s.put('submissions/sub_x/income/2026-09-09_paystub_01.pdf', Buffer.from('%PDF-'), 'application/pdf');
  assert.equal(calls[0].url, 'https://proj.supabase.co/storage/v1/object/loan-documents/submissions/sub_x/income/2026-09-09_paystub_01.pdf');
  assert.equal(calls[0].auth, 'Bearer service-secret');
  assert.equal((await s.get('submissions/sub_x/income/2026-09-09_paystub_01.pdf')).length, 3);
  assert.equal(await s.signedUrl('submissions/sub_x/income/2026-09-09_paystub_01.pdf', 60), 'https://proj.supabase.co/storage/v1/object/sign/loan-documents/k?token=abc');
  await assert.rejects(() => s.put('../escape.pdf', Buffer.from('x')), /unsafe/);
});
