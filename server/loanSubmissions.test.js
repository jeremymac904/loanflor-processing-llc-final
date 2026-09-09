import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import express from 'express';

import { findSensitiveStrings, toPayload, validateSubmission } from '../shared/loanSubmission.js';
import { createLoanSubmissionsRouter, createRateLimiter } from './routes/loanSubmissions.js';
import { attemptDelivery, backoffMs, retryPending } from './services/deliveryQueue.js';
import { deliverToFlo } from './services/floIntake.js';
import { createSubmissionStore } from './services/submissionStore.js';
import { syntheticSubmission } from './synthetic.js';

const quiet = { info() {}, warn() {}, error() {} };

function tmpStore() {
  return createSubmissionStore(fs.mkdtempSync(path.join(os.tmpdir(), 'lf-sub-')));
}

async function withApp({ deliver, store = tmpStore(), rateLimiter, allowedOrigins }, run) {
  const app = express();
  app.use(express.json({ limit: '512kb' }));
  app.use('/api', createLoanSubmissionsRouter({ store, deliver, log: quiet, rateLimiter, allowedOrigins }));
  const server = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const post = (body, headers = {}) => fetch(`${base}/api/loan-submissions`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
  const get = (id) => fetch(`${base}/api/loan-submissions/${id}`);
  try {
    await run({ post, get, store });
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

test('the synthetic submission validates and normalizes into the v1.0 payload', () => {
  const s = syntheticSubmission();
  const { errors, recommended } = validateSubmission(s);
  assert.deepEqual(errors, {});
  assert.ok(recommended.some((r) => r.path === 'documents'));
  const p = toPayload(s, { submittedAt: '2026-09-09T14:42:00.000Z' });
  assert.equal(p.schemaVersion, '1.0');
  assert.equal(p.source, 'lfprocessing.net');
  assert.equal(p.borrowers.length, 1);
  assert.equal(p.borrowers[0].phone, '(904) 555-0102');
  assert.equal(p.loan.loanAmount, 314000);
  assert.equal(p.loan.program, 'fha');
  assert.equal(p.fees.lenderBuyingOutFee, 'no');
  assert.equal(p.income[0].verified, false);
  assert.equal(p.agents.listing.name, 'Michael Capo (synthetic)');
  assert.equal(p.parties.nonBorrowingTitleParty.applies, false);
  assert.ok(!JSON.stringify(p).includes('On a primary refi'));
});

test('conditional requirements: co-borrower, title party, refinance hides agents, program-specific AUS', () => {
  const co = syntheticSubmission({ hasCoBorrower: 'yes' });
  assert.equal(validateSubmission(co).errors['coBorrower.name'], 'Co-borrower full name is required');
  co.coBorrower = { name: 'Sam Synthetic', email: 'sam@synthetic.test', phone: '9045550105' };
  co.income.push({ ...co.income[0], id: 'inc_2', borrower: 'co_borrower', incomeType: '1099', employerOrSource: 'Contract work' });
  assert.deepEqual(validateSubmission(co).errors, {});
  assert.equal(toPayload(co).borrowers.length, 2);

  const tp = syntheticSubmission({ parties: { nonBorrowingTitleParty: { applies: 'yes' } } });
  const e = validateSubmission(tp).errors;
  assert.ok(e['parties.nonBorrowingTitleParty.name']);
  assert.ok(e['parties.nonBorrowingTitleParty.willBeOnTitle']);

  const refi = syntheticSubmission({ loan: { transactionType: 'refinance_rate_term', refinanceType: 'fha_streamline' } });
  assert.deepEqual(validateSubmission(refi).errors, {});
  assert.equal(toPayload(refi).agents.listing, null);
  assert.equal(toPayload(refi).loan.refinanceType, 'fha_streamline');

  const wrongAus = syntheticSubmission({ loan: { program: 'usda', aus: 'du' } });
  assert.ok(validateSubmission(wrongAus).errors['loan.aus']);
  const conv = syntheticSubmission({ loan: { program: 'conventional', conventionalAgency: 'fannie_mae', aus: 'du' } });
  assert.deepEqual(validateSubmission(conv).errors, {});
  assert.equal(toPayload(conv).loan.conventionalAgency, 'fannie_mae');
});

test('credit omissions must be explained, lender buyout notes ride along, HOA/condo fields are conditional', () => {
  const omitted = syntheticSubmission({ credit: { borrower: { status: ['tradeline_omitted'] } } });
  assert.equal(validateSubmission(omitted).errors['credit.borrower.omittedDebtsNotes'], 'If any debts are omitted, please explain');
  omitted.credit.borrower.omittedDebtsNotes = 'Paid collection omitted per lender';
  assert.deepEqual(validateSubmission(omitted).errors, {});

  const buyout = syntheticSubmission({ fees: { lenderBuyingOutFee: 'yes', buyoutNotes: 'Lender credit covers processing fee' } });
  assert.equal(toPayload(buyout).fees.buyoutNotes, 'Lender credit covers processing fee');

  const hoa = syntheticSubmission({ loan: { homeType: 'condo' }, hoa: { present: 'yes', company: 'Synthetic HOA Mgmt', phone: '9045550106', email: 'hoa@synthetic.test', condoQuestionnaireStatus: 'requested' } });
  assert.deepEqual(validateSubmission(hoa).errors, {});
  assert.equal(toPayload(hoa).hoa.condoQuestionnaireStatus, 'requested');
  assert.equal(toPayload(syntheticSubmission()).hoa.condoQuestionnaireStatus, null);
});

test('full SSNs and full account numbers are rejected everywhere; last-4 references pass', () => {
  const ssn = syntheticSubmission({ notes: 'Borrower SSN 123-45-6789' });
  assert.ok(validateSubmission(ssn).errors.notes);
  const acct = syntheticSubmission({ assets: [{ sourceType: 'borrower_bank_account', nameOrInstitution: 'Bank', accountReference: '1234567890', amount: '100' }] });
  assert.ok(validateSubmission(acct).errors['assets.0.accountReference']);
  const spaced = syntheticSubmission({ notes: 'acct 4111 1111 1111 1111' });
  assert.deepEqual(findSensitiveStrings(spaced), ['notes']);
  assert.deepEqual(findSensitiveStrings(syntheticSubmission()), []);
  // Dates, phone numbers inside notes and last-4 references are fine.
  const fine = syntheticSubmission({ notes: 'Closing 09/23/2026, call 9045550199, last 4 of gift acct 4321' });
  assert.deepEqual(findSensitiveStrings(fine), []);
  assert.deepEqual(validateSubmission(fine).errors, {});
});

test('POST creates once, delivers to Flo, and a duplicate click or retry never creates a second loan', async () => {
  let deliveries = 0;
  const deliver = async () => {
    deliveries += 1;
    return { ok: true, result: { status: 201, workspaceId: 'loan_synthetic' } };
  };
  await withApp({ deliver }, async ({ post, get }) => {
    const s = syntheticSubmission();
    const [a, b] = await Promise.all([post(s), post(s)]);
    const first = await a.json();
    const second = await b.json();
    assert.equal(a.status, 200);
    assert.equal(b.status, 200);
    assert.equal(first.submissionId, s.submissionId);
    assert.equal(second.submissionId, s.submissionId);
    assert.equal(deliveries, 1);
    const again = await (await post(s)).json();
    assert.equal(again.duplicate, true);
    assert.equal(deliveries, 1);
    const status = await (await get(s.submissionId)).json();
    assert.equal(status.status, 'delivered');
    assert.equal(status.borrowerName, 'Ariana Justinvil-Synthetic');
    assert.ok(!('payload' in status));
  });
});

test('when Flo is unavailable the loan is kept as pending delivery, the LO sees "received", and the retry worker delivers later', async () => {
  let up = false;
  let deliveries = 0;
  const deliver = async () => {
    deliveries += 1;
    return up ? { ok: true, result: { status: 201, workspaceId: 'loan_synthetic' } } : { ok: false, retryable: true, error: 'Flo intake unreachable (ECONNREFUSED)' };
  };
  await withApp({ deliver }, async ({ post, store }) => {
    const s = syntheticSubmission();
    const res = await post(s);
    assert.equal(res.status, 202);
    const body = await res.json();
    assert.equal(body.ok, true);
    assert.equal(body.status, 'received');
    const record = store.get(s.submissionId);
    assert.equal(record.status, 'pending_delivery');
    assert.equal(record.deliveryAttempts, 1);
    assert.ok(record.nextAttemptAt);
    assert.equal(backoffMs(1), 60_000);
    assert.equal(backoffMs(20), 15 * 60_000);
    // Not due yet: nothing happens.
    assert.equal((await retryPending(store, { deliver, log: quiet })).length, 0);
    // Flo comes back; the worker delivers.
    up = true;
    const far = () => new Date(Date.now() + 60 * 60_000);
    const results = await retryPending(store, { deliver, log: quiet, now: far });
    assert.equal(results.length, 1);
    assert.equal(results[0].status, 'delivered');
    assert.equal(results[0].delivered.workspaceId, 'loan_synthetic');
    assert.equal(deliveries, 2);
    // A resubmit after delivery is still the same loan.
    assert.equal((await (await post(s)).json()).duplicate, true);
    assert.equal(deliveries, 2);
  });
});

test('validation failures, honeypot, bad ids, origin and rate limits are enforced without touching Flo', async () => {
  const deliver = async () => assert.fail('must not deliver');
  await withApp({ deliver, rateLimiter: createRateLimiter({ max: 5 }), allowedOrigins: ['https://lfprocessing.net'] }, async ({ post }) => {
    const ok = { origin: 'https://lfprocessing.net' };
    assert.equal((await post(syntheticSubmission(), { origin: 'https://evil.example' })).status, 403);
    const bad = await post(syntheticSubmission({ borrower: { name: '' }, loan: { loanAmount: 'abc' } }), ok);
    assert.equal(bad.status, 400);
    const fields = (await bad.json()).fields;
    assert.ok(fields['borrower.name']);
    assert.ok(fields['loan.loanAmount']);
    const bot = await post(syntheticSubmission({ website: 'http://spam' }), ok);
    assert.equal(bot.status, 200);
    assert.equal((await post(syntheticSubmission({ submissionId: 'evil/../id' }), ok)).status, 400);
    assert.equal((await post(syntheticSubmission({ submissionId: 'sub_zzzz' }), ok)).status, 400);
    // Sixth request from the same address inside the window is rate limited.
    assert.equal((await post(syntheticSubmission(), ok)).status, 429);
  });
});

test('deliverToFlo sends the bearer token and idempotency key, treats 201/200/409 as delivered, 5xx as retryable, 4xx as not', async () => {
  const env = { FLO_INTAKE_URL: 'http://flo.local:8787/', FLO_INTAKE_TOKEN: 'secret-token' };
  const seen = [];
  const mk = (status, body = {}) => async (url, init) => {
    seen.push({ url, init });
    return { status, text: async () => JSON.stringify(body) };
  };
  const payload = toPayload(syntheticSubmission());
  const ok = await deliverToFlo(payload, { env, fetchImpl: mk(201, { workspaceId: 'loan_x' }) });
  assert.equal(ok.ok, true);
  assert.equal(ok.result.workspaceId, 'loan_x');
  assert.equal(seen[0].url, 'http://flo.local:8787/intake/loan-submissions');
  assert.equal(seen[0].init.headers.Authorization, 'Bearer secret-token');
  assert.equal(seen[0].init.headers['Idempotency-Key'], payload.submissionId);
  assert.equal((await deliverToFlo(payload, { env, fetchImpl: mk(409, { workspaceId: 'loan_x' }) })).result.duplicate, true);
  const down = await deliverToFlo(payload, { env, fetchImpl: mk(503) });
  assert.equal(down.ok, false);
  assert.equal(down.retryable, true);
  const rejected = await deliverToFlo(payload, { env, fetchImpl: mk(422) });
  assert.equal(rejected.retryable, false);
  const unconfigured = await deliverToFlo(payload, { env: {} });
  assert.equal(unconfigured.retryable, true);
  const store = tmpStore();
  const { record } = store.create(payload, {});
  const after = await attemptDelivery(store, record, { deliver: async () => rejected, log: quiet });
  assert.equal(after.status, 'delivery_failed');
});
