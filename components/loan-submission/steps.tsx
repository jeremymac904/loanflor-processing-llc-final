import React, { useRef, useState } from 'react';
import {
  Briefcase,
  Building2,
  ClipboardList,
  CreditCard,
  DollarSign,
  FileUp,
  Home,
  Landmark,
  MessageSquare,
  Plus,
  Receipt,
  Shield,
  Trash2,
  User,
  Users,
  Wallet,
} from 'lucide-react';

import {
  ausOptionsFor,
  DOCUMENT_UPLOAD,
  isPurchase,
  isRefinance,
  labelFor,
  newAssetSource,
  newIncomeStream,
  OPTIONS,
  refinanceOptionsFor,
} from '../../shared/loanSubmission.js';
import {
  CheckboxGroup,
  DateInput,
  EmailInput,
  GhostButton,
  Grid,
  MoneyInput,
  PercentInput,
  PhoneInput,
  RadioGroup,
  SectionTitle,
  Select,
  SubCard,
  TextArea,
  TextInput,
} from './fields';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Submission = any;
export type Errors = Record<string, string>;

export interface StepProps {
  sub: Submission;
  set: (path: string, value: unknown) => void;
  errors: Errors;
}

const icon = (I: React.ComponentType<{ className?: string }>) => <I className="h-4 w-4 text-brand-copper" />;

export function LoanOfficerStep({ sub, set, errors }: StepProps) {
  const lo = sub.loanOfficer;
  return (
    <>
      <SectionTitle icon={icon(User)} title="Loan Officer" blurb="Who is submitting this file. We use this to send updates and questions." />
      <Grid>
        <TextInput id="lo-name" label="Loan officer name" required value={lo.name} onChange={(v) => set('loanOfficer.name', v)} error={errors['loanOfficer.name']} placeholder="Jane Smith" autoComplete="name" />
        <TextInput id="lo-company" label="Company / brokerage" required value={lo.company} onChange={(v) => set('loanOfficer.company', v)} error={errors['loanOfficer.company']} placeholder="ABC Mortgage Group" autoComplete="organization" />
        <EmailInput id="lo-email" label="Loan officer email" required value={lo.email} onChange={(v) => set('loanOfficer.email', v)} error={errors['loanOfficer.email']} />
        <PhoneInput id="lo-phone" label="Loan officer phone" required value={lo.phone} onChange={(v) => set('loanOfficer.phone', v)} error={errors['loanOfficer.phone']} />
        <TextInput id="lo-nmls" label="NMLS #" value={lo.nmls} onChange={(v) => set('loanOfficer.nmls', v)} placeholder="Optional" />
        <DateInput id="lo-date" label="Date submitted" value={lo.dateSubmitted} onChange={(v) => set('loanOfficer.dateSubmitted', v)} error={errors['loanOfficer.dateSubmitted']} hint="Defaults to today." />
      </Grid>
    </>
  );
}

export function BorrowersStep({ sub, set, errors }: StepProps) {
  const hasCo = sub.hasCoBorrower === 'yes';
  return (
    <>
      <SectionTitle icon={icon(Users)} title="Borrowers" blurb="Name, email and phone for each borrower so processing can reach them directly." />
      <div className="space-y-6">
        <SubCard title="Primary borrower">
          <Grid>
            <TextInput id="b-name" label="Full name" required value={sub.borrower.name} onChange={(v) => set('borrower.name', v)} error={errors['borrower.name']} placeholder="First Last" />
            <EmailInput id="b-email" label="Email" value={sub.borrower.email} onChange={(v) => set('borrower.email', v)} error={errors['borrower.email']} />
            <PhoneInput id="b-phone" label="Phone number" value={sub.borrower.phone} onChange={(v) => set('borrower.phone', v)} error={errors['borrower.phone']} />
          </Grid>
        </SubCard>
        <RadioGroup id="has-co" label="Does this loan have a co-borrower?" required value={sub.hasCoBorrower} onChange={(v) => set('hasCoBorrower', v || 'no')} options={OPTIONS.yesNo} error={errors.hasCoBorrower} />
        {hasCo && (
          <SubCard title="Co-borrower">
            <Grid>
              <TextInput id="cb-name" label="Co-borrower full name" required value={sub.coBorrower.name} onChange={(v) => set('coBorrower.name', v)} error={errors['coBorrower.name']} />
              <EmailInput id="cb-email" label="Co-borrower email" value={sub.coBorrower.email} onChange={(v) => set('coBorrower.email', v)} error={errors['coBorrower.email']} />
              <PhoneInput id="cb-phone" label="Co-borrower phone number" value={sub.coBorrower.phone} onChange={(v) => set('coBorrower.phone', v)} error={errors['coBorrower.phone']} />
            </Grid>
          </SubCard>
        )}
      </div>
    </>
  );
}

export function LoanDetailsStep({ sub, set, errors }: StepProps) {
  const loan = sub.loan;
  return (
    <>
      <SectionTitle icon={icon(Home)} title="Loan Details" blurb="The basics of the loan and the property." />
      <Grid>
        <TextInput id="investor" label="Investor / lender" value={loan.investor} onChange={(v) => set('loan.investor', v)} placeholder="e.g. PRMG" className="sm:col-span-2" />
        <TextInput id="address" label="Property address" required value={loan.propertyAddress} onChange={(v) => set('loan.propertyAddress', v)} error={errors['loan.propertyAddress']} placeholder="123 Main St, Jacksonville, FL 32256" autoComplete="street-address" className="sm:col-span-2" />
        <MoneyInput id="amount" label="Loan amount" required value={loan.loanAmount} onChange={(v) => set('loan.loanAmount', v)} error={errors['loan.loanAmount']} />
        <DateInput id="closing" label="Expected closing date" value={loan.expectedClosingDate} onChange={(v) => set('loan.expectedClosingDate', v)} error={errors['loan.expectedClosingDate']} />
        <PercentInput id="rate" label="Interest rate" value={loan.interestRate} onChange={(v) => set('loan.interestRate', v)} error={errors['loan.interestRate']} placeholder="6.25" />
        <div className="grid grid-cols-2 gap-3">
          <PercentInput id="ltv" label="LTV" value={loan.ltv} onChange={(v) => set('loan.ltv', v)} error={errors['loan.ltv']} placeholder="95" />
          <PercentInput id="cltv" label="CLTV" value={loan.cltv} onChange={(v) => set('loan.cltv', v)} error={errors['loan.cltv']} hint="If applicable" />
        </div>
        <RadioGroup id="occupancy" label="Occupancy" required value={loan.occupancy} onChange={(v) => set('loan.occupancy', v)} options={OPTIONS.occupancy} error={errors['loan.occupancy']} className="sm:col-span-2" />
      </Grid>
    </>
  );
}

export function ProgramStep({ sub, set, errors }: StepProps) {
  const loan = sub.loan;
  const refi = isRefinance(sub);
  return (
    <>
      <SectionTitle icon={icon(ClipboardList)} title="Program & Transaction" blurb="Only the choices that apply to this program are shown." />
      <div className="space-y-6">
        <RadioGroup id="txn" label="Transaction type" required value={loan.transactionType} onChange={(v) => { set('loan.transactionType', v); if (!v.startsWith('refinance')) set('loan.refinanceType', ''); }} options={OPTIONS.transactionType} error={errors['loan.transactionType']} />
        <RadioGroup id="program" label="Mortgage / loan program" required value={loan.program} onChange={(v) => { set('loan.program', v); set('loan.aus', ''); set('loan.refinanceType', ''); if (v !== 'conventional') set('loan.conventionalAgency', ''); }} options={OPTIONS.program} error={errors['loan.program']} />
        {loan.program === 'conventional' && (
          <RadioGroup id="agency" label="Conventional — which agency, if known?" value={loan.conventionalAgency} onChange={(v) => set('loan.conventionalAgency', v)} options={OPTIONS.conventionalAgency} error={errors['loan.conventionalAgency']} />
        )}
        {loan.program === 'other' && (
          <TextInput id="program-other" label="Which program?" required value={loan.programOther} onChange={(v) => set('loan.programOther', v)} error={errors['loan.programOther']} />
        )}
        {loan.program && (
          <RadioGroup id="aus" label="Underwriting / AUS" value={loan.aus} onChange={(v) => set('loan.aus', v)} options={ausOptionsFor(loan.program)} error={errors['loan.aus']} hint="Run AUS on the investor site; processing registers the loan." />
        )}
        {refi && (
          <RadioGroup id="refi-type" label="Type of refinance" value={loan.refinanceType} onChange={(v) => set('loan.refinanceType', v)} options={refinanceOptionsFor(loan.program)} error={errors['loan.refinanceType']} />
        )}
        <RadioGroup id="home-type" label="Type of home" value={loan.homeType} onChange={(v) => set('loan.homeType', v)} options={OPTIONS.homeType} error={errors['loan.homeType']} />
        {loan.homeType === 'other' && (
          <TextInput id="home-other" label="Describe the home type" required value={loan.homeTypeOther} onChange={(v) => set('loan.homeTypeOther', v)} error={errors['loan.homeTypeOther']} />
        )}
      </div>
    </>
  );
}

export function FeesStep({ sub, set, errors }: StepProps) {
  const fees = sub.fees;
  return (
    <>
      <SectionTitle icon={icon(Receipt)} title="Fees & Processing" blurb="How the loan is delivered and what fees apply." />
      <div className="space-y-6">
        <RadioGroup id="channel" label="Loan is" value={fees.channel} onChange={(v) => { set('fees.channel', v); if (v !== 'brokered') set('fees.compensation', ''); }} options={OPTIONS.channel} error={errors['fees.channel']} />
        {fees.channel === 'brokered' && (
          <RadioGroup id="comp" label="Brokered — compensation" value={fees.compensation} onChange={(v) => set('fees.compensation', v)} options={OPTIONS.compensation} error={errors['fees.compensation']} />
        )}
        <SubCard title="Origination fees">
          <Grid>
            <PercentInput id="lp-comp" label="LP comp" value={fees.lpComp} onChange={(v) => set('fees.lpComp', v)} error={errors['fees.lpComp']} placeholder="2.75" />
            <MoneyInput id="box1" label="Box 1" value={fees.box1} onChange={(v) => set('fees.box1', v)} error={errors['fees.box1']} />
            <PercentInput id="disc" label="Discount points" value={fees.discountPoints} onChange={(v) => set('fees.discountPoints', v)} error={errors['fees.discountPoints']} />
            <MoneyInput id="credits" label="Credits" value={fees.credits} onChange={(v) => set('fees.credits', v)} error={errors['fees.credits']} />
          </Grid>
        </SubCard>
        <SubCard title="Third-party fees">
          <Grid>
            <MoneyInput id="credit-fee" label="Credit report fee" value={fees.creditReportFee} onChange={(v) => set('fees.creditReportFee', v)} error={errors['fees.creditReportFee']} placeholder="152" />
            <MoneyInput id="proc-fee" label="Processing fee" value={fees.processingFee} onChange={(v) => set('fees.processingFee', v)} error={errors['fees.processingFee']} placeholder="995" />
            <RadioGroup id="buyout" label="Is the lender buying out the fee?" value={fees.lenderBuyingOutFee} onChange={(v) => { set('fees.lenderBuyingOutFee', v); if (v !== 'yes') set('fees.buyoutNotes', ''); }} options={OPTIONS.yesNo} error={errors['fees.lenderBuyingOutFee']} className="sm:col-span-2" />
            {fees.lenderBuyingOutFee === 'yes' && (
              <TextArea id="buyout-notes" label="Buyout details / notes" value={fees.buyoutNotes} onChange={(v) => set('fees.buyoutNotes', v)} error={errors['fees.buyoutNotes']} rows={2} placeholder="Optional — which fee, how much, any conditions" className="sm:col-span-2" />
            )}
          </Grid>
        </SubCard>
      </div>
    </>
  );
}

export function SetupStep({ sub, set, errors }: StepProps) {
  const ap = sub.appraisal;
  const parties = sub.parties;
  const tp = parties.nonBorrowingTitleParty;
  const setup = sub.setup;
  return (
    <>
      <SectionTitle icon={icon(Shield)} title="Appraisal & Loan Setup" blurb="Tell processing when to order the appraisal and how the loan is set up." />
      <div className="space-y-6">
        <SubCard title="Appraisal">
          <RadioGroup id="appraisal" label="Order appraisal" value={ap.orderTiming} onChange={(v) => set('appraisal.orderTiming', v)} options={OPTIONS.appraisalTiming} error={errors['appraisal.orderTiming']} hint="You tell processing when to order it. A credit card authorization is needed for the order." />
          <TextInput id="appraisal-notes" label="Appraisal notes" value={ap.notes} onChange={(v) => set('appraisal.notes', v)} placeholder="Optional — access, contact, rush" className="mt-4" />
        </SubCard>
        <SubCard title="Loan setup">
          <Grid>
            <RadioGroup id="pmi" label="PMI?" value={setup.pmi} onChange={(v) => set('setup.pmi', v)} options={OPTIONS.yesNoNa} error={errors['setup.pmi']} />
            <RadioGroup id="subordination" label="Subordination required?" value={setup.subordinationRequired} onChange={(v) => set('setup.subordinationRequired', v)} options={OPTIONS.yesNo} error={errors['setup.subordinationRequired']} hint={setup.subordinationRequired === 'yes' ? 'Attach or provide the second mortgage information (statement, note, HELOC agreement) if available.' : undefined} />
            <RadioGroup id="locked" label="Loan locked?" value={setup.loanLocked} onChange={(v) => set('setup.loanLocked', v)} options={OPTIONS.yesNo} error={errors['setup.loanLocked']} />
            <RadioGroup id="escrow" label="Escrow waiver?" value={setup.escrowWaiver} onChange={(v) => set('setup.escrowWaiver', v)} options={OPTIONS.yesNo} error={errors['setup.escrowWaiver']} />
          </Grid>
          <CheckboxGroup id="comm" label="Processor should communicate with" values={sub.communicationPreferences} onChange={(v) => set('communicationPreferences', v)} options={OPTIONS.communicationPreferences} error={errors.communicationPreferences} className="mt-5" hint="Select all that apply." />
        </SubCard>
        <SubCard title="Non-occupant & title parties">
          <RadioGroup id="non-occ" label="Is there a non-occupant co-borrower?" value={parties.nonOccupantCoBorrower} onChange={(v) => set('parties.nonOccupantCoBorrower', v)} options={OPTIONS.yesNo} error={errors['parties.nonOccupantCoBorrower']} />
          <div className="mt-5 border-t border-white/[0.06] pt-5">
            <RadioGroup id="tp-applies" label="Non-Borrowing Spouse / Individual on Title" value={tp.applies} onChange={(v) => set('parties.nonBorrowingTitleParty.applies', v || 'no')} options={[['yes', 'Applies to this loan'], ['no', 'Not applicable']]} hint="We must have this information when applicable." />
            {tp.applies === 'yes' && (
              <Grid>
                <TextInput id="tp-name" label="Full name" required value={tp.name} onChange={(v) => set('parties.nonBorrowingTitleParty.name', v)} error={errors['parties.nonBorrowingTitleParty.name']} />
                <RadioGroup id="tp-title" label="Will be on title?" required value={tp.willBeOnTitle} onChange={(v) => set('parties.nonBorrowingTitleParty.willBeOnTitle', v)} options={OPTIONS.yesNo} error={errors['parties.nonBorrowingTitleParty.willBeOnTitle']} />
                <EmailInput id="tp-email" label="Email" value={tp.email} onChange={(v) => set('parties.nonBorrowingTitleParty.email', v)} error={errors['parties.nonBorrowingTitleParty.email']} />
                <PhoneInput id="tp-phone" label="Phone" value={tp.phone} onChange={(v) => set('parties.nonBorrowingTitleParty.phone', v)} error={errors['parties.nonBorrowingTitleParty.phone']} />
              </Grid>
            )}
          </div>
        </SubCard>
      </div>
    </>
  );
}

export function IncomeAssetsStep({ sub, set, errors }: StepProps) {
  const hasCo = sub.hasCoBorrower === 'yes';
  const income: ReturnType<typeof newIncomeStream>[] = sub.income;
  const assets: ReturnType<typeof newAssetSource>[] = sub.assets;
  const purchase = isPurchase(sub);
  return (
    <>
      <SectionTitle icon={icon(DollarSign)} title="Income & Assets" blurb="Qualifying income provided by the LO. LoanFlow reviews and calculates the verified figure after submission." />
      <div className="space-y-6">
        <SubCard
          title="LO-stated qualifying income"
          action={
            <GhostButton onClick={() => set('income', [...income, newIncomeStream('borrower')])}>
              <Plus className="h-3 w-3" /> Add income
            </GhostButton>
          }
        >
          <div className="space-y-4">
            {income.map((s, i) => (
              <div key={s.id} className="rounded-lg border border-white/[0.06] p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs text-white/40">Income stream {i + 1}</span>
                  {income.length > 1 && (
                    <button type="button" onClick={() => set('income', income.filter((x) => x.id !== s.id))} className="text-white/40 hover:text-red-300" aria-label="Remove income stream">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <Grid>
                  {hasCo && (
                    <RadioGroup id={`inc-who-${s.id}`} label="Whose income" value={s.borrower} onChange={(v) => set(`income.${i}.borrower`, v || 'borrower')} options={[['borrower', 'Borrower'], ['co_borrower', 'Co-borrower']]} error={errors[`income.${i}.borrower`]} className="sm:col-span-2" />
                  )}
                  <Select id={`inc-type-${s.id}`} label="Income type" value={s.incomeType} onChange={(v) => set(`income.${i}.incomeType`, v)} options={OPTIONS.incomeType} error={errors[`income.${i}.incomeType`]} />
                  <TextInput id={`inc-src-${s.id}`} label="Employer / source" value={s.employerOrSource} onChange={(v) => set(`income.${i}.employerOrSource`, v)} placeholder="Employer, business or source" />
                  <MoneyInput id={`inc-amt-${s.id}`} label="LO-stated monthly qualifying income" value={s.loStatedMonthlyIncome} onChange={(v) => set(`income.${i}.loStatedMonthlyIncome`, v)} error={errors[`income.${i}.loStatedMonthlyIncome`]} hint="Your estimate; not validated here." />
                  <Select id={`inc-basis-${s.id}`} label="Calculation basis" value={s.calculationBasis} onChange={(v) => set(`income.${i}.calculationBasis`, v)} options={OPTIONS.calculationBasis} error={errors[`income.${i}.calculationBasis`]} />
                  <CheckboxGroup id={`inc-docs-${s.id}`} label="Supporting documents included" values={s.documentsIncluded} onChange={(v) => set(`income.${i}.documentsIncluded`, v)} options={OPTIONS.incomeDocuments} error={errors[`income.${i}.documentsIncluded`]} className="sm:col-span-2" />
                  <TextInput id={`inc-notes-${s.id}`} label="Notes" value={s.notes} onChange={(v) => set(`income.${i}.notes`, v)} placeholder="Optional" className="sm:col-span-2" />
                </Grid>
              </div>
            ))}
          </div>
        </SubCard>

        <SubCard
          title={purchase ? 'Funds to close / down payment' : 'Funds to close'}
          action={
            <GhostButton onClick={() => set('assets', [...assets, newAssetSource()])}>
              <Plus className="h-3 w-3" /> Add source
            </GhostButton>
          }
        >
          <p className="mb-4 text-xs text-white/40">Never enter full account numbers. Use the last 4 digits or a nickname.</p>
          <div className="space-y-4">
            {assets.map((a, i) => (
              <div key={a.id} className="rounded-lg border border-white/[0.06] p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs text-white/40">Source {i + 1}</span>
                  {assets.length > 1 && (
                    <button type="button" onClick={() => set('assets', assets.filter((x) => x.id !== a.id))} className="text-white/40 hover:text-red-300" aria-label="Remove source">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <Grid>
                  <Select id={`ast-type-${a.id}`} label="Source type" value={a.sourceType} onChange={(v) => set(`assets.${i}.sourceType`, v)} options={OPTIONS.fundsSourceType} error={errors[`assets.${i}.sourceType`]} />
                  <TextInput id={`ast-name-${a.id}`} label={a.sourceType === 'gift_from_relative' ? "Relative's name" : 'Name / institution'} value={a.nameOrInstitution} onChange={(v) => set(`assets.${i}.nameOrInstitution`, v)} />
                  <TextInput id={`ast-ref-${a.id}`} label="Account reference / last 4" value={a.accountReference} onChange={(v) => set(`assets.${i}.accountReference`, v)} error={errors[`assets.${i}.accountReference`]} placeholder="e.g. Chase checking ••1234" />
                  <MoneyInput id={`ast-amt-${a.id}`} label="Amount" value={a.amount} onChange={(v) => set(`assets.${i}.amount`, v)} error={errors[`assets.${i}.amount`]} />
                  <TextInput id={`ast-notes-${a.id}`} label="Notes" value={a.notes} onChange={(v) => set(`assets.${i}.notes`, v)} placeholder="Optional" className="sm:col-span-2" />
                </Grid>
              </div>
            ))}
          </div>
        </SubCard>
      </div>
    </>
  );
}

export function CreditStep({ sub, set, errors }: StepProps) {
  const hasCo = sub.hasCoBorrower === 'yes';
  const block = (who: 'borrower' | 'coBorrower', title: string) => {
    const c = sub.credit[who];
    const needsNote = c.status.includes('tradeline_omitted') || c.status.includes('other_issue');
    return (
      <SubCard title={title}>
        <CheckboxGroup id={`credit-${who}`} label="Credit status" values={c.status} onChange={(v) => set(`credit.${who}.status`, v)} options={OPTIONS.creditStatus} error={errors[`credit.${who}.status`]} />
        <TextArea id={`credit-notes-${who}`} label="Omitted debts / credit notes" required={needsNote} value={c.omittedDebtsNotes} onChange={(v) => set(`credit.${who}.omittedDebtsNotes`, v)} error={errors[`credit.${who}.omittedDebtsNotes`]} rows={3} placeholder="If any debts are omitted, please explain." className="mt-4" />
      </SubCard>
    );
  };
  return (
    <>
      <SectionTitle icon={icon(CreditCard)} title="Credit" blurb="If any debts are omitted, please explain. Processing does not make credit decisions from this form." />
      <div className="space-y-6">
        {block('borrower', 'Borrower')}
        {hasCo && block('coBorrower', 'Co-borrower')}
      </div>
    </>
  );
}

export function TitleInsuranceHoaStep({ sub, set, errors }: StepProps) {
  const hoa = sub.hoa;
  const contact = (who: 'title' | 'insurance', title: string, I: React.ComponentType<{ className?: string }>) => {
    const c = sub[who];
    return (
      <SubCard title={title}>
        <RadioGroup id={`${who}-selected`} label={`${title} selected?`} value={c.selected} onChange={(v) => set(`${who}.selected`, v || 'no')} options={[['yes', 'Yes'], ['no', 'Not selected yet']]} error={errors[`${who}.selected`]} />
        {c.selected === 'yes' && (
          <Grid>
            <TextInput id={`${who}-company`} label="Company" value={c.company} onChange={(v) => set(`${who}.company`, v)} />
            <TextInput id={`${who}-contact`} label="Contact" value={c.contact} onChange={(v) => set(`${who}.contact`, v)} />
            <PhoneInput id={`${who}-phone`} label="Phone" value={c.phone} onChange={(v) => set(`${who}.phone`, v)} error={errors[`${who}.phone`]} />
            <EmailInput id={`${who}-email`} label="Email" value={c.email} onChange={(v) => set(`${who}.email`, v)} error={errors[`${who}.email`]} />
          </Grid>
        )}
      </SubCard>
    );
  };
  return (
    <>
      <SectionTitle icon={icon(Landmark)} title="Title / Insurance / HOA" blurb="Who processing will work with on title, insurance and the association." />
      <div className="space-y-6">
        {contact('title', 'Title company', Landmark)}
        {contact('insurance', 'Insurance company', Shield)}
        <SubCard title="Homeowners association">
          <RadioGroup id="hoa" label="Is there an HOA?" value={hoa.present} onChange={(v) => set('hoa.present', v)} options={OPTIONS.yesNoUnknown} error={errors['hoa.present']} />
          {hoa.present === 'yes' && (
            <>
              <Grid>
                <TextInput id="hoa-company" label="HOA company" value={hoa.company} onChange={(v) => set('hoa.company', v)} />
                <TextInput id="hoa-contact" label="Contact person" value={hoa.contact} onChange={(v) => set('hoa.contact', v)} />
                <PhoneInput id="hoa-phone" label="Phone" value={hoa.phone} onChange={(v) => set('hoa.phone', v)} error={errors['hoa.phone']} />
                <EmailInput id="hoa-email" label="Email" value={hoa.email} onChange={(v) => set('hoa.email', v)} error={errors['hoa.email']} />
              </Grid>
              {(sub.loan.homeType === 'condo' || sub.loan.homeType === 'pud' || sub.loan.homeType === 'two_to_four_unit' || !sub.loan.homeType) && (
                <RadioGroup id="condo-q" label="Condo questionnaire status" value={hoa.condoQuestionnaireStatus} onChange={(v) => set('hoa.condoQuestionnaireStatus', v)} options={OPTIONS.condoQuestionnaireStatus} error={errors['hoa.condoQuestionnaireStatus']} className="mt-5" hint="Discuss the need for a questionnaire and its fees with the borrower." />
              )}
            </>
          )}
        </SubCard>
      </div>
    </>
  );
}

export function AgentsStep({ sub, set, errors }: StepProps) {
  const agent = (side: 'listing' | 'buyer', title: string) => {
    const a = sub.agents[side];
    return (
      <SubCard title={title}>
        <Grid>
          <TextInput id={`${side}-name`} label="Name" value={a.name} onChange={(v) => set(`agents.${side}.name`, v)} />
          <TextInput id={`${side}-license`} label="License #" value={a.license} onChange={(v) => set(`agents.${side}.license`, v)} />
          <PhoneInput id={`${side}-phone`} label="Phone" value={a.phone} onChange={(v) => set(`agents.${side}.phone`, v)} error={errors[`agents.${side}.phone`]} />
          <EmailInput id={`${side}-email`} label="Email" value={a.email} onChange={(v) => set(`agents.${side}.email`, v)} error={errors[`agents.${side}.email`]} />
          <TextInput id={`${side}-brokerage`} label="Brokerage" value={a.brokerage} onChange={(v) => set(`agents.${side}.brokerage`, v)} />
          <TextInput id={`${side}-brokerage-license`} label="Brokerage license #" value={a.brokerageLicense} onChange={(v) => set(`agents.${side}.brokerageLicense`, v)} />
        </Grid>
      </SubCard>
    );
  };
  if (!isPurchase(sub)) {
    return (
      <>
        <SectionTitle icon={icon(Briefcase)} title="Agents" />
        <p className="text-sm text-white/45">Real estate agents are only collected for purchases. Nothing to do here for a refinance — continue to the next step.</p>
      </>
    );
  }
  return (
    <>
      <SectionTitle icon={icon(Briefcase)} title="Real Estate Agents" blurb="Listing and buyer's agents for the purchase." />
      <div className="space-y-6">
        {agent('listing', 'Listing agent')}
        {agent('buyer', "Buyer's agent")}
      </div>
    </>
  );
}

const EXAMPLES = ['Rush closing', 'Special borrower situation', 'Upcoming travel', 'Property issue', 'Condition already known', 'Communication preference'];

export function NotesStep({ sub, set, errors }: StepProps) {
  return (
    <>
      <SectionTitle icon={icon(MessageSquare)} title="Special Instructions" blurb="What else does processing need to know about this file?" />
      <TextArea id="notes" label="Important file information" value={sub.notes} onChange={(v) => set('notes', v)} error={errors.notes} rows={7} placeholder="Anything processing should know…" />
      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((e) => (
          <button key={e} type="button" onClick={() => set('notes', sub.notes ? `${sub.notes.replace(/\s+$/, '')}\n${e}: ` : `${e}: `)} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[11px] text-white/55 hover:border-white/25 hover:text-white">
            + {e}
          </button>
        ))}
      </div>
    </>
  );
}

// ── Documents (UI only until secure upload storage exists — see FLO_INTAKE_INTEGRATION.md) ──

interface DocRow {
  id: string;
  category: string;
  fileName: string;
  sizeBytes: number;
  contentType: string;
}

export const SECURE_UPLOAD_ENABLED = false;

export function DocumentsStep({ sub, set, errors }: StepProps) {
  const docs: DocRow[] = sub.documents;
  const [category, setCategory] = useState('loan_application');
  const [rejected, setRejected] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = (files: FileList | File[]) => {
    const bad: string[] = [];
    const next = [...docs];
    for (const f of Array.from(files)) {
      const ext = f.name.toLowerCase().split('.').pop() || '';
      if (!DOCUMENT_UPLOAD.acceptedExtensions.includes(ext)) bad.push(`${f.name}: file type not accepted`);
      else if (f.size > DOCUMENT_UPLOAD.maxFileBytes) bad.push(`${f.name}: larger than 25 MB`);
      else if (next.length >= DOCUMENT_UPLOAD.maxFiles) bad.push(`${f.name}: too many files`);
      else if (!next.some((d) => d.fileName === f.name && d.category === category)) next.push({ id: `${Date.now()}-${f.name}`, category, fileName: f.name, sizeBytes: f.size, contentType: f.type || 'application/octet-stream' });
    }
    setRejected(bad);
    set('documents', next);
  };

  return (
    <>
      <SectionTitle icon={icon(FileUp)} title="Documents" blurb="List the documents you have for this file. PDF preferred; JPG, PNG, TIFF, Word and Excel are fine too." />
      <div className="space-y-5">
        <Select id="doc-category" label="Document category" value={category} onChange={setCategory} options={OPTIONS.documentCategory} placeholder="Choose a category" />
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            addFiles(e.dataTransfer.files);
          }}
          onClick={() => inputRef.current?.click()}
          className="cursor-pointer rounded-2xl border border-dashed border-white/15 bg-white/[0.02] px-6 py-10 text-center transition hover:border-brand-copper/50 hover:bg-white/[0.04]"
        >
          <FileUp className="mx-auto mb-3 h-7 w-7 text-brand-copper" />
          <p className="text-sm text-white/80">Drag files here or click to choose</p>
          <p className="mt-1 text-xs text-white/40">Up to 25 MB each · {labelFor('documentCategory', category)}</p>
          <input ref={inputRef} type="file" multiple accept={DOCUMENT_UPLOAD.acceptedExtensions.map((e) => `.${e}`).join(',')} className="hidden" onChange={(e) => e.target.files && addFiles(e.target.files)} />
        </div>
        {rejected.length > 0 && (
          <ul className="text-xs text-red-300">
            {rejected.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
        {errors.documents && <p className="text-xs text-red-400">{errors.documents}</p>}
        {docs.length > 0 && (
          <ul className="divide-y divide-white/[0.06] rounded-xl border border-white/[0.08]">
            {docs.map((d) => (
              <li key={d.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <Building2 className="h-4 w-4 shrink-0 text-white/30" />
                <span className="min-w-0 flex-1 truncate text-white/85">{d.fileName}</span>
                <span className="hidden text-xs text-white/40 sm:inline">{labelFor('documentCategory', d.category)}</span>
                <span className="text-xs text-white/40">{(d.sizeBytes / 1024 / 1024).toFixed(1)} MB</span>
                <button type="button" onClick={() => set('documents', docs.filter((x) => x.id !== d.id))} className="text-white/40 hover:text-red-300" aria-label="Remove file">
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
        {!SECURE_UPLOAD_ENABLED && (
          <p className="rounded-xl border border-brand-copper/25 bg-brand-copper/[0.06] px-4 py-3 text-xs leading-relaxed text-white/60">
            <Wallet className="mr-1 inline h-3.5 w-3.5 text-brand-copper" />
            Files are listed with the submission so processing knows what you have. Secure file transfer is not enabled on this site yet, so
            the files themselves stay on your computer; LoanFlow will send you a secure upload link for them. Nothing is uploaded from this page.
          </p>
        )}
      </div>
    </>
  );
}
