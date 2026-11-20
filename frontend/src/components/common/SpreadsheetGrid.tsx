/**
 * Spreadsheet-style data grid used on every tabular display.
 * - Single-click top-left PDF / CSV / Excel / Copy buttons (TS Cl. 11.3(j); FRD CMN-18)
 * - Multi-column sort, quick filter, inline edit with drop-downs (TS Cl. 2.2 input controls)
 * - Paste from Excel with a preview before commit (TS Cl. 11.1, 11.3(h)(k); FRD CMN-13, CMN-19)
 */
import { useMemo, useState, type ReactNode } from 'react'
import {
  flexRender, getCoreRowModel, getFilteredRowModel, getSortedRowModel, useReactTable,
  type ColumnDef, type SortingState,
} from '@tanstack/react-table'
import * as XLSX from 'xlsx'
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import { useTranslation } from 'react-i18next'
import { Button, Modal, cls, inputCls } from './ui'

export interface GridCol<T = any> {
  key: string
  label: string
  width?: number
  editable?: boolean
  options?: string[]
  type?: 'text' | 'number' | 'datetime-local'
  render?: (row: T) => ReactNode
  exportValue?: (row: T) => string | number
}

export interface SpreadsheetGridProps<T> {
  columns: GridCol<T>[]
  rows: T[]
  exportName?: string
  rowKey?: (row: T) => string | number
  onCellEdit?: (row: T, key: string, value: string) => void
  onBulkPaste?: (rows: Record<string, string>[]) => void | Promise<void>
  rowClassName?: (row: T) => string
  toolbar?: ReactNode
  compact?: boolean
  emptyText?: string
}

function cellText(row: any, c: GridCol): string {
  if (c.exportValue) return String(c.exportValue(row) ?? '')
  const v = row[c.key]
  return v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v)
}

export function toCsv(columns: GridCol[], rows: any[]) {
  const esc = (s: string) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s)
  return [columns.map((c) => esc(c.label)).join(','), ...rows.map((r) => columns.map((c) => esc(cellText(r, c))).join(','))].join('\n')
}

export function parseClipboardTable(text: string, columns: GridCol[]): Record<string, string>[] {
  const lines = text.replace(/\r/g, '').split('\n').filter((l) => l.trim() !== '')
  if (!lines.length) return []
  let cells = lines.map((l) => l.split('\t'))
  const header = cells[0].map((h) => h.trim().toLowerCase())
  const byLabel = columns.map((c) => header.indexOf(c.label.toLowerCase()) >= 0 ? header.indexOf(c.label.toLowerCase()) : header.indexOf(c.key.toLowerCase()))
  const hasHeader = byLabel.some((i) => i >= 0)
  if (hasHeader) cells = cells.slice(1)
  return cells.map((row) => {
    const o: Record<string, string> = {}
    columns.forEach((c, i) => {
      const idx = hasHeader ? byLabel[i] : i
      if (idx >= 0 && idx < row.length) o[c.key] = row[idx].trim()
    })
    return o
  })
}

export default function SpreadsheetGrid<T extends Record<string, any>>({
  columns, rows, exportName = 'export', rowKey, onCellEdit, onBulkPaste, rowClassName, toolbar, compact, emptyText,
}: SpreadsheetGridProps<T>) {
  const { t } = useTranslation()
  const [sorting, setSorting] = useState<SortingState>([])
  const [filter, setFilter] = useState('')
  const [copied, setCopied] = useState(false)
  const [pasteOpen, setPasteOpen] = useState(false)
  const [pasteText, setPasteText] = useState('')
  const [preview, setPreview] = useState<Record<string, string>[] | null>(null)

  const colDefs = useMemo<ColumnDef<T>[]>(() => columns.map((c) => ({
    id: c.key,
    accessorFn: (r: T) => cellText(r, c),
    header: c.label,
    size: c.width,
    cell: (info) => {
      const row = info.row.original
      if (c.editable && onCellEdit) {
        if (c.options) {
          return (
            <select aria-label={c.label} className="w-full rounded border-slate-200 bg-transparent text-xs" value={row[c.key] ?? ''}
              onChange={(e) => onCellEdit(row, c.key, e.target.value)}>
              <option value="" />
              {c.options.map((o) => <option key={o}>{o}</option>)}
            </select>
          )
        }
        return <input aria-label={c.label} type={c.type ?? 'text'} className="w-full rounded border border-transparent bg-transparent px-1 text-xs hover:border-slate-300 focus:border-grid-500"
          defaultValue={row[c.key] ?? ''} onBlur={(e) => e.target.value !== String(row[c.key] ?? '') && onCellEdit(row, c.key, e.target.value)} />
      }
      return c.render ? c.render(row) : cellText(row, c)
    },
  })), [columns, onCellEdit])

  const table = useReactTable({
    data: rows, columns: colDefs, state: { sorting, globalFilter: filter },
    onSortingChange: setSorting, onGlobalFilterChange: setFilter, enableMultiSort: true, isMultiSortEvent: () => true,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getFilteredRowModel: getFilteredRowModel(),
    getRowId: rowKey ? (r) => String(rowKey(r)) : undefined,
  })
  const visible = table.getRowModel().rows.map((r) => r.original)
  const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, '')

  const exportCsv = () => {
    const blob = new Blob(['﻿' + toCsv(columns, visible)], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${exportName}_${stamp}.csv`
    a.click()
  }
  const exportXlsx = () => {
    const ws = XLSX.utils.aoa_to_sheet([columns.map((c) => c.label), ...visible.map((r) => columns.map((c) => cellText(r, c)))])
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, exportName.slice(0, 28))
    XLSX.writeFile(wb, `${exportName}_${stamp}.xlsx`)
  }
  const exportPdf = () => {
    const doc = new jsPDF({ orientation: columns.length > 6 ? 'landscape' : 'portrait' })
    doc.setFontSize(11)
    doc.text(`Grid-India OMS - ${exportName}`, 14, 12)
    autoTable(doc, { head: [columns.map((c) => c.label)], body: visible.map((r) => columns.map((c) => cellText(r, c))), startY: 16, styles: { fontSize: 7 } })
    doc.save(`${exportName}_${stamp}.pdf`)
  }
  const copy = async () => {
    const tsv = [columns.map((c) => c.label).join('\t'), ...visible.map((r) => columns.map((c) => cellText(r, c)).join('\t'))].join('\n')
    try {
      await navigator.clipboard.writeText(tsv)
    } catch {
      /* clipboard blocked */
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <div className="flex overflow-hidden rounded-lg bg-white shadow-card ring-1 ring-slate-200" role="group" aria-label={t('common.export')}>
          {[['PDF', exportPdf], ['CSV', exportCsv], ['Excel', exportXlsx], [copied ? t('common.copied') : t('common.copy'), copy]].map(([label, fn]) => (
            <button key={label as string} onClick={fn as () => void} className="border-r border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 last:border-r-0 hover:bg-grid-50 hover:text-grid-700">
              {label as string}
            </button>
          ))}
        </div>
        {onBulkPaste && <Button size="sm" variant="secondary" onClick={() => setPasteOpen(true)}>{t('common.pasteFromExcel')}</Button>}
        {toolbar}
        <input aria-label={t('common.search')} placeholder={t('common.search') + '…'} value={filter} onChange={(e) => setFilter(e.target.value)} className={cls(inputCls, 'ml-auto w-56 py-1.5 text-xs')} />
      </div>
      <div className="overflow-x-auto rounded-xl border border-slate-200/80 bg-white shadow-card">
        <table className="min-w-full text-left text-[12.5px]">
          <thead className="sticky top-0 bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th key={h.id} style={{ width: h.getSize() !== 150 ? h.getSize() : undefined }}
                    className="cursor-pointer select-none whitespace-nowrap border-b border-slate-200 px-3 py-2.5 font-semibold hover:text-slate-800"
                    onClick={h.column.getToggleSortingHandler()} aria-sort={h.column.getIsSorted() === 'asc' ? 'ascending' : h.column.getIsSorted() === 'desc' ? 'descending' : 'none'}>
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {{ asc: ' ▲', desc: ' ▼' }[h.column.getIsSorted() as string] ?? ''}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 && (
              <tr><td colSpan={columns.length} className="px-2 py-6 text-center text-slate-400">{emptyText ?? t('common.noData')}</td></tr>
            )}
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id} className={cls('border-b border-slate-100 last:border-0 odd:bg-white even:bg-slate-50/50 hover:bg-grid-50/70', rowClassName?.(r.original))}>
                {r.getVisibleCells().map((c) => (
                  <td key={c.id} className={cls('px-3 align-top text-slate-700', compact ? 'py-1' : 'py-2')}>{flexRender(c.column.columnDef.cell, c.getContext())}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="text-[11px] text-slate-500">{visible.length} / {rows.length} rows · shift-click headers to sort on multiple columns</div>

      <Modal open={pasteOpen} onClose={() => { setPasteOpen(false); setPreview(null); setPasteText('') }} title={t('common.pasteFromExcel')} wide>
        {!preview ? (
          <div className="space-y-2">
            <p className="text-sm text-slate-600">Copy rows from Excel (optionally with header row) and paste below. Expected columns: {columns.filter((c) => !c.render).map((c) => c.label).join(', ')}</p>
            <textarea aria-label="Pasted data" className={cls(inputCls, 'h-40 font-mono text-xs')} value={pasteText} onChange={(e) => setPasteText(e.target.value)} />
            <Button onClick={() => setPreview(parseClipboardTable(pasteText, columns))} disabled={!pasteText.trim()}>{t('common.preview')}</Button>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm font-medium">{preview.length} row(s) will be submitted. Review before committing.</p>
            <div className="max-h-72 overflow-auto rounded border">
              <table className="min-w-full text-xs">
                <thead className="bg-slate-100"><tr>{columns.map((c) => <th key={c.key} className="px-2 py-1 text-left">{c.label}</th>)}</tr></thead>
                <tbody>{preview.map((r, i) => <tr key={i} className="border-t">{columns.map((c) => <td key={c.key} className="px-2 py-1">{r[c.key] ?? ''}</td>)}</tr>)}</tbody>
              </table>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setPreview(null)}>{t('common.edit')}</Button>
              <Button onClick={async () => { await onBulkPaste?.(preview); setPasteOpen(false); setPreview(null); setPasteText('') }}>{t('common.commit')}</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
