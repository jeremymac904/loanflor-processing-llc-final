// ─────────────────────────────────────────────────────────────────────────────
// LoanFlow Loan Submission — shared contract (browser + server).
//
// One module, no dependencies, plain ESM so Vite (the form) and Node (the API)
// use the same option lists, the same validation and the same payload shape.
// The payload is the "New Loan Submission" event Flo consumes; see
// LOAN_SUBMISSION_SCHEMA.md. Bump SCHEMA_VERSION on any breaking change.
// ─────────────────────────────────────────────────────────────────────────────

export const SCHEMA_VERSION = '1.0';
export const SOURCE = 'lfprocessing.net';

export const OPTIONS = {
  occupancy: [
    ['primary', 'Primary residence'],
    ['second_home', 'Second home'],
    ['investment', 'Investment'],
  ],
  transactionType: [
    ['purchase', 'Purchase'],
    ['refinance_rate_term', 'Refinance — Rate & Term'],
    ['refinance_cash_out', 'Refinance — Cash Out'],
  ],
  program: [
    ['conventional', 'Conventional'],
    ['fha', 'FHA'],
    ['va', 'VA'],
    ['usda', 'USDA'],
    ['jumbo', 'Jumbo'],
    ['non_qm', 'Non-QM'],
    ['other', 'Other'],
  ],
  conventionalAgency: [
    ['fannie_mae', 'Fannie Mae'],
    ['freddie_mac', 'Freddie Mac'],
    ['not_sure', 'Not sure'],
  ],
  aus: [
    ['du', 'DU'],
    ['lpa', 'LPA / LP'],
    ['total', 'TOTAL'],
    ['gus', 'GUS'],
    ['va_aus', 'VA AUS'],
    ['manual', 'Manual'],
    ['other', 'Other / Not sure'],
  ],
  refinanceType: [
    ['fha_streamline', 'FHA Streamline'],
    ['va_irrrl', 'VA IRRRL'],
    ['standard', 'Standard refinance'],
    ['other', 'Other'],
  ],
  homeType: [
    ['single_family', 'Single family'],
    ['condo', 'Condo'],
    ['pud', 'PUD'],
    ['two_to_four_unit', '2–4 unit'],
    ['manufactured', 'Manufactured'],
    ['other', 'Other'],
  ],
  channel: [
    ['brokered', 'Brokered'],
    ['correspondent', 'Correspondent'],
  ],
  compensation: [
    ['lender_paid', 'Lender paid'],
    ['borrower_paid', 'Borrower paid'],
  ],
  yesNo: [
    ['yes', 'Yes'],
    ['no', 'No'],
  ],
  yesNoNa: [
    ['yes', 'Yes'],
    ['no', 'No'],
    ['not_applicable', 'Not applicable'],
  ],
  yesNoUnknown: [
    ['yes', 'Yes'],
    ['no', 'No'],
    ['unknown', 'Unknown'],
  ],
  appraisalTiming: [
    ['prior_to_inspection', 'Order PRIOR to inspection'],
    ['after_inspection', 'Order AFTER inspection'],
  ],
  communicationPreferences: [
    ['realtor_voice', 'Realtor — voice'],
    ['realtor_email_cc_lo', 'Realtor — email, CC loan officer'],
    ['borrower_voice', 'Borrower — voice'],
    ['borrower_email_cc_lo', 'Borrower — email, CC loan officer'],
  ],
  condoQuestionnaireStatus: [
    ['completed', 'Already completed / attached'],
    ['requested', 'Requested — waiting on it'],
    ['order_on_disclosure', 'Order upon disclosure / authorization'],
    ['not_applicable', 'Not applicable'],
  ],
  incomeType: [
    ['w2', 'W-2'],
    ['1099', '1099'],
    ['self_employed', 'Self-employed'],
    ['rental', 'Rental'],
    ['retirement_pension', 'Retirement / pension'],
    ['social_security', 'Social Security'],
    ['military', 'Military'],
    ['other', 'Other'],
  ],
  calculationBasis: [
    ['two_year_average', '2-year average'],
    ['latest_year', 'Latest year'],
    ['current_income', 'Current income'],
    ['other_unknown', 'Other / unknown'],
  ],
  incomeDocuments: [
    ['paystubs', 'Paystubs'],
    ['w2s', 'W-2s'],
    ['tax_returns', 'Tax returns'],
    ['1099s', '1099s'],
    ['award_letter', 'Award letter'],
    ['bank_statements', 'Bank statements'],
    ['lease', 'Lease'],
    ['voe', 'VOE'],
  ],
  creditStatus: [
    ['as_per_credit_pull', 'As per credit pull — no additional work'],
    ['rescore_or_supplement', 'Rescore / credit supplement completed or needed'],
    ['tradeline_omitted', 'Tradeline omitted'],
    ['other_issue', 'Other issue'],
  ],
  fundsSourceType: [
    ['gift_from_relative', 'Gift from relative'],
    ['borrower_bank_account', "Borrower's bank account"],
    ['retirement_withdrawal', '401(k) / retirement withdrawal'],
    ['lender_credits', 'Lender credits at closing'],
    ['other', 'Other'],
  ],
  documentCategory: [
    ['loan_application', '1003 / Loan application'],
    ['credit_report', 'Credit report'],
    ['aus_findings', 'AUS findings'],
    ['income', 'Income documents'],
    ['assets', 'Asset documents'],
    ['purchase_contract', 'Purchase contract'],
    ['title_property', 'Title / property documents'],
    ['insurance', 'Insurance'],
    ['other', 'Other'],
  ],
};

export const DOCUMENT_UPLOAD = {
  maxFileBytes: 25 * 1024 * 1024,
  maxFiles: 40,
  acceptedExtensions: ['pdf', 'jpg', 'jpeg', 'png', 'tif', 'tiff', 'doc', 'docx', 'xls', 'xlsx', 'heic'],
};

export const LIMITS = {
  text: 200,
  longText: 4000,
  incomeStreams: 12,
  assetSources: 12,
};

// ── Empty submission (form state) ───────────────────────────────────────────

const person = () => ({ name: '', email: '', phone: '' });
const contact = () => ({ selected: 'yes', company: '', contact: '', phone: '', email: '' });
const agent = () => ({ name: '', license: '', phone: '', email: '', brokerage: '', brokerageLicense: '' });

export function newIncomeStream(borrower = 'borrower') {
  return {
    id: randomId('inc'),
    borrower,
    incomeType: '',
    employerOrSource: '',
    loStatedMonthlyIncome: '',
    calculationBasis: '',
    documentsIncluded: [],
    notes: '',
  };
}

export function newAssetSource() {
  return { id: randomId('ast'), sourceType: '', nameOrInstitution: '', accountReference: '', amount: '', notes: '' };
}

export function emptySubmission() {
  return {
    schemaVersion: SCHEMA_VERSION,
    submissionId: randomId('sub'),
    loanOfficer: { name: '', email: '', phone: '', company: '', nmls: '', dateSubmitted: todayIso() },
    borrower: person(),
    hasCoBorrower: 'no',
    coBorrower: person(),
    loan: {
      investor: '',
      propertyAddress: '',
      expectedClosingDate: '',
      loanAmount: '',
      interestRate: '',
      ltv: '',
      cltv: '',
      occupancy: '',
      transactionType: '',
      program: '',
      conventionalAgency: '',
      programOther: '',
      aus: '',
      refinanceType: '',
      homeType: '',
      homeTypeOther: '',
    },
    fees: {
      channel: '',
      compensation: '',
      lpComp: '',
      box1: '',
      discountPoints: '',
      credits: '',
      creditReportFee: '',
      processingFee: '',
      lenderBuyingOutFee: '',
      buyoutNotes: '',
    },
    appraisal: { orderTiming: '', notes: '' },
    parties: {
      nonOccupantCoBorrower: '',
      nonBorrowingTitleParty: { applies: 'no', name: '', email: '', phone: '', willBeOnTitle: '' },
    },
    setup: { pmi: '', subordinationRequired: '', loanLocked: '', escrowWaiver: '' },
    communicationPreferences: [],
    hoa: { present: '', company: '', phone: '', contact: '', email: '', condoQuestionnaireStatus: '' },
    income: [newIncomeStream('borrower')],
    credit: {
      borrower: { status: [], omittedDebtsNotes: '' },
      coBorrower: { status: [], omittedDebtsNotes: '' },
    },
    assets: [newAssetSource()],
    title: contact(),
    insurance: contact(),
    agents: { listing: agent(), buyer: agent() },
    notes: '',
    documents: [],
    website: '', // honeypot — must stay empty
  };
}

// ── Helpers ─────────────────────────────────────────────────────────────────

export function randomId(prefix) {
  const bytes = new Uint8Array(12);
  if (typeof globalThis.crypto?.getRandomValues === 'function') {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  return `${prefix}_${Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')}`;
}

export function todayIso(date = new Date()) {
  const tz = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - tz).toISOString().slice(0, 10);
}

export function isRefinance(sub) {
  return String(sub?.loan?.transactionType || '').startsWith('refinance');
}

export function isPurchase(sub) {
  return sub?.loan?.transactionType === 'purchase';
}

export function ausOptionsFor(program) {
  const all = OPTIONS.aus;
  const allow = {
    conventional: ['du', 'lpa', 'manual', 'other'],
    fha: ['total', 'du', 'lpa', 'manual', 'other'],
    va: ['va_aus', 'du', 'lpa', 'manual', 'other'],
    usda: ['gus', 'manual', 'other'],
    jumbo: ['du', 'lpa', 'manual', 'other'],
    non_qm: ['manual', 'other'],
    other: ['du', 'lpa', 'total', 'gus', 'va_aus', 'manual', 'other'],
  }[program];
  return allow ? all.filter(([v]) => allow.includes(v)) : all;
}

export function refinanceOptionsFor(program) {
  const all = OPTIONS.refinanceType;
  const allow = { fha: ['fha_streamline', 'standard', 'other'], va: ['va_irrrl', 'standard', 'other'] }[program];
  return allow ? all.filter(([v]) => allow.includes(v)) : all.filter(([v]) => v === 'standard' || v === 'other');
}

export function labelFor(group, value) {
  const hit = (OPTIONS[group] || []).find(([v]) => v === value);
  return hit ? hit[1] : value || '';
}

export function formatPhone(raw) {
  const digits = String(raw || '').replace(/\D/g, '').replace(/^1(?=\d{10}$)/, '');
  if (digits.length !== 10) return String(raw || '').trim();
  return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
}

export function formatMoney(value) {
  const n = Number(String(value ?? '').replace(/[^0-9.]/g, ''));
  if (!Number.isFinite(n) || String(value ?? '').trim() === '') return '';
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const SSN_RE = /\b\d{3}-\d{2}-\d{4}\b/;
// Contiguous digit runs of 8+ that are not phone-shaped (10–11), or 12+ digits joined by spaces/dashes (card / account numbers).
const DIGIT_RUN_RE = /\d{8,}/g;
const GROUPED_DIGITS_RE = /(?:\d[ -]?){12,}\d/;
const ID_RE = /^sub_[0-9a-f]{24}$/;

export function looksLikeAccountNumber(value) {
  const runs = String(value || '').match(DIGIT_RUN_RE) || [];
  if (runs.some((r) => r.length !== 10 && r.length !== 11)) return true;
  return GROUPED_DIGITS_RE.test(String(value || ''));
}

function longestDigitRun(value) {
  return Math.max(0, ...(String(value || '').match(/\d+/g) || []).map((r) => r.length));
}

function text(v) {
  return typeof v === 'string' ? v.trim() : '';
}

function phoneOk(v) {
  const digits = String(v || '').replace(/\D/g, '');
  return digits.length === 10 || digits.length === 11;
}

function numberOk(v, { max } = {}) {
  const s = String(v ?? '').replace(/[$,%\s]/g, '');
  if (s === '') return true;
  const n = Number(s);
  return Number.isFinite(n) && n >= 0 && (max === undefined || n <= max);
}

function optionOk(group, v) {
  return v === '' || (OPTIONS[group] || []).some(([key]) => key === v);
}

// ── Validation (identical on the client and the server) ─────────────────────
//
// errors      -> must be fixed before submitting
// recommended -> highlighted on the review screen, never blocking

export function validateSubmission(sub) {
  const errors = {};
  const recommended = [];
  const err = (path, msg) => {
    if (!errors[path]) errors[path] = msg;
  };
  const rec = (path, msg) => recommended.push({ path, message: msg });

  if (!sub || typeof sub !== 'object' || Array.isArray(sub)) return { errors: { form: 'Invalid submission' }, recommended };
  if (sub.schemaVersion !== SCHEMA_VERSION) err('schemaVersion', `Unsupported schema version (expected ${SCHEMA_VERSION})`);
  if (!ID_RE.test(String(sub.submissionId || ''))) err('submissionId', 'Invalid submission id');

  // Anything that looks like a full SSN or a long account/card number is rejected wherever it appears.
  const sensitive = findSensitiveStrings(sub);
  for (const path of sensitive) err(path, 'Do not enter full SSNs or full account numbers. Use last 4 digits or a nickname.');

  const lo = sub.loanOfficer || {};
  if (!text(lo.name)) err('loanOfficer.name', 'Loan officer name is required');
  if (!text(lo.email)) err('loanOfficer.email', 'Loan officer email is required');
  else if (!EMAIL_RE.test(text(lo.email))) err('loanOfficer.email', 'Enter a valid email address');
  if (!text(lo.phone)) err('loanOfficer.phone', 'Loan officer phone is required');
  else if (!phoneOk(lo.phone)) err('loanOfficer.phone', 'Enter a 10-digit phone number');
  if (!text(lo.company)) err('loanOfficer.company', 'Company / brokerage is required');
  if (text(lo.dateSubmitted) && !DATE_RE.test(text(lo.dateSubmitted))) err('loanOfficer.dateSubmitted', 'Enter a valid date');

  const b = sub.borrower || {};
  if (!text(b.name)) err('borrower.name', 'Borrower full name is required');
  if (text(b.email) && !EMAIL_RE.test(text(b.email))) err('borrower.email', 'Enter a valid email address');
  if (text(b.phone) && !phoneOk(b.phone)) err('borrower.phone', 'Enter a 10-digit phone number');
  if (!text(b.email) && !text(b.phone)) rec('borrower.email', 'Borrower email or phone helps processing reach them quickly');

  if (!['yes', 'no'].includes(sub.hasCoBorrower)) err('hasCoBorrower', 'Tell us whether there is a co-borrower');
  if (sub.hasCoBorrower === 'yes') {
    const c = sub.coBorrower || {};
    if (!text(c.name)) err('coBorrower.name', 'Co-borrower full name is required');
    if (text(c.email) && !EMAIL_RE.test(text(c.email))) err('coBorrower.email', 'Enter a valid email address');
    if (text(c.phone) && !phoneOk(c.phone)) err('coBorrower.phone', 'Enter a 10-digit phone number');
  }

  const loan = sub.loan || {};
  if (!text(loan.propertyAddress)) err('loan.propertyAddress', 'Property address is required');
  if (!text(loan.loanAmount)) err('loan.loanAmount', 'Loan amount is required');
  else if (!numberOk(loan.loanAmount)) err('loan.loanAmount', 'Enter a valid amount');
  if (!numberOk(loan.interestRate, { max: 30 })) err('loan.interestRate', 'Enter a valid rate');
  if (!numberOk(loan.ltv, { max: 200 })) err('loan.ltv', 'Enter a valid LTV');
  if (!numberOk(loan.cltv, { max: 200 })) err('loan.cltv', 'Enter a valid CLTV');
  if (text(loan.expectedClosingDate) && !DATE_RE.test(text(loan.expectedClosingDate))) err('loan.expectedClosingDate', 'Enter a valid date');
  if (!loan.occupancy) err('loan.occupancy', 'Select the occupancy');
  else if (!optionOk('occupancy', loan.occupancy)) err('loan.occupancy', 'Select a valid option');
  if (!loan.transactionType) err('loan.transactionType', 'Select the transaction type');
  else if (!optionOk('transactionType', loan.transactionType)) err('loan.transactionType', 'Select a valid option');
  if (!loan.program) err('loan.program', 'Select the loan program');
  else if (!optionOk('program', loan.program)) err('loan.program', 'Select a valid option');
  if (loan.program === 'conventional' && !optionOk('conventionalAgency', loan.conventionalAgency)) err('loan.conventionalAgency', 'Select a valid option');
  if (loan.program === 'other' && !text(loan.programOther)) err('loan.programOther', 'Tell us the program');
  if (loan.aus && !ausOptionsFor(loan.program).some(([v]) => v === loan.aus)) err('loan.aus', 'That AUS does not apply to the selected program');
  if (isRefinance(sub) && loan.refinanceType && !refinanceOptionsFor(loan.program).some(([v]) => v === loan.refinanceType)) err('loan.refinanceType', 'Select a valid refinance type');
  if (!optionOk('homeType', loan.homeType)) err('loan.homeType', 'Select a valid option');
  if (loan.homeType === 'other' && !text(loan.homeTypeOther)) err('loan.homeTypeOther', 'Describe the home type');
  if (!text(loan.investor)) rec('loan.investor', 'Investor / lender');
  if (!text(loan.expectedClosingDate)) rec('loan.expectedClosingDate', 'Expected closing date');
  if (!loan.aus) rec('loan.aus', 'Underwriting / AUS');
  if (!loan.homeType) rec('loan.homeType', 'Type of home');

  const fees = sub.fees || {};
  if (!optionOk('channel', fees.channel)) err('fees.channel', 'Select a valid option');
  if (fees.channel === 'brokered' && !optionOk('compensation', fees.compensation)) err('fees.compensation', 'Select a valid option');
  for (const k of ['box1', 'credits', 'creditReportFee', 'processingFee']) if (!numberOk(fees[k])) err(`fees.${k}`, 'Enter a valid amount');
  for (const k of ['lpComp', 'discountPoints']) if (!numberOk(fees[k], { max: 100 })) err(`fees.${k}`, 'Enter a valid percentage');
  if (!optionOk('yesNo', fees.lenderBuyingOutFee)) err('fees.lenderBuyingOutFee', 'Select a valid option');
  if (!fees.channel) rec('fees.channel', 'Brokered or correspondent');
  if (!fees.lenderBuyingOutFee) rec('fees.lenderBuyingOutFee', 'Is the lender buying out the fee?');

  const ap = sub.appraisal || {};
  if (!optionOk('appraisalTiming', ap.orderTiming)) err('appraisal.orderTiming', 'Select a valid option');
  if (!ap.orderTiming) rec('appraisal.orderTiming', 'When to order the appraisal');

  const parties = sub.parties || {};
  if (!optionOk('yesNo', parties.nonOccupantCoBorrower)) err('parties.nonOccupantCoBorrower', 'Select a valid option');
  const tp = parties.nonBorrowingTitleParty || {};
  if (tp.applies === 'yes') {
    if (!text(tp.name)) err('parties.nonBorrowingTitleParty.name', 'Full name is required when this applies');
    if (text(tp.email) && !EMAIL_RE.test(text(tp.email))) err('parties.nonBorrowingTitleParty.email', 'Enter a valid email address');
    if (text(tp.phone) && !phoneOk(tp.phone)) err('parties.nonBorrowingTitleParty.phone', 'Enter a 10-digit phone number');
    if (!optionOk('yesNo', tp.willBeOnTitle) || !tp.willBeOnTitle) err('parties.nonBorrowingTitleParty.willBeOnTitle', 'Tell us whether they will be on title');
    if (!text(tp.email) && !text(tp.phone)) rec('parties.nonBorrowingTitleParty.email', 'Email or phone for the person on title');
  }

  const setup = sub.setup || {};
  if (!optionOk('yesNoNa', setup.pmi)) err('setup.pmi', 'Select a valid option');
  for (const k of ['subordinationRequired', 'loanLocked', 'escrowWaiver']) if (!optionOk('yesNo', setup[k])) err(`setup.${k}`, 'Select a valid option');
  if (!setup.loanLocked) rec('setup.loanLocked', 'Loan locked?');
  const prefs = Array.isArray(sub.communicationPreferences) ? sub.communicationPreferences : null;
  if (!prefs || prefs.some((p) => !optionOk('communicationPreferences', p) || p === '')) err('communicationPreferences', 'Select valid communication preferences');
  else if (prefs.length === 0) rec('communicationPreferences', 'Who processing may contact directly');

  const hoa = sub.hoa || {};
  if (!optionOk('yesNoUnknown', hoa.present)) err('hoa.present', 'Select a valid option');
  if (hoa.present === 'yes') {
    if (text(hoa.email) && !EMAIL_RE.test(text(hoa.email))) err('hoa.email', 'Enter a valid email address');
    if (text(hoa.phone) && !phoneOk(hoa.phone)) err('hoa.phone', 'Enter a 10-digit phone number');
    if (!optionOk('condoQuestionnaireStatus', hoa.condoQuestionnaireStatus)) err('hoa.condoQuestionnaireStatus', 'Select a valid option');
    if (!text(hoa.company)) rec('hoa.company', 'HOA company');
  }

  const income = Array.isArray(sub.income) ? sub.income : null;
  if (!income) err('income', 'Income must be a list');
  else {
    if (income.length > LIMITS.incomeStreams) err('income', `Up to ${LIMITS.incomeStreams} income streams`);
    income.forEach((s, i) => {
      if (!['borrower', 'co_borrower'].includes(s?.borrower)) err(`income.${i}.borrower`, 'Select the borrower');
      if (s?.borrower === 'co_borrower' && sub.hasCoBorrower !== 'yes') err(`income.${i}.borrower`, 'There is no co-borrower on this loan');
      if (!optionOk('incomeType', s?.incomeType)) err(`income.${i}.incomeType`, 'Select a valid income type');
      if (!numberOk(s?.loStatedMonthlyIncome)) err(`income.${i}.loStatedMonthlyIncome`, 'Enter a valid amount');
      if (!optionOk('calculationBasis', s?.calculationBasis)) err(`income.${i}.calculationBasis`, 'Select a valid option');
      const docs = Array.isArray(s?.documentsIncluded) ? s.documentsIncluded : null;
      if (!docs || docs.some((d) => !optionOk('incomeDocuments', d) || d === '')) err(`income.${i}.documentsIncluded`, 'Select valid documents');
      const filled = text(s?.employerOrSource) || text(s?.loStatedMonthlyIncome) || s?.incomeType;
      if (filled && !s?.incomeType) err(`income.${i}.incomeType`, 'Select the income type');
    });
    if (!income.some((s) => s?.incomeType)) rec('income', 'At least one income stream for the borrower');
  }

  const credit = sub.credit || {};
  for (const who of ['borrower', 'coBorrower']) {
    const c = credit[who] || {};
    const st = Array.isArray(c.status) ? c.status : null;
    if (!st || st.some((v) => !optionOk('creditStatus', v) || v === '')) err(`credit.${who}.status`, 'Select valid options');
    else if (st.includes('tradeline_omitted') && !text(c.omittedDebtsNotes)) err(`credit.${who}.omittedDebtsNotes`, 'If any debts are omitted, please explain');
    else if (st.includes('other_issue') && !text(c.omittedDebtsNotes)) err(`credit.${who}.omittedDebtsNotes`, 'Please explain the credit issue');
  }
  if (!(credit.borrower?.status || []).length) rec('credit.borrower.status', "Borrower's credit status");

  const assets = Array.isArray(sub.assets) ? sub.assets : null;
  if (!assets) err('assets', 'Funds to close must be a list');
  else {
    if (assets.length > LIMITS.assetSources) err('assets', `Up to ${LIMITS.assetSources} sources`);
    assets.forEach((a, i) => {
      if (!optionOk('fundsSourceType', a?.sourceType)) err(`assets.${i}.sourceType`, 'Select a valid source');
      if (!numberOk(a?.amount)) err(`assets.${i}.amount`, 'Enter a valid amount');
      const ref = text(a?.accountReference);
      if (ref && longestDigitRun(ref) >= 5) err(`assets.${i}.accountReference`, 'Use the last 4 digits or a nickname, not the full account number');
      const filled = text(a?.nameOrInstitution) || text(a?.amount) || ref;
      if (filled && !a?.sourceType) err(`assets.${i}.sourceType`, 'Select the source type');
    });
    if (isPurchase(sub) && !assets.some((a) => a?.sourceType)) rec('assets', 'Where the down payment / cash to close comes from');
  }

  for (const who of ['title', 'insurance']) {
    const c = sub[who] || {};
    if (!['yes', 'no'].includes(c.selected)) err(`${who}.selected`, 'Select a valid option');
    if (c.selected === 'yes') {
      if (text(c.email) && !EMAIL_RE.test(text(c.email))) err(`${who}.email`, 'Enter a valid email address');
      if (text(c.phone) && !phoneOk(c.phone)) err(`${who}.phone`, 'Enter a 10-digit phone number');
      if (!text(c.company)) rec(`${who}.company`, who === 'title' ? 'Title company' : 'Insurance company');
    }
  }

  if (isPurchase(sub)) {
    for (const side of ['listing', 'buyer']) {
      const a = sub.agents?.[side] || {};
      if (text(a.email) && !EMAIL_RE.test(text(a.email))) err(`agents.${side}.email`, 'Enter a valid email address');
      if (text(a.phone) && !phoneOk(a.phone)) err(`agents.${side}.phone`, 'Enter a 10-digit phone number');
      if (!text(a.name)) rec(`agents.${side}.name`, side === 'listing' ? 'Listing agent' : "Buyer's agent");
    }
  }

  const docs = Array.isArray(sub.documents) ? sub.documents : null;
  if (!docs) err('documents', 'Documents must be a list');
  else {
    if (docs.length > DOCUMENT_UPLOAD.maxFiles) err('documents', `Up to ${DOCUMENT_UPLOAD.maxFiles} files`);
    docs.forEach((d, i) => {
      if (!optionOk('documentCategory', d?.category) || !d?.category) err(`documents.${i}.category`, 'Select a document category');
      if (!text(d?.fileName)) err(`documents.${i}.fileName`, 'File name missing');
      if (!(Number(d?.sizeBytes) >= 0 && Number(d?.sizeBytes) <= DOCUMENT_UPLOAD.maxFileBytes)) err(`documents.${i}.sizeBytes`, 'File is too large');
      const ext = text(d?.fileName).toLowerCase().split('.').pop();
      if (!DOCUMENT_UPLOAD.acceptedExtensions.includes(ext)) err(`documents.${i}.fileName`, 'File type not accepted');
    });
    if (docs.length === 0) rec('documents', 'Documents (1003, credit, AUS, income, assets)');
  }

  // Length caps everywhere.
  walkStrings(sub, (path, value) => {
    const cap = ['notes', 'buyoutNotes', 'omittedDebtsNotes', 'appraisal.notes'].some((k) => path.endsWith(k)) ? LIMITS.longText : LIMITS.text;
    if (value.length > cap) err(path, `Use ${cap.toLocaleString()} characters or fewer`);
  });

  if (text(sub.website)) err('website', 'Spam check failed');

  return { errors, recommended };
}

export function findSensitiveStrings(sub) {
  const hits = [];
  walkStrings(sub, (path, value) => {
    if (path === 'submissionId' || path.endsWith('.id')) return;
    if (SSN_RE.test(value)) hits.push(path);
    else if (!isPhonePath(path) && !isAmountPath(path) && looksLikeAccountNumber(value)) hits.push(path);
  });
  return hits;
}

function isPhonePath(path) {
  return /phone$/i.test(path);
}

function isAmountPath(path) {
  return /(amount|loanAmount|income|fee|box1|credits|sizeBytes)$/i.test(path);
}

export function walkStrings(value, visit, path = '') {
  if (typeof value === 'string') {
    visit(path, value);
  } else if (Array.isArray(value)) {
    value.forEach((v, i) => walkStrings(v, visit, path ? `${path}.${i}` : String(i)));
  } else if (value && typeof value === 'object') {
    for (const [k, v] of Object.entries(value)) walkStrings(v, visit, path ? `${path}.${k}` : k);
  }
}

// ── Normalized payload (what leaves the browser and what Flo receives) ──────

const num = (v) => {
  const s = String(v ?? '').replace(/[$,%\s]/g, '');
  return s === '' ? null : Number(s);
};

function personOut(p, role) {
  return { role, name: text(p?.name), email: text(p?.email).toLowerCase(), phone: formatPhone(p?.phone) };
}

function contactOut(c) {
  const selected = c?.selected === 'yes';
  return {
    selected,
    company: selected ? text(c?.company) : '',
    contact: selected ? text(c?.contact) : '',
    phone: selected ? formatPhone(c?.phone) : '',
    email: selected ? text(c?.email).toLowerCase() : '',
  };
}

function agentOut(a) {
  return {
    name: text(a?.name),
    license: text(a?.license),
    phone: formatPhone(a?.phone),
    email: text(a?.email).toLowerCase(),
    brokerage: text(a?.brokerage),
    brokerageLicense: text(a?.brokerageLicense),
  };
}

export function toPayload(sub, { submittedAt = new Date().toISOString() } = {}) {
  const loan = sub.loan || {};
  const fees = sub.fees || {};
  const purchase = isPurchase(sub);
  const refi = isRefinance(sub);
  const tp = sub.parties?.nonBorrowingTitleParty || {};
  const hoaYes = sub.hoa?.present === 'yes';
  const borrowers = [personOut(sub.borrower, 'borrower')];
  if (sub.hasCoBorrower === 'yes') borrowers.push(personOut(sub.coBorrower, 'co_borrower'));
  return {
    schemaVersion: SCHEMA_VERSION,
    submissionId: sub.submissionId,
    submittedAt,
    source: SOURCE,
    loanOfficer: {
      name: text(sub.loanOfficer?.name),
      email: text(sub.loanOfficer?.email).toLowerCase(),
      phone: formatPhone(sub.loanOfficer?.phone),
      company: text(sub.loanOfficer?.company),
      nmls: text(sub.loanOfficer?.nmls),
      dateSubmitted: text(sub.loanOfficer?.dateSubmitted) || todayIso(),
    },
    borrowers,
    loan: {
      investor: text(loan.investor),
      propertyAddress: text(loan.propertyAddress),
      expectedClosingDate: text(loan.expectedClosingDate) || null,
      loanAmount: num(loan.loanAmount),
      interestRate: num(loan.interestRate),
      ltv: num(loan.ltv),
      cltv: num(loan.cltv),
      occupancy: loan.occupancy || null,
      transactionType: loan.transactionType || null,
      program: loan.program || null,
      conventionalAgency: loan.program === 'conventional' ? loan.conventionalAgency || null : null,
      programOther: loan.program === 'other' ? text(loan.programOther) : '',
      aus: loan.aus || null,
      refinanceType: refi ? loan.refinanceType || null : null,
      homeType: loan.homeType || null,
      homeTypeOther: loan.homeType === 'other' ? text(loan.homeTypeOther) : '',
    },
    fees: {
      channel: fees.channel || null,
      compensation: fees.channel === 'brokered' ? fees.compensation || null : null,
      originationFees: { lpCompPercent: num(fees.lpComp), box1: num(fees.box1), discountPoints: num(fees.discountPoints), credits: num(fees.credits) },
      thirdPartyFees: { creditReportFee: num(fees.creditReportFee), processingFee: num(fees.processingFee) },
      lenderBuyingOutFee: fees.lenderBuyingOutFee || null,
      buyoutNotes: fees.lenderBuyingOutFee === 'yes' ? text(fees.buyoutNotes) : '',
    },
    appraisal: { orderTiming: sub.appraisal?.orderTiming || null, notes: text(sub.appraisal?.notes) },
    parties: {
      nonOccupantCoBorrower: sub.parties?.nonOccupantCoBorrower || null,
      nonBorrowingTitleParty:
        tp.applies === 'yes'
          ? { applies: true, name: text(tp.name), email: text(tp.email).toLowerCase(), phone: formatPhone(tp.phone), willBeOnTitle: tp.willBeOnTitle || null }
          : { applies: false, name: '', email: '', phone: '', willBeOnTitle: null },
    },
    setup: {
      pmi: sub.setup?.pmi || null,
      subordinationRequired: sub.setup?.subordinationRequired || null,
      loanLocked: sub.setup?.loanLocked || null,
      escrowWaiver: sub.setup?.escrowWaiver || null,
    },
    communicationPreferences: Array.isArray(sub.communicationPreferences) ? [...sub.communicationPreferences] : [],
    hoa: {
      present: sub.hoa?.present || null,
      company: hoaYes ? text(sub.hoa?.company) : '',
      phone: hoaYes ? formatPhone(sub.hoa?.phone) : '',
      contact: hoaYes ? text(sub.hoa?.contact) : '',
      email: hoaYes ? text(sub.hoa?.email).toLowerCase() : '',
      condoQuestionnaireStatus: hoaYes ? sub.hoa?.condoQuestionnaireStatus || null : null,
    },
    income: (sub.income || [])
      .filter((s) => s?.incomeType)
      .map((s) => ({
        borrower: s.borrower,
        incomeType: s.incomeType,
        employerOrSource: text(s.employerOrSource),
        loStatedMonthlyIncome: num(s.loStatedMonthlyIncome),
        calculationBasis: s.calculationBasis || null,
        documentsIncluded: Array.isArray(s.documentsIncluded) ? [...s.documentsIncluded] : [],
        notes: text(s.notes),
        verified: false, // LO-stated; Flo/Malcolm/Sage compute the qualifying figure later
      })),
    credit: {
      borrower: { status: [...(sub.credit?.borrower?.status || [])], omittedDebtsNotes: text(sub.credit?.borrower?.omittedDebtsNotes) },
      coBorrower:
        sub.hasCoBorrower === 'yes'
          ? { status: [...(sub.credit?.coBorrower?.status || [])], omittedDebtsNotes: text(sub.credit?.coBorrower?.omittedDebtsNotes) }
          : { status: [], omittedDebtsNotes: '' },
    },
    assets: (sub.assets || [])
      .filter((a) => a?.sourceType)
      .map((a) => ({
        sourceType: a.sourceType,
        nameOrInstitution: text(a.nameOrInstitution),
        accountReference: text(a.accountReference),
        amount: num(a.amount),
        notes: text(a.notes),
      })),
    title: contactOut(sub.title),
    insurance: contactOut(sub.insurance),
    agents: purchase ? { listing: agentOut(sub.agents?.listing), buyer: agentOut(sub.agents?.buyer) } : { listing: null, buyer: null },
    notes: text(sub.notes),
    documentRefs: (sub.documents || []).map((d) => ({
      category: d.category,
      fileName: text(d.fileName),
      sizeBytes: Number(d.sizeBytes) || 0,
      contentType: text(d.contentType),
      status: 'pending_secure_upload',
    })),
  };
}

// ── Review-screen summary (also used for the confirmation) ──────────────────

export function summarize(sub) {
  const p = toPayload(sub, { submittedAt: '' });
  const money = (v) => (v === null ? '—' : formatMoney(v));
  const pct = (v) => (v === null ? '—' : `${v}%`);
  const yn = (v) => (v ? labelFor('yesNo', v) || labelFor('yesNoNa', v) || labelFor('yesNoUnknown', v) : '—');
  const or = (v) => (v ? v : '—');
  const groups = [
    {
      title: 'Borrowers',
      rows: p.borrowers.map((b) => [b.role === 'borrower' ? 'Borrower' : 'Co-borrower', [b.name, b.email, b.phone].filter(Boolean).join(' · ') || '—']),
    },
    {
      title: 'Loan',
      rows: [
        ['Property', or(p.loan.propertyAddress)],
        ['Investor / lender', or(p.loan.investor)],
        ['Loan amount', money(p.loan.loanAmount)],
        ['Rate / LTV / CLTV', `${pct(p.loan.interestRate)} · ${pct(p.loan.ltv)} · ${pct(p.loan.cltv)}`],
        ['Expected closing', or(p.loan.expectedClosingDate)],
        ['Occupancy', or(labelFor('occupancy', p.loan.occupancy))],
      ],
    },
    {
      title: 'Program',
      rows: [
        ['Transaction', or(labelFor('transactionType', p.loan.transactionType))],
        ['Program', [labelFor('program', p.loan.program), labelFor('conventionalAgency', p.loan.conventionalAgency), p.loan.programOther].filter(Boolean).join(' · ') || '—'],
        ['AUS', or(labelFor('aus', p.loan.aus))],
        ...(p.loan.refinanceType ? [['Refinance type', labelFor('refinanceType', p.loan.refinanceType)]] : []),
        ['Home type', [labelFor('homeType', p.loan.homeType), p.loan.homeTypeOther].filter(Boolean).join(' · ') || '—'],
        ['Channel', [labelFor('channel', p.fees.channel), labelFor('compensation', p.fees.compensation)].filter(Boolean).join(' · ') || '—'],
        ['Lender buying out the fee', p.fees.lenderBuyingOutFee ? `${yn(p.fees.lenderBuyingOutFee)}${p.fees.buyoutNotes ? ` — ${p.fees.buyoutNotes}` : ''}` : '—'],
        ['PMI / Subordination / Locked / Escrow waiver', `${yn(p.setup.pmi)} · ${yn(p.setup.subordinationRequired)} · ${yn(p.setup.loanLocked)} · ${yn(p.setup.escrowWaiver)}`],
      ],
    },
    {
      title: 'Income (LO-stated)',
      rows: p.income.length
        ? p.income.map((s) => [
            `${s.borrower === 'borrower' ? 'Borrower' : 'Co-borrower'} · ${labelFor('incomeType', s.incomeType)}`,
            [s.employerOrSource, s.loStatedMonthlyIncome === null ? '' : `${money(s.loStatedMonthlyIncome)}/mo`, labelFor('calculationBasis', s.calculationBasis)].filter(Boolean).join(' · ') || '—',
          ])
        : [['Income', '—']],
    },
    {
      title: 'Assets / funds to close',
      rows: p.assets.length
        ? p.assets.map((a) => [labelFor('fundsSourceType', a.sourceType), [a.nameOrInstitution, a.accountReference ? `ref ${a.accountReference}` : '', money(a.amount)].filter(Boolean).join(' · ') || '—'])
        : [['Sources', '—']],
    },
    {
      title: 'Orders',
      rows: [
        ['Appraisal', or(labelFor('appraisalTiming', p.appraisal.orderTiming))],
        ['HOA', p.hoa.present === 'yes' ? [p.hoa.company, p.hoa.contact, p.hoa.phone, p.hoa.email].filter(Boolean).join(' · ') || 'Yes' : or(labelFor('yesNoUnknown', p.hoa.present))],
        ...(p.hoa.condoQuestionnaireStatus ? [['Condo questionnaire', labelFor('condoQuestionnaireStatus', p.hoa.condoQuestionnaireStatus)]] : []),
        ['Processing may contact', p.communicationPreferences.map((c) => labelFor('communicationPreferences', c)).join(', ') || '—'],
      ],
    },
    {
      title: 'Title / Insurance',
      rows: [
        ['Title', p.title.selected ? [p.title.company, p.title.contact, p.title.phone, p.title.email].filter(Boolean).join(' · ') || '—' : 'Not selected yet'],
        ['Insurance', p.insurance.selected ? [p.insurance.company, p.insurance.contact, p.insurance.phone, p.insurance.email].filter(Boolean).join(' · ') || '—' : 'Not selected yet'],
        ['Non-borrowing spouse / individual on title', p.parties.nonBorrowingTitleParty.applies ? [p.parties.nonBorrowingTitleParty.name, p.parties.nonBorrowingTitleParty.email, p.parties.nonBorrowingTitleParty.phone, `on title: ${yn(p.parties.nonBorrowingTitleParty.willBeOnTitle)}`].filter(Boolean).join(' · ') : 'Not applicable'],
      ],
    },
    ...(p.agents.listing
      ? [
          {
            title: 'Agents',
            rows: [
              ['Listing agent', [p.agents.listing.name, p.agents.listing.phone, p.agents.listing.email, p.agents.listing.brokerage].filter(Boolean).join(' · ') || '—'],
              ["Buyer's agent", [p.agents.buyer.name, p.agents.buyer.phone, p.agents.buyer.email, p.agents.buyer.brokerage].filter(Boolean).join(' · ') || '—'],
            ],
          },
        ]
      : []),
    {
      title: 'Credit',
      rows: [
        ['Borrower', [p.credit.borrower.status.map((s) => labelFor('creditStatus', s)).join(', '), p.credit.borrower.omittedDebtsNotes].filter(Boolean).join(' — ') || '—'],
        ...(p.borrowers.length > 1 ? [['Co-borrower', [p.credit.coBorrower.status.map((s) => labelFor('creditStatus', s)).join(', '), p.credit.coBorrower.omittedDebtsNotes].filter(Boolean).join(' — ') || '—']] : []),
      ],
    },
    { title: 'Notes', rows: [['Processing notes', or(p.notes)]] },
    {
      title: 'Documents',
      rows: p.documentRefs.length ? p.documentRefs.map((d) => [labelFor('documentCategory', d.category), d.fileName]) : [['Documents', 'None attached yet']],
    },
  ];
  return groups;
}

export function primaryBorrowerName(sub) {
  return text(sub?.borrower?.name);
}
