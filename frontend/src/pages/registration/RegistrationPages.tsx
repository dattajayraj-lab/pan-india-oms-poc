// Registration Module screens (TS Cl. 11.4.1; FRD REG-*).
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, errMsg } from '../../api/client'
import { useAuth } from '../../store/auth'
import { fmtDT, useAutoRefresh, useRecentPages } from '../../store/hooks'
import SpreadsheetGrid from '../../components/common/SpreadsheetGrid'
import CaseFlowchartTracker from '../../components/workflow/CaseFlowchartTracker'
import DynamicChart, { objToSeries } from '../../components/charts/DynamicChart'
import { CaseHeaderInfo, ConsentPanel, DocumentPanel } from '../../components/workflow/WorkflowPanels'
import { Alert, Badge, Button, Card, Field, LastUpdated, Modal, PageHeader, Tabs, cls, inputCls } from '../../components/common/ui'

const appCols = [
  { key: 'case_number', label: 'Case ID', render: (r: any) => <Link className="font-medium text-grid-700 hover:underline" to={`/registration/${r.application_id}`}>{r.case_number}</Link>, exportValue: (r: any) => r.case_number },
  { key: 'application_type', label: 'Type' }, { key: 'entity', label: 'Entity' }, { key: 'category', label: 'Category' },
  { key: 'nodal_centre', label: 'Nodal RLDC' }, { key: 'current_centre', label: 'With RLDC', render: (r: any) => r.current_centre !== r.nodal_centre ? <Badge color="blue">{r.current_centre} (shifted)</Badge> : r.current_centre },
  { key: 'status', label: 'Status', render: (r: any) => <Badge>{r.status}</Badge> }, { key: 'pending_with_role', label: 'Pending with' },
  { key: 'pending_since', label: 'Since', exportValue: (r: any) => fmtDT(r.pending_since), render: (r: any) => fmtDT(r.pending_since) },
]

export function RegistrationListPage() {
  useRecentPages('Registration applications')
  const [tab, setTab] = useState('')
  const { data, updatedAt } = useAutoRefresh<any[]>('/registration/applications', { app_type: tab || undefined })
  const { data: dash } = useAutoRefresh<any>('/registration/dashboard', undefined, { intervalMs: 10000 })
  return (
    <div className="space-y-4">
      <PageHeader title="Registration Module" subtitle="NSWS connectivity (CONN-4), Fees & Charges registration, communication entities."
        actions={<><LastUpdated at={updatedAt} /><Link to="/registration/new"><Button>+ New registration</Button></Link></>} />
      {dash && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card title="By status"><DynamicChart type="pie" height={180} data={objToSeries(dash.by_status)} xKey="name" series={['value']} /></Card>
          <Card title="By RLDC (current)"><DynamicChart type="bar" height={180} data={objToSeries(dash.by_centre)} xKey="name" series={['value']} /></Card>
          <Card title="By category"><DynamicChart type="bar" height={180} data={objToSeries(dash.by_category)} xKey="name" series={['value']} /></Card>
        </div>
      )}
      <Tabs active={tab} onChange={setTab} tabs={[{ key: '', label: 'All' }, { key: 'NSWS_CONNECTIVITY', label: 'NSWS / CONN-4' }, { key: 'FNC_REGISTRATION', label: 'F&C registration' }, { key: 'DIRECT_COMM', label: 'Communication' }]} />
      <SpreadsheetGrid exportName="registration_applications" rows={data ?? []} columns={appCols} />
    </div>
  )
}

export function NewRegistrationPage() {
  useRecentPages('New registration')
  const nav = useNavigate()
  const [meta, setMeta] = useState<any>(null)
  const [form, setForm] = useState<any>({ category: 'RE_GEN_STATION', sub_category: 'SOLAR', is_modified_element: false, form_data: { name_of_station: '', installed_capacity_mw: '', pooling_station: '', state: '', connectivity_reg_no: '' } })
  const [hybrid, setHybrid] = useState<string[]>([])
  const [err, setErr] = useState('')
  useEffect(() => { api.get('/registration/meta').then((r) => setMeta(r.data)) }, [])
  if (!meta) return null
  const create = async () => {
    try {
      const sub = form.sub_category === 'HYBRID' ? `HYBRID:${hybrid.join('+')}` : form.sub_category
      const { data } = await api.post('/registration/applications', { ...form, sub_category: sub })
      nav(`/registration/${data.application_id}`)
    } catch (e) { setErr(errMsg(e)) }
  }
  const fd = form.form_data
  return (
    <div className="max-w-3xl space-y-3">
      <PageHeader title="New registration (CERC RLDC Fees & Charges Regulations, 2019)" subtitle="Fill Sheet-1 details; upload documents per Sheet-2 checklist on the next page." />
      {err && <Alert kind="error">{err}</Alert>}
      <Card>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Category"><select className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value, sub_category: meta.categories[e.target.value][0] })}>{Object.keys(meta.categories).map((c) => <option key={c}>{c}</option>)}</select></Field>
          <Field label="Sub-category"><select className={inputCls} value={form.sub_category} onChange={(e) => setForm({ ...form, sub_category: e.target.value })}>{meta.categories[form.category].map((c: string) => <option key={c}>{c}</option>)}</select></Field>
          {form.sub_category === 'HYBRID' && (
            <Field label="Hybrid sources (select multiple)">
              <div className="flex gap-3 text-sm">{['SOLAR', 'WIND', 'BESS'].map((s) => <label key={s} className="flex items-center gap-1"><input type="checkbox" checked={hybrid.includes(s)} onChange={(e) => setHybrid(e.target.checked ? [...hybrid, s] : hybrid.filter((x) => x !== s))} />{s}</label>)}</div>
            </Field>
          )}
          {[['name_of_station', 'Name of generating station / park'], ['installed_capacity_mw', 'Installed capacity (MW)'], ['pooling_station', 'Pooling sub-station'], ['state', 'State'], ['connectivity_reg_no', 'Connectivity registration no.']].map(([k, l]) => (
            <Field key={k} label={l} required={k !== 'connectivity_reg_no'}><input className={inputCls} inputMode={k === 'installed_capacity_mw' ? 'decimal' : undefined} value={fd[k]} onChange={(e) => setForm({ ...form, form_data: { ...fd, [k]: k === 'installed_capacity_mw' ? e.target.value.replace(/[^0-9.]/g, '') : e.target.value } })} /></Field>))}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_modified_element} onChange={(e) => setForm({ ...form, is_modified_element: e.target.checked })} /> Modified element (fewer department consents)</label>
        </div>
        <Button className="mt-3" onClick={create}>Save draft & continue to documents</Button>
      </Card>
    </div>
  )
}

export function RegistrationDetailPage() {
  const { id } = useParams()
  useRecentPages(`Registration #${id}`)
  const { data: a, reload, updatedAt } = useAutoRefresh<any>(`/registration/applications/${id}`, undefined, { intervalMs: 5000 })
  const [err, setErr] = useState('')
  const [ctuComments, setCtuComments] = useState<Record<number, string>>({})
  const [review, setReview] = useState<Record<number, string>>({})
  const [joint, setJoint] = useState<Record<number, { source: string; text: string; on: boolean }>>({})
  const [revise, setRevise] = useState<{ id: number; note: string; file: File | null } | null>(null)
  if (!a) return null
  const run = async (fn: () => Promise<any>) => { try { await fn(); setErr(''); reload() } catch (e) { setErr(errMsg(e)) } }
  const nsws = a.application_type === 'NSWS_CONNECTIVITY'
  return (
    <div className="space-y-4">
      <PageHeader title={<>{a.case_number} <Badge>{a.status}</Badge></>} subtitle={`${a.entity} · ${a.category}/${a.sub_category}${a.nsws_ref_no ? ' · NSWS ' + a.nsws_ref_no : ''}`} actions={<LastUpdated at={updatedAt} />} />
      {err && <Alert kind="error">{err}</Alert>}
      <Card title="Case tracking"><CaseHeaderInfo c={a} /><div className="mt-3"><CaseFlowchartTracker steps={a.tracker} /></div></Card>
      {a.shifts.length > 0 && (
        <Card title="NLDC workload shifting log">
          <SpreadsheetGrid exportName="shift_log" compact rows={a.shifts} columns={[{ key: 'from', label: 'From' }, { key: 'to', label: 'Validated by' }, { key: 'shifted_at', label: 'Shifted', exportValue: (r) => fmtDT(r.shifted_at) }, { key: 'nldc_comment', label: 'NLDC comment' }, { key: 'returned_at', label: 'Returned', exportValue: (r) => fmtDT(r.returned_at) }, { key: 'return_comment', label: 'RLDC comment' }]} />
        </Card>
      )}
      {nsws ? (
        <Card title="Model files - file-wise validation (CTUIL ↔ RLDC → joint comments)" actions={<>
          {a.is_ctu && !a.ctu_shared_with_rldc && <Button size="sm" onClick={() => run(() => api.post(`/registration/applications/${id}/ctu-submit`, { comments: ctuComments }))}>Submit to RLDC</Button>}
          {a.is_ctu && <Button size="sm" variant="secondary" onClick={() => run(() => api.post(`/registration/applications/${id}/joint-comments`, { items: Object.entries(joint).filter(([, v]) => v.on).map(([k, v]) => ({ file_id: Number(k), source: v.source, text: v.text })) }))}>Release joint comments (selected)</Button>}
          {a.is_ctu && <Button size="sm" variant="success" onClick={() => run(() => api.post(`/registration/applications/${id}/complete`))}>Issue CONN-4</Button>}
        </>}>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead className="bg-slate-100 text-left"><tr><th className="px-2 py-1">File category</th><th className="px-2 py-1">Iter.</th>{!a.is_requester && <><th className="px-2 py-1">RLDC</th><th className="px-2 py-1">CTUIL</th></>}<th className="px-2 py-1">Joint comment</th><th className="px-2 py-1">Action</th></tr></thead>
              <tbody>
                {a.files.map((f: any) => (
                  <tr key={f.id} className="border-t align-top">
                    <td className="px-2 py-1 font-medium">{f.file_category}{f.requester_change_note && <div className="text-[10px] text-slate-500">Change: {f.requester_change_note}</div>}</td>
                    <td className="px-2 py-1">{f.iteration}</td>
                    {!a.is_requester && <>
                      <td className="px-2 py-1"><Badge>{f.rldc_status}</Badge><div className="text-[10px]">{f.rldc_comment}</div></td>
                      <td className="px-2 py-1"><Badge>{f.ctu_status}</Badge><div className="text-[10px]">{f.ctu_comment}</div></td>
                    </>}
                    <td className="px-2 py-1">{f.joint_released ? <><Badge color="blue">Released</Badge> {f.joint_comment}</> : '—'}</td>
                    <td className="space-y-1 px-2 py-1">
                      {a.is_ctu && !a.ctu_shared_with_rldc && <input aria-label="CTU comment" placeholder="CTUIL comment" className={cls(inputCls, 'py-0.5 text-xs')} value={ctuComments[f.id] ?? ''} onChange={(e) => setCtuComments({ ...ctuComments, [f.id]: e.target.value })} />}
                      {(a.is_coordinator || a.is_ctu) && a.ctu_shared_with_rldc && (
                        <div className="flex gap-1">
                          <input aria-label="Review comment" placeholder="comment" className={cls(inputCls, 'py-0.5 text-xs')} value={review[f.id] ?? ''} onChange={(e) => setReview({ ...review, [f.id]: e.target.value })} />
                          {['APPROVED', 'NEEDS_REVISION'].map((s) => <Button key={s} size="sm" variant={s === 'APPROVED' ? 'success' : 'warning'} onClick={() => run(() => api.post(`/registration/files/${f.id}/review`, { reviewer: a.is_ctu ? 'CTU' : 'RLDC', status: s, comment: review[f.id] ?? '' }))}>{s === 'APPROVED' ? '✔' : '↺'}</Button>)}
                        </div>
                      )}
                      {a.is_ctu && (
                        <div className="flex items-center gap-1">
                          <input type="checkbox" aria-label="Release" checked={joint[f.id]?.on ?? false} onChange={(e) => setJoint({ ...joint, [f.id]: { source: joint[f.id]?.source ?? 'CTU', text: joint[f.id]?.text ?? '', on: e.target.checked } })} />
                          <select aria-label="Joint source" className="rounded border text-xs" value={joint[f.id]?.source ?? 'CTU'} onChange={(e) => setJoint({ ...joint, [f.id]: { ...(joint[f.id] ?? { text: '', on: true }), source: e.target.value } })}><option>CTU</option><option>RLDC</option><option>MANUAL</option></select>
                          {joint[f.id]?.source === 'MANUAL' && <input aria-label="Manual joint comment" className={cls(inputCls, 'py-0.5 text-xs')} value={joint[f.id]?.text ?? ''} onChange={(e) => setJoint({ ...joint, [f.id]: { ...joint[f.id], text: e.target.value } })} />}
                        </div>
                      )}
                      {(a.is_requester || a.is_ctu) && f.joint_released && <Button size="sm" variant="secondary" onClick={() => setRevise({ id: f.id, note: '', file: null })}>Upload revised</Button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <>
          {a.consent_summary.length > 0 && (
            <Card title="Consent status (visible to all coordinators)">
              <div className="flex flex-wrap gap-2">{a.consent_summary.map((c: any) => <span key={c.department} className="text-xs"><b>{c.department}</b> <Badge>{c.status}</Badge> {c.remarks && <i>“{c.remarks}”</i>}</span>)}</div>
            </Card>
          )}
          <ConsentPanel consents={a.consents} actUrl={(cid) => `/registration/applications/${id}/consents/${cid}`} onChange={reload} title="Department consents (SO-1, SO-2, MO, SCADA, MIS)" />
          <Card title="Applicant actions" actions={<>
            {!a.is_locked && a.is_requester && <Button onClick={() => run(() => api.post(`/registration/applications/${id}/submit`))}>Submit application</Button>}
            {a.is_coordinator && a.status !== 'APPROVED' && <Button variant="success" onClick={() => run(() => api.post(`/registration/applications/${id}/issue-letter`))}>Issue registration letter</Button>}
          </>}>
            <dl className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">{Object.entries(a.form_data ?? {}).map(([k, v]) => <div key={k}><dt className="text-xs text-slate-500">{k}</dt><dd>{String(v)}</dd></div>)}</dl>
          </Card>
        </>
      )}
      <DocumentPanel docs={a.documents} uploadUrl={nsws ? undefined : `/registration/applications/${id}/documents`} categories={a.doc_types}
        required={nsws ? undefined : ['SHEET1_FORM', 'UNDERTAKING']} onChange={reload} canUpload={!nsws && (!a.is_locked || !a.is_requester)} title="Documents (auto-named, all revisions kept)" />
      <Modal open={!!revise} onClose={() => setRevise(null)} title="Upload revised file">
        {revise && <div className="space-y-2">
          <Field label="What changed in this revision" required><input className={inputCls} value={revise.note} onChange={(e) => setRevise({ ...revise, note: e.target.value })} /></Field>
          <input type="file" aria-label="Revised file" onChange={(e) => setRevise({ ...revise, file: e.target.files?.[0] ?? null })} />
          <Button disabled={!revise.file || revise.note.length < 3} onClick={() => run(async () => { const fd = new FormData(); fd.append('change_note', revise.note); fd.append('file', revise.file!); await api.post(`/registration/files/${revise.id}/revise`, fd); setRevise(null) })}>Upload</Button>
        </div>}
      </Modal>
    </div>
  )
}

export function NswsPage() {
  useRecentPages('NSWS connectivity')
  const { hasRole } = useAuth()
  const [ref, setRef] = useState('NSWS-RE-' + new Date().getFullYear() + '-' + String(Math.floor(Math.random() * 9000) + 1000))
  const [centre, setCentre] = useState('NRLDC')
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const nav = useNavigate()
  const { data } = useAutoRefresh<any[]>('/registration/applications', { app_type: 'NSWS_CONNECTIVITY' })
  return (
    <div className="space-y-4">
      <PageHeader title="Connectivity applications from NSWS (CONN-4)" subtitle="CTUIL acknowledges on NSWS; data and segregated model files are fetched by API." />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {hasRole('CTU') && (
        <Card title="Acknowledge & pull from NSWS (mock API)">
          <div className="flex flex-wrap items-end gap-2">
            <Field label="NSWS registration no."><input className={inputCls} value={ref} onChange={(e) => setRef(e.target.value.toUpperCase())} /></Field>
            <Field label="Nodal RLDC"><select className={inputCls} value={centre} onChange={(e) => setCentre(e.target.value)}>{['NRLDC', 'ERLDC', 'WRLDC', 'SRLDC', 'NERLDC'].map((c) => <option key={c}>{c}</option>)}</select></Field>
            <Button onClick={async () => { try { const { data } = await api.post('/registration/nsws/sync', { nsws_ref_no: ref, nodal_centre: centre }); nav(`/registration/${data.application_id}`) } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) } }}>Fetch from NSWS</Button>
          </div>
        </Card>
      )}
      <SpreadsheetGrid exportName="nsws_applications" rows={data ?? []} columns={[...appCols, { key: 'files', label: 'CTU approved', render: (r: any) => `${r.files_ctu_approved}/${r.files_total}` }]} />
    </div>
  )
}

export function WorkloadPage() {
  useRecentPages('NLDC workload shifting')
  const { data, reload, updatedAt } = useAutoRefresh<any[]>('/registration/workload')
  const [sel, setSel] = useState<number[]>([])
  const [to, setTo] = useState('WRLDC')
  const [comment, setComment] = useState('')
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  return (
    <div className="space-y-4">
      <PageHeader title="RE application workload across RLDCs" subtitle="NLDC Registration Coordinator shifts unstarted RE applications from heavily to lightly loaded RLDCs; they return automatically after model validation." actions={<LastUpdated at={updatedAt} />} />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {data && <Card title="Pending RE applications per RLDC"><DynamicChart type="stacked" height={220} xKey="centre" series={['unstarted', 'started']} data={data.map((c) => ({ centre: c.centre, unstarted: c.unstarted, started: c.pending - c.unstarted }))} /></Card>}
      <Card title="Select applications to shift" actions={<>
        <select aria-label="Target RLDC" className={cls(inputCls, 'w-32')} value={to} onChange={(e) => setTo(e.target.value)}>{['NRLDC', 'ERLDC', 'WRLDC', 'SRLDC', 'NERLDC'].map((c) => <option key={c}>{c}</option>)}</select>
        <input aria-label="NLDC comment" placeholder="NLDC comment" className={cls(inputCls, 'w-56')} value={comment} onChange={(e) => setComment(e.target.value)} />
        <Button disabled={!sel.length || comment.length < 3} onClick={async () => { try { const r = await api.post('/registration/shift', { application_ids: sel, to_centre: to, comment }); setMsg({ kind: 'success', text: `Shifted: ${r.data.moved.join(', ')}` }); setSel([]); reload() } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) } }}>Shift to {to}</Button>
      </>}>
        {(data ?? []).map((c) => (
          <div key={c.centre} className="mb-2">
            <div className="text-xs font-semibold">{c.centre} · {c.pending} pending ({c.unstarted} not started)</div>
            {c.applications.map((a: any) => (
              <label key={a.application_id} className={cls('ml-3 flex items-center gap-2 text-xs', a.processing_started && 'text-slate-400')}>
                <input type="checkbox" disabled={a.processing_started} checked={sel.includes(a.application_id)} onChange={(e) => setSel(e.target.checked ? [...sel, a.application_id] : sel.filter((x) => x !== a.application_id))} />
                {a.case_number} · {a.entity} {a.processing_started && '(processing started - cannot shift)'}{a.current_centre !== a.nodal_centre && <Badge color="blue">from {a.nodal_centre}</Badge>}
              </label>
            ))}
          </div>
        ))}
      </Card>
    </div>
  )
}

export function FncImportPage() {
  useRecentPages('Fees & Charges import')
  const [prev, setPrev] = useState<any>(null)
  const [done, setDone] = useState<any>(null)
  const [err, setErr] = useState('')
  const upload = async (f: File) => {
    const fd = new FormData(); fd.append('file', f)
    try { setPrev((await api.post('/registration/fnc-import/preview', fd)).data); setDone(null); setErr('') } catch (e) { setErr(errMsg(e)) }
  }
  return (
    <div className="space-y-4">
      <PageHeader title="Import from RLDC Fees & Charges software" subtitle="Defined Excel template → preview with row errors → commit creates entities and login IDs (default password, forced change)." />
      {err && <Alert kind="error">{err}</Alert>}
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={() => import('../../api/client').then((m) => m.download('/registration/fnc-import/template', 'fnc_import_template.xlsx'))}>Download template</Button>
          <input type="file" accept=".xlsx" aria-label="F&C Excel" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </div>
      </Card>
      {prev && !done && (
        <Card title={`Preview: ${prev.valid} valid row(s), ${prev.errors.length} with errors`} actions={<Button disabled={!prev.valid} onClick={async () => setDone((await api.post(`/registration/fnc-import/${prev.batch_id}/commit`)).data)}>Commit valid rows</Button>}>
          <SpreadsheetGrid exportName="fnc_preview" compact rows={prev.rows} rowClassName={(r) => (r.errors.length ? 'bg-red-50' : '')} columns={[{ key: 'row', label: 'Row' }, { key: 'Registration No', label: 'Reg. No' }, { key: 'Entity Name', label: 'Entity' }, { key: 'Entity Type', label: 'Type' }, { key: 'E-mail', label: 'E-mail' }, { key: 'errors', label: 'Errors', exportValue: (r) => r.errors.join('; '), render: (r) => r.errors.length ? <span className="text-red-700">{r.errors.join('; ')}</span> : <Badge color="green">OK</Badge> }]} />
        </Card>
      )}
      {done && <Card title="Logins generated (e-mailed to entities)"><SpreadsheetGrid exportName="fnc_logins" rows={done.created} columns={[{ key: 'entity', label: 'Entity' }, { key: 'username', label: 'Username' }, { key: 'temp_password', label: 'Default password (POC display)' }]} /></Card>}
    </div>
  )
}

export function AccountRequestsPage() {
  useRecentPages('User-ID requests')
  const { data, reload } = useAutoRefresh<any[]>('/registration/account-requests', undefined, { intervalMs: 5000 })
  const decide = (id: number, approve: boolean) => api.post(`/registration/account-requests/${id}/decide`, { approve, extra_user_types: approve ? ['OUTAGE'] : [] }).then(reload)
  return (
    <div>
      <PageHeader title="Pre-registration / user-ID requests" subtitle="Approve with role & rights; multiple permissions can be assigned to one login." />
      <SpreadsheetGrid exportName="account_requests" rows={data ?? []} columns={[{ key: 'username', label: 'Username' }, { key: 'name', label: 'Name' }, { key: 'organisation', label: 'Organisation' }, { key: 'user_type', label: 'Type' }, { key: 'centre', label: 'RLDC' }, { key: 'nsws_reg_no', label: 'NSWS' }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> }, { key: 'created_at', label: 'Requested', exportValue: (r) => fmtDT(r.created_at) },
        { key: 'x', label: 'Decision', render: (r) => r.status === 'PENDING' ? <div className="flex gap-1"><Button size="sm" variant="success" onClick={() => decide(r.id, true)}>Approve</Button><Button size="sm" variant="danger" onClick={() => decide(r.id, false)}>Reject</Button></div> : null }]} />
    </div>
  )
}

export function SignupPage() {
  const [f, setF] = useState<any>({ user_type: 'RE_REGISTRATION', organisation: '', first_name: '', last_name: '', mobile: '', username: '', email: '', password: '', confirm_password: '', centre_code: 'NRLDC', nsws_reg_no: '', cea_egen_no: '', fnc_reg_no: '', connectivity_reg_no: '' })
  const [avail, setAvail] = useState<boolean | null>(null)
  const [cap, setCap] = useState<any>(null)
  const [ans, setAns] = useState('')
  const [res, setRes] = useState<any>(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.get('/auth/captcha').then((r) => setCap(r.data)) }, [])
  useEffect(() => {
    if (f.username.length < 4) return setAvail(null)
    const t = setTimeout(() => api.get('/auth/username-available', { params: { username: f.username } }).then((r) => setAvail(r.data.available)), 300)
    return () => clearTimeout(t)
  }, [f.username])
  const submit = async () => {
    try { setRes((await api.post('/registration/signup', { ...f, captcha_token: cap?.captcha_token, captcha_answer: ans })).data); setErr('') } catch (e) { setErr(errMsg(e)); api.get('/auth/captcha').then((r) => setCap(r.data)) }
  }
  const field = (k: string, label: string, type = 'text') => <Field label={label}><input type={type} className={inputCls} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></Field>
  return (
    <div className="min-h-screen bg-slate-50 p-4">
      <div className="mx-auto max-w-2xl rounded-lg bg-white p-6 shadow">
        <Link to="/welcome" className="text-xs text-grid-600">← Grid-India OMS</Link>
        <h1 className="mb-3 text-xl font-bold text-grid-800">Stakeholder pre-registration / उपयोगकर्ता पंजीकरण</h1>
        {res ? <Alert kind="success">{res.message} Request #{res.id} submitted at {fmtDT(res.submitted_at)}. You will be informed by e-mail after approval by RLDC.</Alert> : (
          <div className="grid gap-3 md:grid-cols-2">
            {err && <div className="md:col-span-2"><Alert kind="error">{err}</Alert></div>}
            <Field label="User type"><select className={inputCls} value={f.user_type} onChange={(e) => setF({ ...f, user_type: e.target.value })}>{['RE_REGISTRATION', 'FTC', 'OUTAGE', 'COMM', 'PROTECTION', 'AVAILABILITY'].map((x) => <option key={x}>{x}</option>)}</select></Field>
            {field('organisation', 'Organisation')}{field('first_name', 'First name')}{field('last_name', 'Last name')}
            {field('mobile', 'Mobile')}{field('email', 'E-mail', 'email')}
            <Field label="Login name" hint={avail === null ? '' : avail ? '✓ available' : '✗ not available'}><input className={inputCls} value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} /></Field>
            <Field label="RLDC"><select className={inputCls} value={f.centre_code} onChange={(e) => setF({ ...f, centre_code: e.target.value })}>{['NRLDC', 'ERLDC', 'WRLDC', 'SRLDC', 'NERLDC', 'NLDC'].map((c) => <option key={c}>{c}</option>)}</select></Field>
            {field('password', 'Password', 'password')}{field('confirm_password', 'Confirm password', 'password')}
            {field('nsws_reg_no', 'NSWS registration no.')}{field('cea_egen_no', 'CEA e-GEN no.')}{field('fnc_reg_no', 'F&C registration no.')}{field('connectivity_reg_no', 'Connectivity registration no.')}
            <div className="flex items-center gap-2 md:col-span-2"><span className="rounded bg-slate-800 px-2 py-1 font-mono text-xs text-amber-200">{cap?.question}</span><input aria-label="captcha answer" className={cls(inputCls, 'w-20')} value={ans} onChange={(e) => setAns(e.target.value)} /><Button onClick={submit} disabled={avail === false}>Submit request</Button></div>
          </div>
        )}
      </div>
    </div>
  )
}
