import { Button } from '@hermes/plugin-sdk'
import { useEffect, useState } from 'react'

import { runFloAction } from './actions-api'
import type { FileRecord } from './ashley'
import type { CustomerFileContact } from './data'

const ROLES = [
  ['borrower', 'Borrower'],
  ['co_borrower', 'Co-Borrower'],
  ['loan_officer', 'Loan Officer'],
  ['lender', 'Lender'],
  ['lender_ae', 'Lender Account Executive / AE'],
  ['buyers_agent', "Buyer's Agent / Realtor"],
  ['listing_agent', 'Listing Agent / Realtor'],
  ['title_closing_agent', 'Title / Closing Agent'],
  ['insurance_agent', 'HOI / Insurance Agent'],
  ['employer_voe', 'Employer / VOE Contact'],
  ['appraiser_amc', 'Appraiser / AMC'],
  ['other', 'Other custom contact'],
] as const

const INPUT = 'min-w-0 rounded border border-(--ui-stroke-tertiary) bg-(--ui-bg-input) px-2 py-1.5 text-sm text-(--ui-text-primary)'

const blankContact = (role: string, index = 0): CustomerFileContact => ({
  contact_id: `contact-${role}-${index + 1}`,
  role,
  preferred_communication_method: 'not_set',
})

function hasContactData(contact: CustomerFileContact): boolean {
  return Boolean(contact.custom_role || contact.name || contact.company || contact.phone || contact.mobile || contact.email || contact.nmls_license_id || contact.notes)
}

export function ContactsPanel({ ws, onSaved }: { ws: FileRecord; onSaved: () => void }) {
  const [contacts, setContacts] = useState<CustomerFileContact[]>(ws.contacts ?? [])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    void runFloAction<{ action: string; message: string; contacts: CustomerFileContact[]; seeded?: boolean }>('contacts-get', { workspace_id: ws.workspace_id })
      .then(result => {
        if (active) {
          setContacts(Array.isArray(result.contacts) ? result.contacts : [])

          if (result.seeded) {onSaved()}
        }
      })
      .catch(reason => {
        if (active) {setError(reason instanceof Error ? reason.message : 'Contacts could not be loaded.')}
      })
      .finally(() => { if (active) {setLoading(false)} })

    return () => { active = false }
  }, [onSaved, ws.workspace_id])

  const rows = [...contacts]

  for (const [role] of ROLES) {
    const matches = contacts.filter(contact => contact.role === role)

    if (matches.length === 0) {rows.push(blankContact(role))}
  }

  const update = (contactId: string, field: keyof CustomerFileContact, value: string) => {
    setContacts(current => {
      const index = current.findIndex(contact => contact.contact_id === contactId)

      if (index >= 0) {return current.map(contact => contact.contact_id === contactId ? { ...contact, [field]: value } : contact)}
      const empty = rows.find(contact => contact.contact_id === contactId)

      return empty ? [...current, { ...empty, [field]: value }] : current
    })
    setNotice(null)
  }

  const addAnother = (role: string) => setContacts(current => {
    const count = current.filter(contact => contact.role === role).length

    return [...current, blankContact(role, count)]
  })

  const save = async () => {
    setSaving(true)
    setError(null)
    setNotice(null)

    try {
      const saved = await runFloAction<{ action: string; message: string; contacts: CustomerFileContact[] }>('contacts-save', {
        workspace_id: ws.workspace_id,
        contacts: contacts.filter(hasContactData),
      })

      setContacts(saved.contacts ?? [])
      setNotice('Customer File contacts saved.')
      onSaved()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Contacts could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  const remove = (contactId: string) => setContacts(current => current.filter(contact => contact.contact_id !== contactId))

  return (
    <details className="rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-bg-card) p-3" data-testid="customer-file-contacts">
      <summary className="cursor-pointer text-sm font-medium">Contacts · {contacts.filter(hasContactData).length} saved</summary>
      <div className="mt-3 flex flex-col gap-4">
        <p className="m-0 text-xs text-(--ui-text-secondary)">
          Saved with this Customer File. Missing source information is shown as “Not Set”; Flo won’t guess contact details.
        </p>
        {error ? <p className="m-0 text-sm text-destructive" role="alert">{error}</p> : null}
        {notice ? <p className="m-0 text-sm text-(--ui-text-secondary)" role="status">{notice}</p> : null}
        {loading ? <p className="m-0 text-sm text-(--ui-text-secondary)">Loading contacts…</p> : null}
        {!loading && rows.map(contact => {
          const roleLabel = ROLES.find(([key]) => key === contact.role)?.[1] ?? 'Other custom contact'
          const rowHasData = hasContactData(contact)

          return (
            <section className="rounded border border-(--ui-stroke-tertiary) p-3" key={contact.contact_id}>
              <div className="mb-2 flex items-center justify-between gap-2">
                <h4 className="m-0 text-sm font-semibold">{contact.role === 'other' && contact.custom_role ? contact.custom_role : roleLabel}</h4>
                {contact.role === 'other' || rows.filter(item => item.role === contact.role).length > 1 ? (
                  <Button onClick={() => remove(contact.contact_id)} size="xs" variant="secondary">Remove</Button>
                ) : null}
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {contact.role === 'other' ? (
                  <input aria-label="Custom contact role" className={INPUT} onChange={event => update(contact.contact_id, 'custom_role', event.target.value)} placeholder="Contact role · Not Set" value={contact.custom_role ?? ''} />
                ) : null}
                <input aria-label={`${roleLabel} name`} className={INPUT} onChange={event => update(contact.contact_id, 'name', event.target.value)} placeholder="Name · Not Set" value={contact.name ?? ''} />
                <input aria-label={`${roleLabel} company`} className={INPUT} onChange={event => update(contact.contact_id, 'company', event.target.value)} placeholder="Company · Not Set" value={contact.company ?? ''} />
                <input aria-label={`${roleLabel} phone`} className={INPUT} onChange={event => update(contact.contact_id, 'phone', event.target.value)} placeholder="Phone · Not Set" value={contact.phone ?? ''} />
                <input aria-label={`${roleLabel} mobile`} className={INPUT} onChange={event => update(contact.contact_id, 'mobile', event.target.value)} placeholder="Mobile · Not Set" value={contact.mobile ?? ''} />
                <input aria-label={`${roleLabel} email`} className={INPUT} onChange={event => update(contact.contact_id, 'email', event.target.value)} placeholder="Email · Not Set" type="email" value={contact.email ?? ''} />
                <input aria-label={`${roleLabel} NMLS or license`} className={INPUT} onChange={event => update(contact.contact_id, 'nmls_license_id', event.target.value)} placeholder="NMLS / license · Not Set" value={contact.nmls_license_id ?? ''} />
                <select aria-label={`${roleLabel} preferred communication`} className={INPUT} onChange={event => update(contact.contact_id, 'preferred_communication_method', event.target.value)} value={contact.preferred_communication_method ?? 'not_set'}>
                  <option value="not_set">Preferred method · Not Set</option>
                  <option value="phone">Phone</option>
                  <option value="text">Text</option>
                  <option value="email">Email</option>
                  <option value="other">Other</option>
                </select>
                <textarea aria-label={`${roleLabel} notes`} className={`${INPUT} sm:col-span-2 lg:col-span-3`} onChange={event => update(contact.contact_id, 'notes', event.target.value)} placeholder="Notes · Not Set" rows={2} value={contact.notes ?? ''} />
                {contact.source?.kind ? <p className="m-0 text-[0.6875rem] text-(--ui-text-tertiary) sm:col-span-2 lg:col-span-3">Imported from {contact.source.kind}{contact.source.path ? ` · ${contact.source.path}` : ''}</p> : null}
                {!rowHasData ? <span className="sr-only">Not Set</span> : null}
              </div>
            </section>
          )
        })}
        <div className="flex flex-wrap gap-2">
          {ROLES.map(([role, label]) => role === 'other' || contacts.some(contact => contact.role === role && hasContactData(contact)) ? (
            <Button key={role} onClick={() => addAnother(role)} size="xs" variant="secondary">+ {label}</Button>
          ) : null)}
          <Button disabled={saving || loading} onClick={() => void save()} size="sm">{saving ? 'Saving…' : 'Save Contacts'}</Button>
        </div>
      </div>
    </details>
  )
}
