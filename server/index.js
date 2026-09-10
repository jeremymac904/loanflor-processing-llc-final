import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

import { createDocumentsRouter } from './routes/documents.js';
import { createEsignWebhookRouter } from './routes/esignWebhook.js';
import { createLoanSubmissionsRouter } from './routes/loanSubmissions.js';
import { startDeliveryWorker } from './services/deliveryQueue.js';
import { createDocumentStorage } from './services/documentStorage.js';
import { createDocumentStore } from './services/documentStore.js';
import { createEsignWebhookStore } from './services/esignWebhookStore.js';
import { intakeConfigured } from './services/floIntake.js';
import { createSubmissionStore } from './services/submissionStore.js';

// ── Load environment variables ──────────────────────────────────
dotenv.config();

const app = express();
const PORT = process.env.SERVER_PORT || 3001;
const PRODUCTION = process.env.NODE_ENV === 'production';
const ALLOWED_ORIGINS = (process.env.CORS_ORIGIN || 'http://localhost:3000')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);

// ── Middleware ───────────────────────────────────────────────────
app.set('trust proxy', 1);
app.disable('x-powered-by');
app.use((req, res, next) => {
  // HTTPS only in production (behind the host's proxy); plain http is fine locally.
  if (PRODUCTION && req.get('x-forwarded-proto') && req.get('x-forwarded-proto') !== 'https') {
    return res.redirect(308, `https://${req.get('host')}${req.originalUrl}`);
  }
  res.set('X-Content-Type-Options', 'nosniff');
  res.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.set('Cache-Control', 'no-store');
  return next();
});
app.use(cors({ origin: ALLOWED_ORIGINS }));
app.use(express.json({ limit: '512kb' }));

// ── Routes ──────────────────────────────────────────────────────
const store = createSubmissionStore();
const documents = createDocumentStore();
const storage = createDocumentStorage();
app.use('/api', createLoanSubmissionsRouter({ store, documents, allowedOrigins: PRODUCTION ? ALLOWED_ORIGINS : [] }));
app.use('/api', createDocumentsRouter({ store: documents, storage, submissions: store }));
const esignWebhookStore = createEsignWebhookStore();
app.use('/api', createEsignWebhookRouter({ store: esignWebhookStore }));

// Health-check endpoint
app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'LoanFlow Processing API',
    floIntake: intakeConfigured() ? 'configured' : 'not configured (submissions are stored as pending delivery)',
    documentStorage: storage.kind,
    pendingDelivery: store.pending().length,
    esignWebhook: process.env.DOCUMENSO_WEBHOOK_SECRET ? 'configured' : 'not configured',
    timestamp: new Date().toISOString(),
  });
});

// JSON errors, never stack traces or bodies.
app.use((error, _req, res, _next) => {
  if (error?.type === 'entity.too.large') return res.status(413).json({ ok: false, error: 'Submission is too large' });
  if (error?.type === 'entity.parse.failed') return res.status(400).json({ ok: false, error: 'Invalid JSON' });
  console.error(`[api] ${error?.message || 'error'}`);
  return res.status(500).json({ ok: false, error: 'Something went wrong. Please try again.' });
});

// ── Start server ────────────────────────────────────────────────
app.listen(PORT, () => {
  startDeliveryWorker(store);
  console.log('');
  console.log('  ┌──────────────────────────────────────────────┐');
  console.log(`  │  LoanFlow API server running on port ${PORT}     │`);
  console.log('  │  POST /api/loan-submissions                   │');
  console.log('  │  GET  /api/loan-submissions/:id               │');
  console.log('  │  GET  /api/health                             │');
  console.log('  └──────────────────────────────────────────────┘');
  console.log(`  Flo intake: ${intakeConfigured() ? 'configured' : 'NOT configured — submissions will wait as pending delivery'}`);
  console.log('');
});
