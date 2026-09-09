import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ArrowLeft, ArrowRight, Check, CheckCircle, FileText, Loader2, Printer, RotateCcw, Send } from 'lucide-react';

import { emptySubmission, primaryBorrowerName, summarize, validateSubmission } from '../shared/loanSubmission.js';
import { sampleSubmission } from './loan-submission/sample';
import {
  AgentsStep,
  BorrowersStep,
  CreditStep,
  DocumentsStep,
  type Errors,
  FeesStep,
  IncomeAssetsStep,
  LoanDetailsStep,
  LoanOfficerStep,
  NotesStep,
  ProgramStep,
  SetupStep,
  type Submission,
  TitleInsuranceHoaStep,
} from './loan-submission/steps';

// ── Steps ─────────────────────────────────────────────────────────────────
// Error paths are mapped back to the step that owns them so "Next" can stop
// on the right screen and the review screen can link to it.

const STEPS = [
  { id: 'lo', title: 'Loan Officer', short: 'LO', prefixes: ['loanOfficer'] },
  { id: 'borrowers', title: 'Borrowers', short: 'Borrowers', prefixes: ['borrower', 'coBorrower', 'hasCoBorrower'] },
  { id: 'loan', title: 'Loan Details', short: 'Loan', prefixes: ['loan.investor', 'loan.propertyAddress', 'loan.expectedClosingDate', 'loan.loanAmount', 'loan.interestRate', 'loan.ltv', 'loan.cltv', 'loan.occupancy'] },
  { id: 'program', title: 'Program & Transaction', short: 'Program', prefixes: ['loan.'] },
  { id: 'fees', title: 'Fees & Processing', short: 'Fees', prefixes: ['fees'] },
  { id: 'setup', title: 'Appraisal & Loan Setup', short: 'Setup', prefixes: ['appraisal', 'parties', 'setup', 'communicationPreferences'] },
  { id: 'income', title: 'Income & Assets', short: 'Income', prefixes: ['income', 'assets'] },
  { id: 'credit', title: 'Credit', short: 'Credit', prefixes: ['credit'] },
  { id: 'title', title: 'Title / Insurance / HOA', short: 'Title', prefixes: ['title', 'insurance', 'hoa'] },
  { id: 'agents', title: 'Agents', short: 'Agents', prefixes: ['agents'] },
  { id: 'notes', title: 'Important Notes', short: 'Notes', prefixes: ['notes'] },
  { id: 'documents', title: 'Documents', short: 'Docs', prefixes: ['documents'] },
  { id: 'review', title: 'Review & Submit', short: 'Review', prefixes: [] },
] as const;

type StepId = (typeof STEPS)[number]['id'];
const REVIEW = STEPS.length - 1;
const DRAFT_KEY = 'lf.loanSubmission.draft.v1';

export function stepForPath(path: string): number {
  // Most specific prefix wins (loan.* is shared between Loan Details and Program).
  let best = -1;
  let bestLen = -1;
  STEPS.forEach((s, i) => {
    for (const p of s.prefixes) {
      if ((path === p || path.startsWith(p)) && p.length > bestLen) {
        best = i;
        bestLen = p.length;
      }
    }
  });
  return best === -1 ? 0 : best;
}

function errorsForStep(errors: Errors, step: number): Errors {
  return Object.fromEntries(Object.entries(errors).filter(([path]) => stepForPath(path) === step));
}

function setPath(obj: Submission, path: string, value: unknown): Submission {
  const keys = path.split('.');
  const next = Array.isArray(obj) ? [...obj] : { ...obj };
  let cursor = next;
  for (let i = 0; i < keys.length - 1; i += 1) {
    const k = keys[i];
    const child = cursor[k];
    cursor[k] = Array.isArray(child) ? [...child] : { ...(child ?? {}) };
    cursor = cursor[k];
  }
  cursor[keys[keys.length - 1]] = value;
  return next;
}

function loadDraft(): { sub: Submission; savedAt: string } | null {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed?.sub?.schemaVersion !== emptySubmission().schemaVersion) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveDraft(sub: Submission) {
  try {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify({ sub: { ...sub, documents: [] }, savedAt: new Date().toISOString() }));
  } catch {
    /* storage unavailable */
  }
}

function clearDraft() {
  try {
    window.localStorage.removeItem(DRAFT_KEY);
  } catch {
    /* ignore */
  }
}

type Status = 'idle' | 'submitting' | 'success' | 'error';

interface Confirmation {
  submissionId: string;
  borrowerName: string;
  submittedAt: string;
  expectedClosingDate: string | null;
  status: 'received' | 'delivered';
}

function demoParams(): { demo: boolean; step: number } {
  if (!import.meta.env.DEV) return { demo: false, step: 0 };
  const q = new URLSearchParams(window.location.search);
  const step = STEPS.findIndex((s) => s.id === q.get('lfStep'));
  return { demo: q.get('lfDemo') === '1', step: step === -1 ? 0 : step };
}

export const LoanSubmission: React.FC = () => {
  const [sub, setSub] = useState<Submission>(() => {
    const { demo } = demoParams();
    return demo ? sampleSubmission() : (loadDraft()?.sub ?? emptySubmission());
  });
  const [restored, setRestored] = useState<string | null>(() => {
    if (demoParams().demo) return null;
    const draft = loadDraft();
    // Only announce a restore when the LO had actually started typing.
    return draft && (draft.sub.loanOfficer?.name || draft.sub.borrower?.name || draft.sub.loan?.propertyAddress) ? draft.savedAt : null;
  });
  const [step, setStep] = useState<number>(() => demoParams().step);
  const [touched, setTouched] = useState<Set<number>>(new Set());
  const demoDone = demoParams().demo && new URLSearchParams(window.location.search).get('lfStep') === 'done';
  const [status, setStatus] = useState<Status>(demoDone ? 'success' : 'idle');
  const [serverError, setServerError] = useState('');
  const [serverFields, setServerFields] = useState<Errors>({});
  const [confirmation, setConfirmation] = useState<Confirmation | null>(
    demoDone
      ? { submissionId: 'sub_0123456789abcdef01234567', borrowerName: 'Ariana Justinvil-Synthetic', submittedAt: new Date().toISOString(), expectedClosingDate: '2026-09-23', status: 'delivered' }
      : null
  );
  const inFlight = useRef(false);
  const topRef = useRef<HTMLDivElement>(null);

  const set = useCallback((path: string, value: unknown) => {
    setSub((prev: Submission) => setPath(prev, path, value));
    setServerFields((prev) => {
      if (!prev[path]) return prev;
      const next = { ...prev };
      delete next[path];
      return next;
    });
  }, []);

  // Deep link: /#submit (nav button, emails) lands on the form once it has rendered.
  useEffect(() => {
    if (window.location.hash === '#submit' || demoParams().demo) {
      window.setTimeout(() => topRef.current?.scrollIntoView({ block: 'start' }), 50);
    }
  }, []);

  // Autosave (documents are not persisted: the files live only in this session).
  useEffect(() => {
    if (status === 'success') return;
    const t = window.setTimeout(() => saveDraft(sub), 400);
    return () => window.clearTimeout(t);
  }, [sub, status]);

  const validation = useMemo(() => validateSubmission(sub), [sub]);
  const allErrors: Errors = useMemo(() => ({ ...validation.errors, ...serverFields }), [validation.errors, serverFields]);
  const visibleErrors: Errors = useMemo(() => (touched.has(step) || step === REVIEW ? errorsForStep(allErrors, step) : {}), [allErrors, step, touched]);
  const stepHasErrors = (i: number) => Object.keys(errorsForStep(allErrors, i)).length > 0;

  const scrollTop = () => topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const goTo = (i: number) => {
    setStep(Math.max(0, Math.min(REVIEW, i)));
    scrollTop();
  };

  const next = () => {
    setTouched((t) => new Set(t).add(step));
    if (stepHasErrors(step)) {
      const first = Object.keys(errorsForStep(allErrors, step))[0];
      document.querySelector<HTMLElement>(`[aria-invalid="true"]`)?.focus();
      if (first) return;
    }
    goTo(step + 1);
  };

  const reset = () => {
    clearDraft();
    setSub(emptySubmission());
    setStep(0);
    setTouched(new Set());
    setStatus('idle');
    setServerError('');
    setServerFields({});
    setConfirmation(null);
    setRestored(null);
  };

  async function submit() {
    if (inFlight.current) return;
    setTouched(new Set(STEPS.map((_, i) => i)));
    if (Object.keys(validation.errors).length > 0) {
      goTo(stepForPath(Object.keys(validation.errors)[0]));
      return;
    }
    inFlight.current = true;
    setStatus('submitting');
    setServerError('');
    try {
      const attempt = async () => {
        const res = await fetch('/api/loan-submissions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(sub) });
        const json = await res.json().catch(() => ({}));
        return { res, json };
      };
      let { res, json } = await attempt();
      if (!res.ok && res.status >= 500) ({ res, json } = await attempt()); // one retry; same submissionId => never a duplicate loan
      if (res.ok && json.ok) {
        setConfirmation({
          submissionId: json.submissionId || sub.submissionId,
          borrowerName: primaryBorrowerName(sub),
          submittedAt: json.receivedAt || new Date().toISOString(),
          expectedClosingDate: sub.loan.expectedClosingDate || null,
          status: json.status === 'delivered' ? 'delivered' : 'received',
        });
        clearDraft();
        setStatus('success');
      } else {
        setStatus('error');
        setServerError(json.error || 'Submission failed. Please try again.');
        if (json.fields && typeof json.fields === 'object') {
          setServerFields(json.fields);
          goTo(stepForPath(Object.keys(json.fields)[0]));
        }
      }
    } catch {
      setStatus('error');
      setServerError('Unable to reach the server. Your answers are saved in this browser — please try again in a moment.');
    } finally {
      inFlight.current = false;
    }
  }

  const stepProps = { sub, set, errors: visibleErrors };
  const current = STEPS[step].id as StepId;

  return (
    <section id="submit" className="relative py-24 sm:py-32 bg-gradient-to-b from-brand-dark via-[#0d241e] to-brand-dark overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-brand-copper/[0.03] rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-emerald-500/[0.03] rounded-full blur-3xl" />
      </div>

      <div ref={topRef} className="relative mx-auto max-w-4xl px-4 sm:px-6 scroll-mt-24">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/[0.05] border border-white/10 px-4 py-1.5 mb-6">
            <FileText className="h-4 w-4 text-brand-copper" />
            <span className="text-xs font-medium uppercase tracking-widest text-white/60">Loan Submission</span>
          </div>
          <h2 className="font-serif text-4xl sm:text-5xl font-bold text-white mb-4">
            Submit a <span className="bg-gradient-to-r from-brand-copper to-amber-400 bg-clip-text text-transparent">New Loan</span>
          </h2>
          <p className="mx-auto max-w-2xl text-white/50 leading-relaxed">
            About ten minutes. Your progress saves in this browser automatically, and the file lands with LoanFlow Processing the moment you submit.
          </p>
        </div>

        {status === 'success' && confirmation ? (
          <ConfirmationCard confirmation={confirmation} onReset={reset} />
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (step === REVIEW) void submit();
              else next();
            }}
            noValidate
            className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl shadow-[0_22px_70px_rgba(0,0,0,0.4)] overflow-hidden"
          >
            <Stepper step={step} onSelect={goTo} hasErrors={(i) => touched.has(i) && stepHasErrors(i)} />

            {restored && step === 0 && (
              <div className="flex flex-wrap items-center gap-3 border-b border-white/[0.06] bg-brand-copper/[0.06] px-6 py-3 text-xs text-white/70">
                <RotateCcw className="h-3.5 w-3.5 text-brand-copper" />
                We restored the draft you were working on ({new Date(restored).toLocaleString()}).
                <button type="button" onClick={reset} className="ml-auto underline decoration-white/30 hover:text-white">
                  Start over
                </button>
              </div>
            )}

            {status === 'error' && serverError && (
              <div className="flex items-start gap-3 bg-red-500/[0.08] border-b border-red-400/20 px-6 py-4">
                <AlertCircle className="h-5 w-5 text-red-400 mt-0.5 flex-shrink-0" />
                <p className="text-sm text-red-300">{serverError}</p>
              </div>
            )}

            <div className="p-6 sm:p-10">
              {current === 'lo' && <LoanOfficerStep {...stepProps} />}
              {current === 'borrowers' && <BorrowersStep {...stepProps} />}
              {current === 'loan' && <LoanDetailsStep {...stepProps} />}
              {current === 'program' && <ProgramStep {...stepProps} />}
              {current === 'fees' && <FeesStep {...stepProps} />}
              {current === 'setup' && <SetupStep {...stepProps} />}
              {current === 'income' && <IncomeAssetsStep {...stepProps} />}
              {current === 'credit' && <CreditStep {...stepProps} />}
              {current === 'title' && <TitleInsuranceHoaStep {...stepProps} />}
              {current === 'agents' && <AgentsStep {...stepProps} />}
              {current === 'notes' && <NotesStep {...stepProps} />}
              {current === 'documents' && <DocumentsStep {...stepProps} />}
              {current === 'review' && <Review sub={sub} errors={allErrors} recommended={validation.recommended} onEdit={goTo} />}

              {/* Honeypot (invisible to real users) */}
              <div className="absolute -left-[9999px]" aria-hidden="true">
                <label htmlFor="website">Website</label>
                <input type="text" id="website" name="website" value={sub.website} onChange={(e) => set('website', e.target.value)} tabIndex={-1} autoComplete="off" />
              </div>
            </div>

            <div className="border-t border-white/[0.06] bg-white/[0.02] px-6 sm:px-10 py-5 flex flex-col-reverse sm:flex-row items-center justify-between gap-4">
              <div className="flex w-full items-center justify-between gap-3 sm:w-auto sm:justify-start">
                <button
                  type="button"
                  onClick={() => goTo(step - 1)}
                  disabled={step === 0 || status === 'submitting'}
                  className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-medium text-white/75 transition hover:bg-white/[0.08] hover:text-white disabled:opacity-40"
                >
                  <ArrowLeft className="h-4 w-4" /> {step === REVIEW ? 'Back & Edit' : 'Back'}
                </button>
                <span className="text-xs text-white/30">
                  Step {step + 1} of {STEPS.length}
                </span>
              </div>
              {step === REVIEW ? (
                <button
                  type="submit"
                  disabled={status === 'submitting'}
                  className="group relative inline-flex w-full sm:w-auto items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-brand-copper to-amber-600 px-8 py-3.5 text-sm font-bold text-brand-dark shadow-lg shadow-brand-copper/20 transition-all duration-300 hover:shadow-xl hover:shadow-brand-copper/30 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100"
                >
                  {status === 'submitting' ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Submitting…
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /> Submit Loan to Processing
                    </>
                  )}
                </button>
              ) : (
                <button
                  type="submit"
                  className="group inline-flex w-full sm:w-auto items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-brand-copper to-amber-600 px-7 py-3 text-sm font-bold text-brand-dark shadow-lg shadow-brand-copper/20 transition-all duration-300 hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]"
                >
                  {step === REVIEW - 1 ? 'Review' : 'Next'} <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </button>
              )}
            </div>
          </form>
        )}
      </div>
    </section>
  );
};

function Stepper({ step, onSelect, hasErrors }: { step: number; onSelect: (i: number) => void; hasErrors: (i: number) => boolean }) {
  const pct = Math.round((step / (STEPS.length - 1)) * 100);
  return (
    <div className="border-b border-white/[0.06] px-6 sm:px-10 pt-5 pb-4">
      <div className="flex items-center justify-between text-xs text-white/50">
        <span className="font-medium text-white/80">{STEPS[step].title}</span>
        <span>{pct}% complete</span>
      </div>
      <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full bg-gradient-to-r from-brand-copper to-amber-400 transition-all duration-500" style={{ width: `${Math.max(4, pct)}%` }} />
      </div>
      <ol className="mt-3 hidden flex-wrap gap-1 md:flex">
        {STEPS.map((s, i) => {
          const done = i < step;
          const active = i === step;
          const bad = hasErrors(i);
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onSelect(i)}
                className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] transition ${
                  active ? 'bg-brand-copper/20 text-white' : bad ? 'text-red-300 hover:bg-white/5' : done ? 'text-white/70 hover:bg-white/5' : 'text-white/35 hover:bg-white/5 hover:text-white/60'
                }`}
              >
                {bad ? <AlertCircle className="h-3 w-3" /> : done ? <Check className="h-3 w-3 text-brand-copper" /> : <span className="w-3 text-center">{i + 1}</span>}
                {s.short}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function Review({ sub, errors, recommended, onEdit }: { sub: Submission; errors: Errors; recommended: Array<{ path: string; message: string }>; onEdit: (i: number) => void }) {
  const groups = summarize(sub);
  const blocking = Object.entries(errors);
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-widest text-white/70">Review & Submit</h3>
        <p className="mt-2 text-sm text-white/45">One last look. Anything highlighted in copper is recommended but not required.</p>
      </div>

      {blocking.length > 0 && (
        <div className="rounded-xl border border-red-400/30 bg-red-500/[0.06] p-4 text-sm">
          <p className="mb-2 flex items-center gap-2 font-medium text-red-300">
            <AlertCircle className="h-4 w-4" /> {blocking.length} {blocking.length === 1 ? 'item needs' : 'items need'} a fix before submitting
          </p>
          <ul className="space-y-1 text-red-200/80">
            {blocking.slice(0, 8).map(([path, msg]) => (
              <li key={path}>
                <button type="button" onClick={() => onEdit(stepForPath(path))} className="underline decoration-red-300/40 hover:text-white">
                  {STEPS[stepForPath(path)].title}
                </button>
                : {msg}
              </li>
            ))}
          </ul>
        </div>
      )}

      {recommended.length > 0 && (
        <div className="rounded-xl border border-brand-copper/30 bg-brand-copper/[0.06] p-4 text-sm">
          <p className="mb-2 font-medium text-brand-copper">Recommended, still missing</p>
          <ul className="flex flex-wrap gap-2">
            {recommended.map((r) => (
              <li key={r.path}>
                <button type="button" onClick={() => onEdit(stepForPath(r.path))} className="rounded-full border border-brand-copper/30 px-3 py-1 text-xs text-white/75 hover:bg-brand-copper/15 hover:text-white">
                  {r.message}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {groups.map((g) => (
          <div key={g.title} className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-4">
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-white/60">{g.title}</h4>
              <button type="button" onClick={() => onEdit(stepForGroup(g.title))} className="text-[11px] text-brand-copper hover:underline">
                Edit
              </button>
            </div>
            <dl className="space-y-1.5 text-sm">
              {g.rows.map(([k, v]) => (
                <div key={k} className="grid grid-cols-[minmax(0,42%)_1fr] gap-2">
                  <dt className="truncate text-white/40">{k}</dt>
                  <dd className="break-words text-white/85">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}

function stepForGroup(title: string): number {
  const map: Record<string, StepId> = {
    Borrowers: 'borrowers',
    Loan: 'loan',
    Program: 'program',
    'Income (LO-stated)': 'income',
    'Assets / funds to close': 'income',
    Orders: 'setup',
    'Title / Insurance': 'title',
    Agents: 'agents',
    Credit: 'credit',
    Notes: 'notes',
    Documents: 'documents',
  };
  return Math.max(0, STEPS.findIndex((s) => s.id === (map[title] ?? 'lo')));
}

function ConfirmationCard({ confirmation, onReset }: { confirmation: Confirmation; onReset: () => void }) {
  const when = new Date(confirmation.submittedAt);
  const isToday = when.toDateString() === new Date().toDateString();
  const submitted = `${isToday ? 'Today' : when.toLocaleDateString()} at ${when.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  const closing = confirmation.expectedClosingDate ? new Date(`${confirmation.expectedClosingDate}T12:00:00`).toLocaleDateString('en-US') : '—';
  return (
    <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/[0.08] backdrop-blur-xl p-8 sm:p-10 text-center print:border-black print:bg-white print:text-black">
      <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/20">
        <CheckCircle className="h-8 w-8 text-emerald-400" />
      </div>
      <h3 className="font-serif text-2xl font-bold text-white mb-2 print:text-black">Loan Submitted Successfully</h3>
      <p className="text-white/60 mb-8 print:text-black">LoanFlow Processing has received the submission.</p>
      <dl className="mx-auto grid max-w-md grid-cols-1 gap-3 text-left text-sm sm:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 print:border-black">
          <dt className="text-[11px] uppercase tracking-wider text-white/40 print:text-black">Borrower</dt>
          <dd className="text-white/90 print:text-black">{confirmation.borrowerName || '—'}</dd>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 print:border-black">
          <dt className="text-[11px] uppercase tracking-wider text-white/40 print:text-black">Submitted</dt>
          <dd className="text-white/90 print:text-black">{submitted}</dd>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 print:border-black">
          <dt className="text-[11px] uppercase tracking-wider text-white/40 print:text-black">Expected closing</dt>
          <dd className="text-white/90 print:text-black">{closing}</dd>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 print:border-black">
          <dt className="text-[11px] uppercase tracking-wider text-white/40 print:text-black">Confirmation ID</dt>
          <dd className="break-all font-mono text-xs text-white/90 print:text-black">{confirmation.submissionId}</dd>
        </div>
      </dl>
      <p className="mx-auto mt-6 max-w-md text-xs text-white/45 print:text-black">
        Keep this ID for your records. Processing will reach out with anything still needed; if you listed documents, you will get a secure upload link for them.
      </p>
      <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row print:hidden">
        <button type="button" onClick={() => window.print()} className="inline-flex items-center gap-2 rounded-xl bg-white/[0.08] border border-white/10 px-6 py-3 text-sm font-medium text-white/80 hover:bg-white/[0.12] hover:text-white transition">
          <Printer className="h-4 w-4" /> Print / Save Confirmation
        </button>
        <button type="button" onClick={onReset} className="inline-flex items-center gap-2 rounded-xl bg-white/[0.08] border border-white/10 px-6 py-3 text-sm font-medium text-white/80 hover:bg-white/[0.12] hover:text-white transition">
          <Send className="h-4 w-4" /> Submit Another Loan
        </button>
      </div>
    </div>
  );
}
