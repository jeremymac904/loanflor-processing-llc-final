import { Router } from 'express';
import { appendToSheet } from '../services/googleSheets.js';

export const loanSubmissionRouter = Router();

/**
 * Fields that must be present and non-empty in every submission.
 */
const REQUIRED_FIELDS = [
  'loanOfficerFullName',
  'companyName',
  'emailAddress',
  'phoneNumber',
  'borrowerFullName',
  'propertyAddress',
  'loanType',
];

/**
 * Simple email format validation.
 */
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * POST /api/loan-submission
 *
 * Accepts a JSON body with loan submission fields, validates them,
 * and appends a new row to the Google Sheet.
 */
loanSubmissionRouter.post('/loan-submission', async (req, res) => {
  try {
    const data = req.body;

    // ── Honeypot spam check ─────────────────────────────────────
    // If the hidden "website" field has a value, a bot filled it in.
    // Return success silently so the bot doesn't know it was caught.
    if (data.website) {
      return res.json({ ok: true });
    }

    // ── Required-field validation ───────────────────────────────
    const missing = REQUIRED_FIELDS.filter(
      (field) => !data[field] || !data[field].toString().trim()
    );

    if (missing.length > 0) {
      return res.status(400).json({
        ok: false,
        error: 'Missing required fields',
        fields: missing,
      });
    }

    // ── Email validation ────────────────────────────────────────
    if (!isValidEmail(data.emailAddress)) {
      return res.status(400).json({
        ok: false,
        error: 'Invalid email address format',
        fields: ['emailAddress'],
      });
    }

    // Validate borrower email if provided
    if (data.borrowerEmail && data.borrowerEmail.trim() && !isValidEmail(data.borrowerEmail)) {
      return res.status(400).json({
        ok: false,
        error: 'Invalid borrower email address format',
        fields: ['borrowerEmail'],
      });
    }

    // ── Build row in exact column order ─────────────────────────
    const timestamp = new Date().toLocaleString('en-US', {
      timeZone: 'America/New_York',
    });

    const row = [
      timestamp,                                    // A - Timestamp
      data.loanOfficerFullName.trim(),              // B - Loan Officer Full Name
      data.companyName.trim(),                      // C - Company Name
      data.emailAddress.trim(),                     // D - Email Address
      data.phoneNumber.trim(),                      // E - Phone Number
      data.borrowerFullName.trim(),                 // F - Borrower Full Name
      (data.coBorrowerFullName || '').trim(),        // G - Co-Borrower Full Name
      (data.borrowerEmail || '').trim(),             // H - Borrower Email
      (data.borrowerPhone || '').trim(),             // I - Borrower Phone
      data.propertyAddress.trim(),                  // J - Property Address
      data.loanType.trim(),                         // K - Loan Type
      (data.notes || '').trim(),                    // L - Notes
    ];

    // ── Append to Google Sheet ──────────────────────────────────
    await appendToSheet(row);

    console.log(`✓ Loan submission received from ${data.loanOfficerFullName} at ${data.companyName}`);

    return res.json({ ok: true });
  } catch (error) {
    console.error('Loan submission error:', error.message || error);

    return res.status(500).json({
      ok: false,
      error: 'Failed to submit loan. Please try again or contact support at (904) 535-1902.',
    });
  }
});
