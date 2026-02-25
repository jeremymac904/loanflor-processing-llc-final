import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { loanSubmissionRouter } from './routes/loanSubmission.js';

// ── Load environment variables ──────────────────────────────────
dotenv.config();

const app = express();
const PORT = process.env.SERVER_PORT || 3001;

// ── Middleware ───────────────────────────────────────────────────
app.use(
  cors({
    origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
  })
);
app.use(express.json({ limit: '1mb' }));

// ── Routes ──────────────────────────────────────────────────────
app.use('/api', loanSubmissionRouter);

// Health-check endpoint
app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'LoanFlow Processing API',
    timestamp: new Date().toISOString(),
  });
});

// ── Start server ────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log('');
  console.log('  ┌──────────────────────────────────────────────┐');
  console.log(`  │  LoanFlow API server running on port ${PORT}     │`);
  console.log('  │  POST /api/loan-submission                    │');
  console.log('  │  GET  /api/health                             │');
  console.log('  └──────────────────────────────────────────────┘');
  console.log('');
});
