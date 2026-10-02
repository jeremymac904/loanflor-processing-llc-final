import { describe, expect, it } from 'vitest'

import type { ComposerAttachment } from '@/store/composer'

import { attachedMismoPaths, intakeAcknowledgement } from './local-intake-intent'

const xml: ComposerAttachment = { id: 'x', kind: 'file', label: 'Smith_3.4.xml', path: 'C:/Synthetic/Smith_3.4.xml' }

describe('normal Flo chat MISMO intake intent', () => {
  it.each(['Add this loan to the pipeline.', 'Start this loan.', 'Review this file.', 'Prep this file.', 'Open this loan.'])(
    'routes explicit attached-file intent before model tool selection: %s', text => {
      expect(attachedMismoPaths(text, [xml])).toEqual([xml.path])
    }
  )

  it('does not intercept general chat or a PDF-only attachment', () => {
    expect(attachedMismoPaths('What is a loan estimate?', [xml])).toEqual([])
    expect(attachedMismoPaths('Add this loan to the pipeline.', [{ ...xml, path: 'C:/Synthetic/1003.pdf', label: '1003.pdf' }])).toEqual([])
  })

  it('keeps the follow-up model prompt free of borrower/file data', () => {
    expect(intakeAcknowledgement()).not.toMatch(/Jamie|Smith|SMITH-TEST|Fern Way|C:\\Synthetic/i)
  })
})
