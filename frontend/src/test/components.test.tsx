import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import '../i18n'
import SpreadsheetGrid, { parseClipboardTable, toCsv } from '../components/common/SpreadsheetGrid'
import { Badge, statusColor } from '../components/common/ui'
import { setLanguage, bi } from '../i18n'

const cols = [{ key: 'name', label: 'Element' }, { key: 'kv', label: 'kV' }]

describe('SpreadsheetGrid', () => {
  it('shows PDF / CSV / Excel / Copy export buttons and rows', () => {
    render(<SpreadsheetGrid columns={cols} rows={[{ name: 'Agra-Gwalior', kv: 765 }, { name: 'Bikaner-Bhadla', kv: 400 }]} />)
    for (const b of ['PDF', 'CSV', 'Excel', 'Copy']) expect(screen.getByRole('button', { name: b })).toBeInTheDocument()
    expect(screen.getByText('Agra-Gwalior')).toBeInTheDocument()
  })
  it('filters rows with quick search', () => {
    render(<SpreadsheetGrid columns={cols} rows={[{ name: 'Agra-Gwalior', kv: 765 }, { name: 'Bikaner-Bhadla', kv: 400 }]} />)
    fireEvent.change(screen.getByLabelText('Search'), { target: { value: 'Bikaner' } })
    expect(screen.queryByText('Agra-Gwalior')).not.toBeInTheDocument()
  })
  it('parses Excel paste with and without header', () => {
    expect(parseClipboardTable('Element\tkV\nLine A\t400\n', cols)).toEqual([{ name: 'Line A', kv: '400' }])
    expect(parseClipboardTable('Line B\t220', cols)).toEqual([{ name: 'Line B', kv: '220' }])
  })
  it('escapes CSV', () => {
    expect(toCsv(cols, [{ name: 'A, "B"', kv: 1 }])).toBe('Element,kV\n"A, ""B""",1')
  })
})

describe('status colour coding', () => {
  it('maps statuses', () => {
    expect(statusColor('APPROVED')).toBe('green')
    expect(statusColor('RETURNED')).toBe('red')
    expect(statusColor('CONSENT_PENDING')).toBe('amber')
    render(<MemoryRouter><Badge>TRIPPED</Badge></MemoryRouter>)
    expect(screen.getByText('TRIPPED').className).toContain('red')
  })
})

describe('bilingual', () => {
  it('prefers Hindi field when language is Hindi', () => {
    const row = { title_en: 'Notice', title_hi: 'सूचना' }
    setLanguage('hi')
    expect(bi(row, 'title')).toBe('सूचना')
    setLanguage('en')
    expect(bi(row, 'title')).toBe('Notice')
  })
})
