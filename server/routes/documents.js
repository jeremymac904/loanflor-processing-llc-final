// Document upload for a loan submission (before the LO clicks Submit) and the
// authenticated internal fetch Flo uses to pull the files.
//
//   PUT    /api/loan-submissions/:id/documents?category=&subcategory=&borrower=&filename=   (raw bytes)
//   GET    /api/loan-submissions/:id/documents
//   DELETE /api/loan-submissions/:id/documents/:docId
//   GET    /api/internal/documents/:id/:docId          Authorization: Bearer <FLO_INTAKE_TOKEN>
//
// Browser → this server → private storage. Storage credentials live only here.

import crypto from 'node:crypto';
import express, { Router } from 'express';

import { DOCUMENT_UPLOAD } from '../../shared/loanSubmission.js';
import { publicDocument, UploadError, validateUpload } from '../services/documentStore.js';
import { createRateLimiter } from './loanSubmissions.js';

const ID_RE = /^sub_[0-9a-f]{24}$/;
const DOC_ID_RE = /^doc_[0-9a-f]{24}$/;

function tokenOk(req, token) {
  const header = req.get('authorization') || '';
  const presented = header.startsWith('Bearer ') ? header.slice(7) : '';
  if (!token || !presented || presented.length !== token.length) return false;
  return crypto.timingSafeEqual(Buffer.from(presented), Buffer.from(token));
}

export function createDocumentsRouter({ store, storage, submissions, intakeToken = process.env.FLO_INTAKE_TOKEN, rateLimiter = createRateLimiter({ max: 300 }), log = console } = {}) {
  const router = Router();
  const raw = express.raw({ type: () => true, limit: DOCUMENT_UPLOAD.maxFileBytes + 1024 });

  router.put('/loan-submissions/:id/documents', rateLimiter, raw, async (req, res) => {
    const submissionId = req.params.id;
    if (!ID_RE.test(submissionId)) return res.status(400).json({ ok: false, error: 'Invalid submission id' });
    if (store.isSubmitted(submissionId) || submissions?.get?.(submissionId)) return res.status(409).json({ ok: false, error: 'This submission was already sent; processing will ask for anything else it needs.' });
    try {
      const originalFilename = String(req.query.filename || '');
      const buffer = Buffer.isBuffer(req.body) ? req.body : Buffer.alloc(0);
      const checked = validateUpload({ originalFilename, sizeBytes: buffer.length, buffer });
      const { record, storeBinary } = store.register({
        submissionId,
        category: String(req.query.category || ''),
        subcategory: String(req.query.subcategory || '') || null,
        borrowerRef: String(req.query.borrower || '') || null,
        originalFilename,
        sizeBytes: buffer.length,
        ext: checked.ext,
        mimeType: checked.mimeType,
        sha256: checked.sha256,
      });
      if (storeBinary) await storage.put(record.storageKey, buffer, record.mimeType);
      log.info?.(`[documents] ${submissionId} ${record.documentId} ${record.status} (${record.category}, ${buffer.length} bytes)`);
      return res.status(201).json({ ok: true, document: publicDocument(record) });
    } catch (error) {
      if (error instanceof UploadError) return res.status(error.status).json({ ok: false, error: error.message });
      log.error?.(`[documents] ${submissionId} upload failed: ${error.message}`);
      return res.status(500).json({ ok: false, error: 'Upload failed. Please try that file again.' });
    }
  });

  router.get('/loan-submissions/:id/documents', (req, res) => {
    if (!ID_RE.test(req.params.id)) return res.status(400).json({ ok: false, error: 'Invalid submission id' });
    return res.json({ ok: true, documents: store.list(req.params.id).filter((d) => d.status !== 'removed').map(publicDocument) });
  });

  router.delete('/loan-submissions/:id/documents/:docId', (req, res) => {
    if (!ID_RE.test(req.params.id) || !DOC_ID_RE.test(req.params.docId)) return res.status(400).json({ ok: false, error: 'Invalid id' });
    if (store.isSubmitted(req.params.id)) return res.status(409).json({ ok: false, error: 'This submission was already sent' });
    const rec = store.remove(req.params.id, req.params.docId);
    if (!rec) return res.status(404).json({ ok: false, error: 'Not found' });
    // The object is kept until the archive/cleanup job runs (another record may share it); nothing is deleted here.
    return res.json({ ok: true });
  });

  router.get('/internal/documents/:id/:docId', async (req, res) => {
    if (!tokenOk(req, intakeToken)) return res.status(401).json({ ok: false, error: 'unauthorized' });
    if (!ID_RE.test(req.params.id) || !DOC_ID_RE.test(req.params.docId)) return res.status(400).json({ ok: false, error: 'Invalid id' });
    const rec = store.get(req.params.id, req.params.docId);
    if (!rec || rec.status === 'removed') return res.status(404).json({ ok: false, error: 'Not found' });
    try {
      const buffer = await storage.get(rec.storageKey);
      res.set('Content-Type', rec.mimeType || 'application/octet-stream');
      res.set('Content-Length', String(buffer.length));
      res.set('X-Document-Sha256', rec.sha256);
      res.set('Content-Disposition', `attachment; filename="${rec.displayName}"`);
      return res.send(buffer);
    } catch (error) {
      log.error?.(`[documents] fetch ${rec.documentId} failed: ${error.message}`);
      return res.status(502).json({ ok: false, error: 'Storage unavailable' });
    }
  });

  return router;
}
