import { google } from 'googleapis';

// Optional, best-effort: one summary row per delivered submission in the existing
// "Form Responses 1" tab (the legacy 12-column layout). The full submission never
// goes to the sheet — Flo is the system of record. Silently skipped when the
// Google credentials are not configured.

let sheetsClient = null;

function configured() {
  return Boolean(process.env.GOOGLE_CLIENT_EMAIL && process.env.GOOGLE_PRIVATE_KEY && process.env.GOOGLE_SHEET_ID);
}

function getAuthClient() {
  const clientEmail = process.env.GOOGLE_CLIENT_EMAIL;
  const privateKey = process.env.GOOGLE_PRIVATE_KEY?.replace(/\\n/g, '\n');
  if (!clientEmail || !privateKey) throw new Error('Missing Google Sheets credentials');
  return new google.auth.GoogleAuth({ credentials: { client_email: clientEmail, private_key: privateKey }, scopes: ['https://www.googleapis.com/auth/spreadsheets'] });
}

function getSheetsClient() {
  if (!sheetsClient) sheetsClient = google.sheets({ version: 'v4', auth: getAuthClient() });
  return sheetsClient;
}

/**
 * Appends a single row to the "Form Responses 1" tab (columns A:L).
 * @param {string[]} rowData
 */
export async function appendToSheet(rowData) {
  const sheets = getSheetsClient();
  const response = await sheets.spreadsheets.values.append({
    spreadsheetId: process.env.GOOGLE_SHEET_ID,
    range: 'Form Responses 1!A:L',
    valueInputOption: 'RAW',
    insertDataOption: 'INSERT_ROWS',
    requestBody: { values: [rowData] },
  });
  return response.data;
}

/** Legacy 12-column summary for a delivered submission record. No income, assets, credit or notes. */
export function summaryRow(record) {
  const p = record.payload;
  const borrower = p.borrowers?.[0] || {};
  const co = p.borrowers?.[1] || {};
  const timestamp = new Date(record.receivedAt).toLocaleString('en-US', { timeZone: 'America/New_York' });
  return [
    timestamp,
    p.loanOfficer?.name || '',
    p.loanOfficer?.company || '',
    p.loanOfficer?.email || '',
    p.loanOfficer?.phone || '',
    borrower.name || '',
    co.name || '',
    borrower.email || '',
    borrower.phone || '',
    p.loan?.propertyAddress || '',
    [p.loan?.program, p.loan?.transactionType].filter(Boolean).join(' / '),
    `Submitted to Flo · ${record.submissionId}`,
  ];
}

export async function appendSubmissionSummary(record) {
  if (!configured()) return null;
  return appendToSheet(summaryRow(record));
}
