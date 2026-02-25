import React, { useState } from 'react';
import {
  Send,
  CheckCircle,
  AlertCircle,
  Loader2,
  FileText,
  User,
  Building,
  Mail,
  Phone,
  MapPin,
  ClipboardList,
  Users,
} from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────

interface FormData {
  loanOfficerFullName: string;
  companyName: string;
  emailAddress: string;
  phoneNumber: string;
  borrowerFullName: string;
  coBorrowerFullName: string;
  borrowerEmail: string;
  borrowerPhone: string;
  propertyAddress: string;
  loanType: string;
  notes: string;
  website: string; // honeypot
}

interface FormErrors {
  [key: string]: string;
}

type SubmitStatus = 'idle' | 'submitting' | 'success' | 'error';

// ── Constants ────────────────────────────────────────────────────

const INITIAL_FORM_DATA: FormData = {
  loanOfficerFullName: '',
  companyName: '',
  emailAddress: '',
  phoneNumber: '',
  borrowerFullName: '',
  coBorrowerFullName: '',
  borrowerEmail: '',
  borrowerPhone: '',
  propertyAddress: '',
  loanType: '',
  notes: '',
  website: '',
};

const LOAN_TYPES = [
  'Conventional',
  'FHA',
  'VA',
  'USDA',
  'Non-QM',
  'Jumbo',
  'Other',
];

// ── Component ────────────────────────────────────────────────────

export const LoanSubmission: React.FC = () => {
  const [formData, setFormData] = useState<FormData>(INITIAL_FORM_DATA);
  const [errors, setErrors] = useState<FormErrors>({});
  const [status, setStatus] = useState<SubmitStatus>('idle');
  const [serverError, setServerError] = useState('');

  // ── Validation ──────────────────────────────────────────────

  function validate(): FormErrors {
    const errs: FormErrors = {};

    if (!formData.loanOfficerFullName.trim())
      errs.loanOfficerFullName = 'Loan officer name is required';
    if (!formData.companyName.trim())
      errs.companyName = 'Company name is required';

    if (!formData.emailAddress.trim()) {
      errs.emailAddress = 'Email address is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.emailAddress)) {
      errs.emailAddress = 'Enter a valid email address';
    }

    if (!formData.phoneNumber.trim())
      errs.phoneNumber = 'Phone number is required';

    if (!formData.borrowerFullName.trim())
      errs.borrowerFullName = 'Borrower name is required';

    if (
      formData.borrowerEmail.trim() &&
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.borrowerEmail)
    ) {
      errs.borrowerEmail = 'Enter a valid email address';
    }

    if (!formData.propertyAddress.trim())
      errs.propertyAddress = 'Property address is required';
    if (!formData.loanType) errs.loanType = 'Select a loan type';

    return errs;
  }

  // ── Handlers ────────────────────────────────────────────────

  function handleChange(
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >
  ) {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Clear field error on change
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    // Validate
    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      // Scroll to first error
      const firstErrorField = Object.keys(validationErrors)[0];
      document
        .querySelector(`[name="${firstErrorField}"]`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    setStatus('submitting');
    setServerError('');

    try {
      const res = await fetch('/api/loan-submission', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      const json = await res.json();

      if (res.ok && json.ok) {
        setStatus('success');
        setFormData(INITIAL_FORM_DATA);
        setErrors({});
      } else {
        setStatus('error');
        setServerError(
          json.error || 'Submission failed. Please try again.'
        );

        // Highlight server-reported invalid fields
        if (json.fields) {
          const fieldErrors: FormErrors = {};
          json.fields.forEach((f: string) => {
            fieldErrors[f] = 'This field requires attention';
          });
          setErrors(fieldErrors);
        }
      }
    } catch {
      setStatus('error');
      setServerError(
        'Unable to reach the server. Please check your connection and try again.'
      );
    }
  }

  function handleNewSubmission() {
    setStatus('idle');
    setServerError('');
  }

  // ── Shared input styles ─────────────────────────────────────

  const inputBase =
    'w-full rounded-xl border bg-white/[0.04] px-4 py-3 text-sm text-white/90 placeholder-white/30 outline-none backdrop-blur-sm transition duration-200 focus:ring-2 focus:ring-brand-copper/50 focus:border-brand-copper/60';

  const inputNormal = `${inputBase} border-white/10 hover:border-white/20`;
  const inputError = `${inputBase} border-red-400/60 ring-1 ring-red-400/30`;

  function inputClass(field: string) {
    return errors[field] ? inputError : inputNormal;
  }

  // ── Render ──────────────────────────────────────────────────

  return (
    <section
      id="submit"
      className="relative py-24 sm:py-32 bg-gradient-to-b from-brand-dark via-[#0d241e] to-brand-dark overflow-hidden"
    >
      {/* Decorative background elements */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-brand-copper/[0.03] rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-emerald-500/[0.03] rounded-full blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-4xl px-6">
        {/* ── Section Header ──────────────────────────────────── */}
        <div className="text-center mb-14">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/[0.05] border border-white/10 px-4 py-1.5 mb-6">
            <FileText className="h-4 w-4 text-brand-copper" />
            <span className="text-xs font-medium uppercase tracking-widest text-white/60">
              Loan Intake
            </span>
          </div>

          <h2 className="font-serif text-4xl sm:text-5xl font-bold text-white mb-4">
            Submit a{' '}
            <span className="bg-gradient-to-r from-brand-copper to-amber-400 bg-clip-text text-transparent">
              Loan File
            </span>
          </h2>

          <p className="mx-auto max-w-2xl text-white/50 leading-relaxed">
            Ready to get started? Fill out the details below and our team will
            begin processing within 24 hours.
          </p>
        </div>

        {/* ── Success State ───────────────────────────────────── */}
        {status === 'success' && (
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/[0.08] backdrop-blur-xl p-10 text-center">
            <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/20">
              <CheckCircle className="h-8 w-8 text-emerald-400" />
            </div>
            <h3 className="font-serif text-2xl font-bold text-white mb-3">
              Submission Received
            </h3>
            <p className="text-white/60 mb-8 max-w-md mx-auto">
              Thank you! Your loan file has been submitted successfully. Our
              team will review it and reach out within 24 hours.
            </p>
            <button
              onClick={handleNewSubmission}
              className="inline-flex items-center gap-2 rounded-xl bg-white/[0.08] border border-white/10 px-6 py-3 text-sm font-medium text-white/80 hover:bg-white/[0.12] hover:text-white transition"
            >
              <Send className="h-4 w-4" />
              Submit Another Loan
            </button>
          </div>
        )}

        {/* ── Form ────────────────────────────────────────────── */}
        {status !== 'success' && (
          <form
            onSubmit={handleSubmit}
            noValidate
            className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl shadow-[0_22px_70px_rgba(0,0,0,0.4)] overflow-hidden"
          >
            {/* Server error banner */}
            {status === 'error' && serverError && (
              <div className="flex items-start gap-3 bg-red-500/[0.08] border-b border-red-400/20 px-6 py-4">
                <AlertCircle className="h-5 w-5 text-red-400 mt-0.5 flex-shrink-0" />
                <p className="text-sm text-red-300">{serverError}</p>
              </div>
            )}

            <div className="p-6 sm:p-10 space-y-10">
              {/* ═══════════ Section 1: Loan Officer ═══════════ */}
              <fieldset>
                <legend className="flex items-center gap-2 mb-6">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-copper/20">
                    <User className="h-4 w-4 text-brand-copper" />
                  </div>
                  <span className="text-sm font-semibold uppercase tracking-widest text-white/70">
                    Loan Officer Information
                  </span>
                </legend>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  {/* Full Name */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      Full Name <span className="text-brand-copper">*</span>
                    </label>
                    <input
                      type="text"
                      name="loanOfficerFullName"
                      value={formData.loanOfficerFullName}
                      onChange={handleChange}
                      placeholder="Jane Smith"
                      className={inputClass('loanOfficerFullName')}
                    />
                    {errors.loanOfficerFullName && (
                      <p className="mt-1 text-xs text-red-400">
                        {errors.loanOfficerFullName}
                      </p>
                    )}
                  </div>

                  {/* Company Name */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      <span className="inline-flex items-center gap-1">
                        <Building className="h-3 w-3" /> Company Name{' '}
                        <span className="text-brand-copper">*</span>
                      </span>
                    </label>
                    <input
                      type="text"
                      name="companyName"
                      value={formData.companyName}
                      onChange={handleChange}
                      placeholder="ABC Mortgage Group"
                      className={inputClass('companyName')}
                    />
                    {errors.companyName && (
                      <p className="mt-1 text-xs text-red-400">
                        {errors.companyName}
                      </p>
                    )}
                  </div>

                  {/* Email */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      <span className="inline-flex items-center gap-1">
                        <Mail className="h-3 w-3" /> Email Address{' '}
                        <span className="text-brand-copper">*</span>
                      </span>
                    </label>
                    <input
                      type="email"
                      name="emailAddress"
                      value={formData.emailAddress}
                      onChange={handleChange}
                      placeholder="jane@abcmortgage.com"
                      className={inputClass('emailAddress')}
                    />
                    {errors.emailAddress && (
                      <p className="mt-1 text-xs text-red-400">
                        {errors.emailAddress}
                      </p>
                    )}
                  </div>

                  {/* Phone */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      <span className="inline-flex items-center gap-1">
                        <Phone className="h-3 w-3" /> Phone Number{' '}
                        <span className="text-brand-copper">*</span>
                      </span>
                    </label>
                    <input
                      type="tel"
                      name="phoneNumber"
                      value={formData.phoneNumber}
                      onChange={handleChange}
                      placeholder="(555) 123-4567"
                      className={inputClass('phoneNumber')}
                    />
                    {errors.phoneNumber && (
                      <p className="mt-1 text-xs text-red-400">
                        {errors.phoneNumber}
                      </p>
                    )}
                  </div>
                </div>
              </fieldset>

              {/* Divider */}
              <div className="border-t border-white/[0.06]" />

              {/* ═══════════ Section 2: Borrower ═══════════════ */}
              <fieldset>
                <legend className="flex items-center gap-2 mb-6">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-copper/20">
                    <Users className="h-4 w-4 text-brand-copper" />
                  </div>
                  <span className="text-sm font-semibold uppercase tracking-widest text-white/70">
                    Borrower Information
                  </span>
                </legend>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  {/* Borrower Name */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      Borrower Full Name{' '}
                      <span className="text-brand-copper">*</span>
                    </label>
                    <input
                      type="text"
                      name="borrowerFullName"
                      value={formData.borrowerFullName}
                      onChange={handleChange}
                      placeholder="John Doe"
                      className={inputClass('borrowerFullName')}
                    />
                    {errors.borrowerFullName && (
                      <p className="mt-1 text-xs text-red-400">
                        {errors.borrowerFullName}
                      </p>
                    )}
                  </div>

                  {/* Co-Borrower Name */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      Co-Borrower Full Name
                    </label>
                    <input
                      type="text"
                      name="coBorrowerFullName"
                      value={formData.coBorrowerFullName}
                      onChange={handleChange}
                      placeholder="Optional"
                      className={inputClass('coBorrowerFullName')}
                    />
                  </div>

                  {/* Borrower Email */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      <span className="inline-flex items-center gap-1">
                        <Mail className="h-3 w-3" /> Borrower Email
                      </span>
                    </label>
                    <input
                      type="email"
                      name="borrowerEmail"
                      value={formData.borrowerEmail}
                      onChange={handleChange}
                      placeholder="john@email.com"
                      className={inputClass('borrowerEmail')}
                    />
                    {errors.borrowerEmail && (
                      <p className="mt-1 text-xs text-red-400">
                        {errors.borrowerEmail}
                      </p>
                    )}
                  </div>

                  {/* Borrower Phone */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      <span className="inline-flex items-center gap-1">
                        <Phone className="h-3 w-3" /> Borrower Phone
                      </span>
                    </label>
                    <input
                      type="tel"
                      name="borrowerPhone"
                      value={formData.borrowerPhone}
                      onChange={handleChange}
                      placeholder="(555) 987-6543"
                      className={inputClass('borrowerPhone')}
                    />
                  </div>
                </div>
              </fieldset>

              {/* Divider */}
              <div className="border-t border-white/[0.06]" />

              {/* ═══════════ Section 3: Loan Details ═══════════ */}
              <fieldset>
                <legend className="flex items-center gap-2 mb-6">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-copper/20">
                    <ClipboardList className="h-4 w-4 text-brand-copper" />
                  </div>
                  <span className="text-sm font-semibold uppercase tracking-widest text-white/70">
                    Loan Details
                  </span>
                </legend>

                <div className="space-y-5">
                  {/* Property Address */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      <span className="inline-flex items-center gap-1">
                        <MapPin className="h-3 w-3" /> Property Address{' '}
                        <span className="text-brand-copper">*</span>
                      </span>
                    </label>
                    <input
                      type="text"
                      name="propertyAddress"
                      value={formData.propertyAddress}
                      onChange={handleChange}
                      placeholder="123 Main St, Jacksonville, FL 32256"
                      className={inputClass('propertyAddress')}
                    />
                    {errors.propertyAddress && (
                      <p className="mt-1 text-xs text-red-400">
                        {errors.propertyAddress}
                      </p>
                    )}
                  </div>

                  {/* Loan Type */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      Loan Type{' '}
                      <span className="text-brand-copper">*</span>
                    </label>
                    <select
                      name="loanType"
                      value={formData.loanType}
                      onChange={handleChange}
                      className={`${inputClass('loanType')} appearance-none cursor-pointer`}
                    >
                      <option value="" className="bg-brand-dark text-white/50">
                        Select loan type…
                      </option>
                      {LOAN_TYPES.map((type) => (
                        <option
                          key={type}
                          value={type}
                          className="bg-brand-dark text-white"
                        >
                          {type}
                        </option>
                      ))}
                    </select>
                    {errors.loanType && (
                      <p className="mt-1 text-xs text-red-400">
                        {errors.loanType}
                      </p>
                    )}
                  </div>

                  {/* Notes */}
                  <div>
                    <label className="block text-xs font-medium text-white/50 mb-1.5">
                      Notes
                    </label>
                    <textarea
                      name="notes"
                      value={formData.notes}
                      onChange={handleChange}
                      rows={4}
                      placeholder="Any additional details, special instructions, or file notes…"
                      className={`${inputNormal} resize-none`}
                    />
                  </div>
                </div>
              </fieldset>

              {/* ── Honeypot (invisible to real users) ──────── */}
              <div className="absolute -left-[9999px]" aria-hidden="true">
                <label htmlFor="website">Website</label>
                <input
                  type="text"
                  id="website"
                  name="website"
                  value={formData.website}
                  onChange={handleChange}
                  tabIndex={-1}
                  autoComplete="off"
                />
              </div>
            </div>

            {/* ── Submit Button Bar ───────────────────────────── */}
            <div className="border-t border-white/[0.06] bg-white/[0.02] px-6 sm:px-10 py-6 flex flex-col sm:flex-row items-center justify-between gap-4">
              <p className="text-xs text-white/30">
                <span className="text-brand-copper">*</span> Required fields
              </p>

              <button
                type="submit"
                disabled={status === 'submitting'}
                className="group relative inline-flex items-center gap-2.5 rounded-xl bg-gradient-to-r from-brand-copper to-amber-600 px-8 py-3.5 text-sm font-bold text-brand-dark shadow-lg shadow-brand-copper/20 transition-all duration-300 hover:shadow-xl hover:shadow-brand-copper/30 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100"
              >
                {status === 'submitting' ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Submitting…
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                    Submit Loan File
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
};
