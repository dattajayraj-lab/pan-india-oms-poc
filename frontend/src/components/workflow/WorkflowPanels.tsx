// Shared case panels: versioned documents, departmental consents, editable checklists (FRD CMN-21, CMN-27, CMN-11).
import { useEffect, useMemo, useState } from 'react'
import { api, download, errMsg } from '../../api/client'
import { fmtDT } from '../../store/hooks'
import { Alert, Badge, Button, Card, Modal, cls, inputCls } from '../common/ui'

export interface Doc { id: number; doc_category: string; auto_filename: string; original_filename: string; version_no: number; is_latest: boolean; uploader_name: string; change_note: string; created_at: string; visible_to_applicant: boolean; is_confidential: boolean }

export function DocumentPanel({ docs, uploadUrl, categories, labels, required, onChange, canUpload = true, title = 'Documents' }:
  { docs: Doc[]; uploadUrl?: string; categories: string[]; labels?: Record<string, string>; required?: string[]; onChange: () => void; canUpload?: boolean; title?: string }) {
  const [cat, setCat] = useState(categories[0] ?? 'OTHER')
  const [file, setFile] = useState<File | null>(null)
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')
  const [showAll, setShowAll] = useState(false)
  useEffect(() => { if (!categories.includes(cat)) setCat(categories[0]) }, [categories]) // eslint-disable-line react-hooks/exhaustive-deps
  const latest = docs.filter((d) => showAll || d.is_latest)
  const have = new Set(docs.map((d) => d.doc_category))
  const upload = async () => {
    if (!file || !uploadUrl) return
    const fd = new FormData()
    fd.append('doc_category', cat)
    fd.append('change_note', note)
    fd.append('file', file)
    try { await api.post(uploadUrl, fd); setFile(null); setNote(''); setErr(''); onChange() } catch (e) { setErr(errMsg(e)) }
  }
  return (
    <Card title={title} actions={<label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> show all revisions</label>}>
      {required && required.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {required.map((r) => <Badge key={r} color={have.has(r) ? 'green' : 'red'}>{have.has(r) ? '✓' : '✗'} {r}</Badge>)}
        </div>
      )}
      {canUpload && uploadUrl && (
        <div className="mb-3 grid gap-2 rounded bg-slate-50 p-2 md:grid-cols-[1fr_1fr_1fr_auto]">
          <select aria-label="Document category" className={inputCls} value={cat} onChange={(e) => setCat(e.target.value)}>
            {categories.map((c) => <option key={c} value={c}>{c}{labels?.[c] ? ` - ${labels[c]}` : ''}</option>)}
          </select>
          <input aria-label="File" type="file" className="text-xs" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <input aria-label="Change note" placeholder="What changed (for revisions)" className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} />
          <Button onClick={upload} disabled={!file}>Upload</Button>
        </div>
      )}
      {err && <div className="mb-2"><Alert kind="error">{err}</Alert></div>}
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead className="bg-slate-100 text-left"><tr><th className="px-2 py-1">Category</th><th className="px-2 py-1">Auto-named file</th><th className="px-2 py-1">Rev</th><th className="px-2 py-1">By</th><th className="px-2 py-1">Uploaded</th><th className="px-2 py-1">Note</th><th /></tr></thead>
          <tbody>
            {latest.length === 0 && <tr><td colSpan={7} className="px-2 py-3 text-center text-slate-400">No documents</td></tr>}
            {latest.map((d) => (
              <tr key={d.id} className={cls('border-t', !d.is_latest && 'text-slate-400')}>
                <td className="px-2 py-1">{d.doc_category} {!d.visible_to_applicant && <Badge color="purple">RLDC only</Badge>}</td>
                <td className="px-2 py-1 font-mono">{d.auto_filename}</td>
                <td className="px-2 py-1">v{d.version_no}{d.is_latest && ' (latest)'}</td>
                <td className="px-2 py-1">{d.uploader_name}</td>
                <td className="px-2 py-1">{fmtDT(d.created_at)}</td>
                <td className="px-2 py-1">{d.change_note}</td>
                <td className="px-2 py-1"><button className="text-grid-700 underline" onClick={() => download(`/documents/${d.id}/download`, d.auto_filename)}>Download</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export function ConsentPanel({ consents, actUrl, onChange, title = 'Departmental consents' }: { consents: any[]; actUrl: (id: number) => string; onChange: () => void; title?: string }) {
  const [remarks, setRemarks] = useState<Record<number, string>>({})
  const [err, setErr] = useState('')
  const act = async (id: number, decision: string) => {
    try { await api.post(actUrl(id), { decision, remarks: remarks[id] ?? '' }); setErr(''); onChange() } catch (e) { setErr(errMsg(e)) }
  }
  const groups = useMemo(() => [...new Set(consents.map((c) => c.group))].sort(), [consents])
  if (!consents.length) return null
  return (
    <Card title={title}>
      {err && <div className="mb-2"><Alert kind="error">{err}</Alert></div>}
      <div className="space-y-2">
        {groups.map((g) => (
          <div key={g} className="rounded border border-slate-200 p-2">
            <div className="mb-1 text-[11px] font-semibold uppercase text-slate-500">Step {g} {consents.filter((c) => c.group === g).length > 1 && '(parallel)'}</div>
            <div className="grid gap-2 md:grid-cols-3">
              {consents.filter((c) => c.group === g).map((c) => (
                <div key={c.id} className="rounded bg-slate-50 p-2 text-xs">
                  <div className="flex items-center justify-between"><b>{c.label} · {c.level}</b><Badge>{c.status}</Badge></div>
                  {c.remarks && <div className="mt-1 text-slate-600">“{c.remarks}”</div>}
                  {c.can_act && (
                    <div className="mt-1 space-y-1">
                      <input aria-label={`Remarks ${c.label}`} placeholder="Remarks / observations" className={inputCls} value={remarks[c.id] ?? ''} onChange={(e) => setRemarks({ ...remarks, [c.id]: e.target.value })} />
                      <div className="flex gap-1">
                        <Button size="sm" variant="success" onClick={() => act(c.id, 'ACCEPTED')}>Accept</Button>
                        <Button size="sm" variant="warning" onClick={() => act(c.id, 'RETURNED')}>Return</Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

/** Checklist with Tick / Pending(+comment) per item; editable template for coordinators. */
export function ChecklistPanel({ code, value, onChange, editable }: { code: string; value: Record<string, any>; onChange: (v: Record<string, any>) => void; editable?: boolean }) {
  const [cl, setCl] = useState<any>(null)
  const [edit, setEdit] = useState(false)
  const [items, setItems] = useState<any[]>([])
  const load = () => api.get('/workflow/checklists').then((r) => { const c = r.data.find((x: any) => x.code === code); setCl(c); setItems(c?.items ?? []) })
  useEffect(() => { load() }, [code]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!cl) return null
  const set = (k: string, patch: any) => onChange({ ...value, [k]: { ...(value[k] ?? {}), ...patch } })
  return (
    <div className="rounded border border-slate-200 p-2">
      <div className="mb-1 flex items-center justify-between text-xs font-semibold">{cl.title}{editable && <button className="text-grid-600" onClick={() => setEdit(true)}>Edit checklist</button>}</div>
      <ul className="space-y-1">
        {cl.items.map((it: any) => {
          const st = value[it.key]?.state ?? 'UNTICKED'
          return (
            <li key={it.key} className="text-xs">
              <div className="flex items-center gap-2">
                <select aria-label={it.text_en} className="rounded border px-1 py-0.5 text-xs" value={st} onChange={(e) => set(it.key, { state: e.target.value })}>
                  <option value="UNTICKED">☐</option><option value="TICKED">✔ Ticked</option><option value="PENDING">⏳ Pending</option>
                </select>
                <span className={st === 'TICKED' ? 'text-emerald-700' : ''}>{it.text_en}</span>
              </div>
              {st === 'PENDING' && <input aria-label="Pending comment" placeholder="Comment required for pending item" className={cls(inputCls, 'mt-1 py-0.5 text-xs')} value={value[it.key]?.comment ?? ''} onChange={(e) => set(it.key, { comment: e.target.value })} />}
            </li>
          )
        })}
      </ul>
      <Button size="sm" variant="ghost" className="mt-1" onClick={() => onChange(Object.fromEntries(cl.items.map((i: any) => [i.key, { state: 'TICKED' }])))}>Tick all</Button>
      <Modal open={edit} onClose={() => setEdit(false)} title={`Edit checklist ${code}`}>
        <div className="space-y-1">
          {items.map((it, i) => (
            <div key={i} className="flex gap-1">
              <input aria-label="Item" className={inputCls} value={it.text_en} onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, text_en: e.target.value } : x)))} />
              <Button size="sm" variant="danger" onClick={() => setItems(items.filter((_, j) => j !== i))}>✕</Button>
            </div>
          ))}
          <Button size="sm" variant="secondary" onClick={() => setItems([...items, { text_en: 'New item', mandatory: true }])}>+ Item</Button>
          <Button size="sm" onClick={() => api.put(`/workflow/checklists/${code}`, { title: cl.title, items }).then(() => { setEdit(false); load() })}>Save</Button>
        </div>
      </Modal>
    </div>
  )
}

export function CaseHeaderInfo({ c }: { c: any }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm md:grid-cols-4">
      {[['Case ID', c.case_number], ['Centre', c.centre], ['Status', <Badge key="s">{c.status}</Badge>], ['Pending with', c.pending_with_role ?? '—'],
        ['Stage', c.current_stage], ['Pending since', fmtDT(c.pending_since)], ['Created', fmtDT(c.created_at)], ['Locked', c.is_locked ? 'Yes (submitted)' : 'No']].map(([k, v], i) => (
        <div key={i}><dt className="text-xs text-slate-500">{k}</dt><dd className="font-medium">{v}</dd></div>))}
    </dl>
  )
}
