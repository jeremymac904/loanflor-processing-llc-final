import React from 'react';
import { AlertCircle } from 'lucide-react';

// ── Shared field primitives for the Loan Submission form ──────────────────
// Visual language = the existing LoanFlow dark glass style (white/[0.04]
// inputs, copper focus ring, tiny uppercase labels).

/** `[value, label]` — the shared contract ships plain arrays, so accept any readonly string pair. */
export type Option = readonly string[];

const base =
  'w-full rounded-xl border bg-white/[0.04] px-4 py-3 text-sm text-white/90 placeholder-white/30 outline-none backdrop-blur-sm transition duration-200 focus:ring-2 focus:ring-brand-copper/50 focus:border-brand-copper/60';
const normal = `${base} border-white/10 hover:border-white/20`;
const invalid = `${base} border-red-400/60 ring-1 ring-red-400/30`;

export function inputClass(error?: string) {
  return error ? invalid : normal;
}

export function Field({
  label,
  required,
  hint,
  error,
  htmlFor,
  children,
  className = '',
}: {
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  htmlFor?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="block text-xs font-medium text-white/50 mb-1.5">
        {label} {required && <span className="text-brand-copper">*</span>}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-[11px] text-white/35">{hint}</p>}
      {error && (
        <p className="mt-1 flex items-center gap-1 text-xs text-red-400" role="alert">
          <AlertCircle className="h-3 w-3" /> {error}
        </p>
      )}
    </div>
  );
}

type BaseProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  hint?: string;
  error?: string;
  placeholder?: string;
  className?: string;
  autoComplete?: string;
};

export function TextInput({ id, label, value, onChange, required, hint, error, placeholder, className, autoComplete, type = 'text' }: BaseProps & { type?: string }) {
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={id} className={className}>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        className={inputClass(error)}
        aria-invalid={Boolean(error)}
      />
    </Field>
  );
}

export function EmailInput(props: BaseProps) {
  return <TextInput {...props} type="email" autoComplete={props.autoComplete ?? 'email'} placeholder={props.placeholder ?? 'name@company.com'} />;
}

function formatPhoneLive(raw: string) {
  const d = raw.replace(/\D/g, '').replace(/^1(?=\d{10})/, '').slice(0, 10);
  if (d.length < 4) return d;
  if (d.length < 7) return `(${d.slice(0, 3)}) ${d.slice(3)}`;
  return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
}

export function PhoneInput(props: BaseProps) {
  return (
    <TextInput
      {...props}
      type="tel"
      autoComplete={props.autoComplete ?? 'tel'}
      placeholder={props.placeholder ?? '(555) 123-4567'}
      onChange={(v) => props.onChange(formatPhoneLive(v))}
    />
  );
}

export function DateInput(props: BaseProps) {
  return <TextInput {...props} type="date" autoComplete="off" />;
}

function Affixed({ prefix, suffix, children }: { prefix?: string; suffix?: string; children: React.ReactNode }) {
  return (
    <div className="relative">
      {prefix && <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-sm text-white/40">{prefix}</span>}
      <div className={prefix ? '[&>input]:pl-8' : suffix ? '[&>input]:pr-9' : ''}>{children}</div>
      {suffix && <span className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-sm text-white/40">{suffix}</span>}
    </div>
  );
}

export function MoneyInput({ id, label, value, onChange, required, hint, error, placeholder, className }: BaseProps) {
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={id} className={className}>
      <Affixed prefix="$">
        <input
          id={id}
          name={id}
          inputMode="decimal"
          value={value}
          onChange={(e) => onChange(e.target.value.replace(/[^0-9.,]/g, ''))}
          onBlur={(e) => {
            const n = Number(e.target.value.replace(/,/g, ''));
            if (e.target.value && Number.isFinite(n)) onChange(n.toLocaleString('en-US', { maximumFractionDigits: 2 }));
          }}
          placeholder={placeholder ?? '0.00'}
          className={inputClass(error)}
          aria-invalid={Boolean(error)}
        />
      </Affixed>
    </Field>
  );
}

export function PercentInput({ id, label, value, onChange, required, hint, error, placeholder, className }: BaseProps) {
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={id} className={className}>
      <Affixed suffix="%">
        <input
          id={id}
          name={id}
          inputMode="decimal"
          value={value}
          onChange={(e) => onChange(e.target.value.replace(/[^0-9.]/g, ''))}
          placeholder={placeholder ?? '0.00'}
          className={inputClass(error)}
          aria-invalid={Boolean(error)}
        />
      </Affixed>
    </Field>
  );
}

export function TextArea({ id, label, value, onChange, required, hint, error, placeholder, className, rows = 4 }: BaseProps & { rows?: number }) {
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={id} className={className}>
      <textarea
        id={id}
        name={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        placeholder={placeholder}
        className={`${inputClass(error)} resize-y`}
        aria-invalid={Boolean(error)}
      />
    </Field>
  );
}

export function Select({
  id,
  label,
  value,
  onChange,
  options,
  required,
  hint,
  error,
  placeholder = 'Select…',
  className,
}: BaseProps & { options: readonly Option[] }) {
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={id} className={className}>
      <select
        id={id}
        name={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`${inputClass(error)} appearance-none cursor-pointer`}
        aria-invalid={Boolean(error)}
      >
        <option value="" className="bg-brand-dark text-white/50">
          {placeholder}
        </option>
        {options.map(([v, l]) => (
          <option key={v} value={v} className="bg-brand-dark text-white">
            {l}
          </option>
        ))}
      </select>
    </Field>
  );
}

/** Pill-style radio group: one tap, no dropdown. */
export function RadioGroup({
  id,
  label,
  value,
  onChange,
  options,
  required,
  hint,
  error,
  className,
}: BaseProps & { options: readonly Option[] }) {
  return (
    <Field label={label} required={required} hint={hint} error={error} className={className}>
      <div role="radiogroup" aria-labelledby={`${id}-label`} className="flex flex-wrap gap-2">
        {options.map(([v, l]) => {
          const active = value === v;
          return (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(v)}
              className={`rounded-xl border px-4 py-2.5 text-sm transition ${
                active
                  ? 'border-brand-copper/70 bg-brand-copper/15 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                  : 'border-white/10 bg-white/[0.03] text-white/70 hover:border-white/25 hover:text-white'
              } ${error ? 'ring-1 ring-red-400/30' : ''}`}
            >
              {l}
            </button>
          );
        })}
      </div>
    </Field>
  );
}

export function CheckboxGroup({
  id,
  label,
  values,
  onChange,
  options,
  hint,
  error,
  className,
}: {
  id: string;
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  options: readonly Option[];
  hint?: string;
  error?: string;
  className?: string;
}) {
  return (
    <Field label={label} hint={hint} error={error} className={className}>
      <div className="flex flex-wrap gap-2">
        {options.map(([v, l]) => {
          const active = values.includes(v);
          return (
            <label
              key={v}
              className={`inline-flex cursor-pointer items-center gap-2 rounded-xl border px-3.5 py-2 text-sm transition select-none ${
                active ? 'border-brand-copper/70 bg-brand-copper/15 text-white' : 'border-white/10 bg-white/[0.03] text-white/70 hover:border-white/25'
              }`}
            >
              <input
                type="checkbox"
                name={id}
                value={v}
                checked={active}
                onChange={(e) => onChange(e.target.checked ? [...values, v] : values.filter((x) => x !== v))}
                className="h-3.5 w-3.5 accent-[#c69c6d]"
              />
              {l}
            </label>
          );
        })}
      </div>
    </Field>
  );
}

export function SectionTitle({ icon, title, blurb }: { icon: React.ReactNode; title: string; blurb?: string }) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-copper/20">{icon}</div>
        <h3 className="text-sm font-semibold uppercase tracking-widest text-white/70">{title}</h3>
      </div>
      {blurb && <p className="mt-2 text-sm text-white/45">{blurb}</p>}
    </div>
  );
}

export function SubCard({ title, action, children }: { title?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-4 sm:p-5">
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h4 className="text-xs font-semibold uppercase tracking-wider text-white/60">{title}</h4>}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

export function GhostButton({ onClick, children, className = '' }: { onClick: () => void; children: React.ReactNode; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-white/70 transition hover:bg-white/[0.08] hover:text-white ${className}`}
    >
      {children}
    </button>
  );
}

export const Grid: React.FC<{ children: React.ReactNode; cols?: 2 | 3 }> = ({ children, cols = 2 }) => (
  <div className={`grid grid-cols-1 gap-5 ${cols === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>{children}</div>
);
