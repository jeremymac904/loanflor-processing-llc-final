import { emptySubmission } from '../../shared/loanSubmission.js';

/** Synthetic demo data (dev only: `?lfDemo=1`). Never real borrower data. */
export function sampleSubmission() {
  const s = emptySubmission();
  s.loanOfficer = { ...s.loanOfficer, name: 'Matt Combs', email: 'matt@synthetic-mortgage.test', phone: '(904) 555-0101', company: 'Synthetic Mortgage Group', nmls: '123456' };
  s.borrower = { name: 'Ariana Justinvil-Synthetic', email: 'ariana@synthetic.test', phone: '(904) 555-0102' };
  s.loan = { ...s.loan, investor: 'PRMG', propertyAddress: '123 Synthetic Way, Jacksonville, FL 32256', expectedClosingDate: '2026-09-23', loanAmount: '314,000', interestRate: '6.25', ltv: '95.15', occupancy: 'primary', transactionType: 'purchase', program: 'fha', aus: 'total', homeType: 'single_family' };
  s.fees = { ...s.fees, channel: 'brokered', compensation: 'lender_paid', lpComp: '2.75', creditReportFee: '152', processingFee: '995', lenderBuyingOutFee: 'no' };
  s.appraisal = { orderTiming: 'prior_to_inspection', notes: '' };
  s.parties.nonOccupantCoBorrower = 'no';
  s.setup = { pmi: 'yes', subordinationRequired: 'no', loanLocked: 'no', escrowWaiver: 'no' };
  s.communicationPreferences = ['realtor_voice', 'realtor_email_cc_lo', 'borrower_voice', 'borrower_email_cc_lo'];
  s.hoa = { ...s.hoa, present: 'no' };
  s.income = [{ ...s.income[0], incomeType: 'w2', employerOrSource: 'Synthetic Health System', loStatedMonthlyIncome: '7,842', calculationBasis: 'current_income', documentsIncluded: ['paystubs', 'w2s'] }];
  s.credit.borrower = { status: ['as_per_credit_pull'], omittedDebtsNotes: '' };
  s.assets = [{ ...s.assets[0], sourceType: 'borrower_bank_account', nameOrInstitution: 'Synthetic Credit Union', accountReference: 'checking ••1234', amount: '18,500' }];
  s.title = { selected: 'yes', company: 'Hawes Law Firm (synthetic)', contact: '', phone: '(678) 555-0103', email: 'closings@synthetic-title.test' };
  s.insurance = { selected: 'no', company: '', contact: '', phone: '', email: '' };
  s.agents.listing = { name: 'Michael Capo (synthetic)', license: '267977', phone: '(404) 555-0104', email: 'listing@synthetic.test', brokerage: 'Synthetic Realty', brokerageLicense: '62466' };
  s.agents.buyer = { name: 'Taylor Carroll (synthetic)', license: '416149', phone: '(404) 555-0105', email: 'buyer@synthetic.test', brokerage: 'Synthetic Realty', brokerageLicense: '78172' };
  s.notes = 'This is a rush file, closing in 2 weeks.';
  s.documents = [
    { id: 'doc_0123456789abcdef01234567', category: 'loan_application', subcategory: '', borrowerRef: '', fileName: 'synthetic-1003.pdf', sizeBytes: 412_000, contentType: 'application/pdf', status: 'received' },
    { id: 'doc_0123456789abcdef01234568', category: 'income', subcategory: 'paystub', borrowerRef: 'borrower', fileName: 'scan0042.pdf', sizeBytes: 88_000, contentType: 'application/pdf', status: 'received' },
    { id: 'doc_0123456789abcdef01234569', category: 'assets', subcategory: 'bank_statement', borrowerRef: 'borrower', fileName: 'bank_statement_july.pdf', sizeBytes: 240_000, contentType: 'application/pdf', status: 'received' },
  ];
  return s;
}
