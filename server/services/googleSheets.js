import { google } from 'googleapis';

let sheetsClient = null;

/**
 * Creates a Google Auth client using service account credentials
 * stored in environment variables.
 */
function getAuthClient() {
  const clientEmail = process.env.GOOGLE_CLIENT_EMAIL;
  const privateKey = process.env.GOOGLE_PRIVATE_KEY?.replace(/\\n/g, '\n');
  const sheetId = process.env.GOOGLE_SHEET_ID;

  if (!clientEmail || !privateKey || !sheetId) {
    throw new Error(
      'Missing Google Sheets credentials. Ensure GOOGLE_CLIENT_EMAIL, GOOGLE_PRIVATE_KEY, and GOOGLE_SHEET_ID are set in .env'
    );
  }

  const auth = new google.auth.GoogleAuth({
    credentials: {
      client_email: clientEmail,
      private_key: privateKey,
    },
    scopes: ['https://www.googleapis.com/auth/spreadsheets'],
  });

  return auth;
}

/**
 * Returns a cached Google Sheets API client instance.
 */
function getSheetsClient() {
  if (!sheetsClient) {
    const auth = getAuthClient();
    sheetsClient = google.sheets({ version: 'v4', auth });
  }
  return sheetsClient;
}

/**
 * Appends a single row of data to the "Form Responses 1" tab
 * of the configured Google Sheet.
 *
 * @param {string[]} rowData - Array of cell values in column order
 * @returns {object} Google Sheets API response data
 */
export async function appendToSheet(rowData) {
  const sheets = getSheetsClient();
  const spreadsheetId = process.env.GOOGLE_SHEET_ID;

  const response = await sheets.spreadsheets.values.append({
    spreadsheetId,
    range: 'Form Responses 1!A:L',
    valueInputOption: 'USER_ENTERED',
    insertDataOption: 'INSERT_ROWS',
    requestBody: {
      values: [rowData],
    },
  });

  console.log(
    `✓ Row appended to sheet. Updated range: ${response.data.updates?.updatedRange}`
  );

  return response.data;
}
