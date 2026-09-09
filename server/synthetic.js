// Synthetic loan submission used by tests and manual QA. Never real borrower data.
import { emptySubmission } from '../shared/loanSubmission.js';

export function syntheticSubmission(overrides = {}) {
  const s = emptySubmission();
  s.loanOfficer = { name: 'Matt Combs', email: 'matt@synthetic-mortgage.test', phone: '9045550101', company: 'Synthetic Mortgage Group', nmls: '123456', dateSubmitted: '2026-09-09' };
  s.borrower = { name: 'Ariana Justinvil-Synthetic', email: 'ariana@synthetic.test', phone: '(904) 555-0102' };
  s.loan = { ...s.loan, investor: 'PRMG', propertyAddress: '123 Synthetic Way, Jacksonville, FL 32256', expectedClosingDate: '2026-09-23', loanAmount: '314000', interestRate: '6.25', ltv: '95.15', occupancy: 'primary', transactionType: 'purchase', program: 'fha', aus: 'total', homeType: 'single_family' };
  s.fees = { ...s.fees, channel: 'brokered', compensation: 'lender_paid', lpComp: '2.75', creditReportFee: '152', processingFee: '995', lenderBuyingOutFee: 'no' };
  s.appraisal = { orderTiming: 'prior_to_inspection', notes: '' };
  s.parties.nonOccupantCoBorrower = 'no';
  s.setup = { pmi: 'yes', subordinationRequired: 'no', loanLocked: 'no', escrowWaiver: 'no' };
  s.communicationPreferences = ['realtor_voice', 'borrower_email_cc_lo'];
  s.hoa = { ...s.hoa, present: 'no' };
  s.income = [{ ...s.income[0], incomeType: 'w2', employerOrSource: 'Synthetic Health System', loStatedMonthlyIncome: '7842', calculationBasis: 'current_income', documentsIncluded: ['paystubs', 'w2s'] }];
  s.credit.borrower = { status: ['as_per_credit_pull'], omittedDebtsNotes: '' };
  s.assets = [{ ...s.assets[0], sourceType: 'borrower_bank_account', nameOrInstitution: 'Synthetic Credit Union', accountReference: 'last 4: 1234', amount: '18500' }];
  s.title = { selected: 'yes', company: 'Hawes Law Firm (synthetic)', contact: '', phone: '6785550103', email: 'closings@synthetic-title.test' };
  s.insurance = { selected: 'no', company: '', contact: '', phone: '', email: '' };
  s.agents.listing = { ...s.agents.listing, name: 'Michael Capo (synthetic)', license: '267977', phone: '4045550104', email: 'listing@synthetic.test', brokerage: 'Synthetic Realty', brokerageLicense: '62466' };
  s.notes = 'This is a rush file, closing in 2 weeks.';
  return deepMerge(s, overrides);
}

function deepMerge(base, patch) {
  for (const [k, v] of Object.entries(patch)) {
    if (v && typeof v === 'object' && !Array.isArray(v) && base[k] && typeof base[k] === 'object') deepMerge(base[k], v);
    else base[k] = v;
  }
  return base;
}
