// Document records for a submission (one JSON file per submission, git-ignored) and the
// upload rules: type/size/magic-byte validation, safe generated storage keys, clean
// display names, checksum-based duplicate detection. Files themselves go through
// documentStorage.js. The original binary is never altered; display names are metadata.

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { DOCUMENT_UPLOAD, OPTIONS } from '../../shared/loanSubmission.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_DIR = path.resolve(HERE, '..', 'data', 'documents-meta');
const ID_RE = /^sub_[0-9a-f]{24}$/;
const DOC_ID_RE = /^doc_[0-9a-f]{24}$/;
const CATEGORY_FOLDER = {
  loan_application: 'application',
  credit_report: 'credit',
  aus_findings: 'aus',
  income: 'income',
  assets: 'assets',
  purchase_contract: 'contract',
  title_property: 'title',
  insurance: 'insurance',
  identification: 'identification',
  other: 'other',
};
const SLUG = {
  loan_application: '1003',
  credit_report: 'credit_report',
  aus_findings: 'aus_findings',
  income: 'income',
  assets: 'asset',
  purchase_contract: 'purchase_contract',
  title_property: 'title',
  insurance: 'insurance',
  identification: 'identification',
  other: 'document',
  paystub: 'paystub',
  w2: 'w2',
  1099: '1099',
  tax_return: 'tax_return',
  profit_and_loss: 'profit_and_loss',
  k1: 'k1',
  bank_statement: 'bank_statement',
  retirement_statement: 'retirement_statement',
  gift_documentation: 'gift_documentation',
};

const MAGIC = {
  pdf: (b) => b.subarray(0, 5).toString('latin1') === '%PDF-',
  jpg: (b) => b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff,
  jpeg: (b) => b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff,
  png: (b) => b.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])),
  tif: (b) => ['II*\0', 'MM\0*'].includes(b.subarray(0, 4).toString('latin1')),
  tiff: (b) => ['II*\0', 'MM\0*'].includes(b.subarray(0, 4).toString('latin1')),
  heic: (b) => b.subarray(4, 8).toString('latin1') === 'ftyp',
  docx: (b) => b[0] === 0x50 && b[1] === 0x4b && b[2] === 0x03 && b[3] === 0x04,
  xlsx: (b) => b[0] === 0x50 && b[1] === 0x4b && b[2] === 0x03 && b[3] === 0x04,
};

export class UploadError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export function safeOriginalName(name) {
  const base = String(name || 'document').split(/[\\/]/).pop().replace(/[^\w.\- ()]/g, '_').trim().slice(0, 120);
  return base || 'document';
}

export function extensionOf(name) {
  return String(name || '').toLowerCase().split('.').pop();
}

/** Validate an incoming file. Returns {ext, mimeType, sha256}. */
export function validateUpload({ originalFilename, sizeBytes, buffer }) {
  const ext = extensionOf(originalFilename);
  if (!DOCUMENT_UPLOAD.acceptedExtensions.includes(ext)) throw new UploadError(415, 'File type not accepted. Use PDF, JPG, PNG, TIFF, HEIC, DOCX or XLSX.');
  if (!buffer || buffer.length === 0) throw new UploadError(400, 'Empty file');
  if (buffer.length > DOCUMENT_UPLOAD.maxFileBytes || sizeBytes > DOCUMENT_UPLOAD.maxFileBytes) throw new UploadError(413, 'File is larger than 25 MB');
  const magic = MAGIC[ext];
  if (magic && !magic(buffer)) throw new UploadError(415, 'File content does not match its type');
  // Anything that looks like HTML/script, regardless of extension, is refused.
  const head = buffer.subarray(0, 512).toString('latin1').toLowerCase();
  if (/<!doctype html|<html|<script/.test(head)) throw new UploadError(415, 'File content not accepted');
  if (/\b\d{3}-\d{2}-\d{4}\b/.test(originalFilename) || /\d{8,}/.test(originalFilename)) throw new UploadError(400, 'File name must not contain an SSN or account number');
  return { ext, mimeType: DOCUMENT_UPLOAD.mimeByExtension[ext], sha256: crypto.createHash('sha256').update(buffer).digest('hex') };
}

function slugFor(category, subcategory) {
  return SLUG[subcategory] || SLUG[category] || 'document';
}

function pad(n) {
  return String(n).padStart(2, '0');
}

export function createDocumentStore(dir = process.env.DOCUMENTS_META_DIR || DEFAULT_DIR) {
  fs.mkdirSync(dir, { recursive: true });
  const fileFor = (submissionId) => {
    if (!ID_RE.test(submissionId)) throw new UploadError(400, 'invalid submission id');
    return path.join(dir, `${submissionId}.json`);
  };
  const read = (submissionId) => {
    try {
      return JSON.parse(fs.readFileSync(fileFor(submissionId), 'utf8'));
    } catch (error) {
      if (error.code === 'ENOENT') return { submissionId, documents: [] };
      throw error;
    }
  };
  const write = (doc) => {
    const file = fileFor(doc.submissionId);
    const tmp = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(doc, null, 2), { mode: 0o600 });
    fs.renameSync(tmp, file);
    return doc;
  };

  return {
    dir,
    list(submissionId) {
      return read(submissionId).documents;
    },
    get(submissionId, documentId) {
      if (!DOC_ID_RE.test(documentId)) return null;
      return read(submissionId).documents.find((d) => d.documentId === documentId) || null;
    },
    /**
     * Register an upload. Duplicate content (same sha256 already stored for this submission) is recorded
     * with status `duplicate` pointing at the existing object — nothing is deleted, and no second copy is stored.
     */
    register({ submissionId, category, subcategory, borrowerRef, originalFilename, sizeBytes, ext, mimeType, sha256, uploadedBy = 'loan_officer', now = new Date() }) {
      if (!OPTIONS.documentCategory.some(([v]) => v === category)) throw new UploadError(400, 'Select a document category');
      const sub = (category === 'income' ? OPTIONS.incomeSubtype : category === 'assets' ? OPTIONS.assetSubtype : []).some(([v]) => v === subcategory) ? subcategory : null;
      const who = OPTIONS.documentBorrower.some(([v]) => v === borrowerRef) ? borrowerRef : null;
      const doc = read(submissionId);
      const active = doc.documents.filter((d) => d.status !== 'removed');
      if (active.length >= DOCUMENT_UPLOAD.maxFiles) throw new UploadError(400, `Up to ${DOCUMENT_UPLOAD.maxFiles} files per submission`);
      const existing = active.find((d) => d.sha256 === sha256 && d.status !== 'duplicate');
      const folder = CATEGORY_FOLDER[category];
      const date = now.toISOString().slice(0, 10);
      const n = active.filter((d) => d.category === category && (d.subcategory || null) === sub).length + 1;
      const slug = slugFor(category, sub);
      const displayName = `${date}_${slug}_${pad(n)}.${ext}`;
      const record = {
        documentId: `doc_${crypto.randomBytes(12).toString('hex')}`,
        submissionId,
        category,
        subcategory: sub,
        borrowerRef: who,
        originalFilename: safeOriginalName(originalFilename),
        displayName,
        storageKey: existing ? existing.storageKey : `submissions/${submissionId}/${folder}/${displayName}`,
        mimeType,
        sizeBytes,
        sha256,
        uploadedAt: now.toISOString(),
        uploadedBy,
        status: existing ? 'duplicate' : 'received',
        duplicateOf: existing ? existing.documentId : null,
        classificationSource: 'loan_officer',
        notes: existing ? `Same content as ${existing.displayName}` : '',
      };
      doc.documents.push(record);
      write(doc);
      return { record, storeBinary: !existing };
    },
    remove(submissionId, documentId) {
      const doc = read(submissionId);
      const rec = doc.documents.find((d) => d.documentId === documentId);
      if (!rec) return null;
      rec.status = 'removed';
      rec.removedAt = new Date().toISOString();
      write(doc);
      return rec;
    },
    markSubmitted(submissionId) {
      const doc = read(submissionId);
      doc.submittedAt = new Date().toISOString();
      write(doc);
      return doc;
    },
    isSubmitted(submissionId) {
      return Boolean(read(submissionId).submittedAt);
    },
  };
}

export function publicDocument(rec) {
  return {
    id: rec.documentId,
    category: rec.category,
    subcategory: rec.subcategory,
    borrowerRef: rec.borrowerRef,
    fileName: rec.originalFilename,
    displayName: rec.displayName,
    sizeBytes: rec.sizeBytes,
    contentType: rec.mimeType,
    status: rec.status,
    uploadedAt: rec.uploadedAt,
  };
}
