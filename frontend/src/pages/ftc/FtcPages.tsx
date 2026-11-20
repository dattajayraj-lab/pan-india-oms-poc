// First Time Charging screens: 5-stage wizard, A2 element grid with duplicate helper, Format TR, consents, certificate (TS Cl. 11.4.2; FRD FTC-*).
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, download, errMsg } from '../../api/client'
import { useAuth } from '../../store/auth'
import { fmtDT, useAutoRefresh, useRecentPages } from '../../store/hooks'
import SpreadsheetGrid from '../../components/common/SpreadsheetGrid'
import CaseFlowchartTracker from '../../components/workflow/CaseFlowchartTracker'
import DynamicChart, { objToSeries } from '../../components/charts/DynamicChart'
import { CaseHeaderInfo, ChecklistPanel, ConsentPanel, DocumentPanel } from '../../components/workflow/WorkflowPanels'
import { Alert, Badge, Button, Card, Field, LastUpdated, PageHeader, Stat, Tabs, cls, inputCls } from '../../components/common/ui'

const CHECKLIST_FOR: Record<number, string | null> = { 1: 'FTC_A_COORD', 2: 'FTC_B_COORD', 3: 'FTC_C_COORD', 4: null, 5: null }

export function FtcListPage() {
  useRecentPages('FTC cases')
  const { data, updatedAt } = useAutoRefresh<any[]>('/ftc/cases')
  const { data: dash } = useAutoRefresh<any>('/ftc/dashboard', undefined, { intervalMs: 10000 })
  return (
    <div className="space-y-4">
      <PageHeader title="First Time Charging (FTC)" subtitle="IEGC 2023 procedure: A → B (+Format TR) → C → certificate → DOCO; NLDC/RLDC jurisdiction routed automatically."
        actions={<><LastUpdated at={updatedAt} /><Link to="/ftc/new"><Button>+ New FTC application</Button></Link></>} />
      {dash && (
        <div className="grid gap-3 md:grid-cols-4">
          <Stat label="FTC cases" value={dash.total} /><Stat label="Dept. acceptances" value={dash.accepted} tone="green" />
          <Stat label="Dept. returns" value={dash.returned} tone="red" /><Stat label="Avg clearance (days)" value={dash.avg_clearance_days} />
          <Card title="Cases by stage" className="md:col-span-2"><DynamicChart type="bar" height={170} data={objToSeries(dash.by_stage)} xKey="name" series={['value']} /></Card>
          <Card title="Rejection/return causes by department" className="md:col-span-2"><DynamicChart type="pie" height={170} data={objToSeries(dash.return_by_department)} xKey="name" series={['value']} /></Card>
        </div>
      )}
      <SpreadsheetGrid exportName="ftc_cases" rows={data ?? []} columns={[
        { key: 'case_number', label: 'FTC Case ID', render: (r) => <Link className="font-medium text-grid-700 hover:underline" to={`/ftc/${r.ftc_id}`}>{r.case_number}</Link>, exportValue: (r) => r.case_number },
        { key: 'entity', label: 'User / entity' }, { key: 'title', label: 'Elements brief' }, { key: 'jurisdiction', label: 'Code by', render: (r) => <Badge color={r.jurisdiction === 'NLDC' ? 'purple' : 'blue'}>{r.jurisdiction}</Badge> },
        { key: 'stage', label: 'Stage', render: (r) => `Stage ${r.stage}` }, { key: 'stage_status', label: 'Stage status', render: (r) => <Badge>{r.stage_status}</Badge> },
        { key: 'pending_with_role', label: 'Pending with' }, { key: 'created_at', label: 'Request date', exportValue: (r) => fmtDT(r.created_at), render: (r) => fmtDT(r.created_at) },
      ]} />
    </div>
  )
}

export function NewFtcPage() {
  useRecentPages('New FTC application')
  const nav = useNavigate()
  const { user } = useAuth()
  const [entities, setEntities] = useState<any[]>([])
  const [f, setF] = useState({ element_category: 'RE_PLANT', proposed_charging_date: '', title: '', entity_id: '' })
  const [err, setErr] = useState('')
  useEffect(() => { if (!user?.is_external) api.get('/master/entities').then((r) => setEntities(r.data)) }, [user])
  const create = async () => {
    try { const { data } = await api.post('/ftc/cases', { ...f, entity_id: f.entity_id ? Number(f.entity_id) : undefined }); nav(`/ftc/${data.ftc_id}`) } catch (e) { setErr(errMsg(e)) }
  }
  return (
    <div className="max-w-xl space-y-3">
      <PageHeader title="New FTC application" subtitle="A unique FTC Case ID is generated; fill A-annexures online next." />
      {err && <Alert kind="error">{err}</Alert>}
      <Card>
        <div className="space-y-3">
          {!user?.is_external && <Field label="Applicant entity"><select className={inputCls} value={f.entity_id} onChange={(e) => setF({ ...f, entity_id: e.target.value })}><option value="">—</option>{entities.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></Field>}
          <Field label="Category"><select className={inputCls} value={f.element_category} onChange={(e) => setF({ ...f, element_category: e.target.value })}><option value="RE_PLANT">RE plant</option><option value="NON_RE_PLANT">Non-RE plant</option><option value="TRANSMISSION">Transmission elements</option></select></Field>
          <Field label="Proposed charging date" required hint="A-annexures must be submitted at least 10 days before this date"><input type="date" className={inputCls} value={f.proposed_charging_date} onChange={(e) => setF({ ...f, proposed_charging_date: e.target.value })} /></Field>
          <Field label="Short title"><input className={inputCls} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Button onClick={create} disabled={!f.proposed_charging_date}>Create FTC case</Button>
        </div>
      </Card>
    </div>
  )
}

function A2Editor({ c, onChange }: { c: any; onChange: () => void }) {
  const [rows, setRows] = useState<any[]>(c.a2_elements)
  const [types, setTypes] = useState<any[]>([])
  const [subs, setSubs] = useState<any[]>([])
  const [err, setErr] = useState('')
  useEffect(() => { setRows(c.a2_elements) }, [c.a2_elements])
  useEffect(() => { api.get('/master/element-types').then((r) => setTypes(r.data)); api.get('/master/substations').then((r) => setSubs(r.data)) }, [])
  const save = async (next = rows) => { try { const r = await api.put(`/ftc/cases/${c.ftc_id}/annexure/A2`, { elements: next }); setErr(''); onChange(); return r } catch (e) { setErr(errMsg(e)) } }
  const blank = { name: '', element_type: 'AC_LINE', voltage_kv: 400, rating: '', length_km: '', from_substation_id: '', to_substation_id: '', is_inter_regional: false }
  const locked = c.is_locked || c.stage !== 1
  return (
    <Card title={<>Annexure A2: elements to be charged <Badge color={c.jurisdiction === 'NLDC' ? 'purple' : 'blue'}>Code: {c.jurisdiction}</Badge> <Badge color="slate">Certificate: {c.cert_jurisdiction}</Badge></>}
      actions={!locked && <><Button size="sm" variant="secondary" onClick={() => setRows([...rows, blank])}>+ Row</Button><Button size="sm" onClick={() => save()}>Save A2</Button></>}>
      {err && <div className="mb-2"><Alert kind="error">{err}</Alert></div>}
      <SpreadsheetGrid exportName="annexure_A2" rows={rows.map((r, i) => ({ ...r, _i: i }))} compact
        onCellEdit={locked ? undefined : (row, key, v) => setRows(rows.map((r, i) => (i === row._i ? { ...r, [key]: key === 'voltage_kv' || key === 'length_km' ? Number(v) || '' : key === 'is_inter_regional' ? v === 'true' : v } : r)))}
        onBulkPaste={locked ? undefined : (pasted) => { const next = [...rows, ...pasted.map((p) => ({ ...blank, ...p, voltage_kv: Number(p.voltage_kv) || 400 }))]; setRows(next); save(next) }}
        columns={[
          { key: 'name', label: 'Element name', editable: true },
          { key: 'element_type', label: 'Type', editable: true, options: types.map((t) => t.code) },
          { key: 'voltage_kv', label: 'kV', editable: true, type: 'number' },
          { key: 'rating', label: 'Rating', editable: true },
          { key: 'length_km', label: 'Length km', editable: true, type: 'number' },
          { key: 'from_substation_id', label: 'From S/S id', editable: true, options: subs.map((s) => String(s.id)) },
          { key: 'to_substation_id', label: 'To S/S id', editable: true, options: subs.map((s) => String(s.id)) },
          { key: 'is_inter_regional', label: 'Inter-regional', editable: true, options: ['true', 'false'] },
          { key: 'dup', label: 'Duplicate', render: (r) => !locked && <Button size="sm" variant="ghost" onClick={async () => { await api.post(`/ftc/cases/${c.ftc_id}/a2/duplicate`, { index: r._i, count: 1 }); onChange() }}>⧉ Copy</Button> },
        ]} />
      <p className="mt-1 text-[11px] text-slate-500">Substation ids: {subs.slice(0, 8).map((s) => `${s.id}=${s.name}`).join(', ')} … · Unique Element IDs are generated in the master DB when Stage 1 is accepted.</p>
    </Card>
  )
}

export function FtcDetailPage() {
  const { id } = useParams()
  useRecentPages(`FTC #${id}`)
  const { data: c, reload, updatedAt } = useAutoRefresh<any>(`/ftc/cases/${id}`, undefined, { intervalMs: 5000 })
  const [err, setErr] = useState('')
  const [ok, setOk] = useState('')
  const [chk, setChk] = useState<Record<string, any>>({})
  const [remarks, setRemarks] = useState('')
  const [nldc, setNldc] = useState(false)
  const [tr, setTr] = useState({ trial_run_date: '', quantum_mw: '', remarks: '' })
  const [pre, setPre] = useState({ 'Trial run period': '', 'Trial run result': 'Successful', 'Max MW during trial': '' })
  const [a1, setA1] = useState<Record<string, string>>({})
  const [issue, setIssue] = useState('')
  const [tab, setTab] = useState('stage')
  useEffect(() => { if (c) setA1(c.annexures?.A1 ?? { expected_date: '', contact_person: '', documents_list: '' }) }, [c?.ftc_id]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!c) return null
  const run = async (fn: () => Promise<any>, success = '') => { try { await fn(); setErr(''); setOk(success); reload() } catch (e) { setErr(errMsg(e)); setOk('') } }
  const st = c.stages.find((s: any) => s.no === c.stage)
  const coord = c.is_coordinator
  return (
    <div className="space-y-4">
      <PageHeader title={<>{c.case_number} <Badge>{c.status}</Badge> <Badge color="purple">Stage {c.stage}</Badge></>} subtitle={`${c.entity} · ${c.element_category} · proposed charging ${c.proposed_charging_date}`} actions={<LastUpdated at={updatedAt} />} />
      <div className="flex flex-wrap gap-1">
        {c.stages.map((s: any) => <span key={s.no} className={cls('rounded px-2 py-1 text-xs font-medium', s.no < c.stage ? 'bg-emerald-100 text-emerald-800' : s.no === c.stage ? 'bg-grid-700 text-white' : 'bg-slate-100 text-slate-500')}>{s.no}. {s.name.replace(/^Stage \d - /, '')}</span>)}
      </div>
      {err && <Alert kind="error">{err}</Alert>}{ok && <Alert kind="success">{ok}</Alert>}
      <Card title="Status tracking"><CaseHeaderInfo c={c} /><div className="mt-3"><CaseFlowchartTracker steps={c.tracker} /></div></Card>
      <Tabs active={tab} onChange={setTab} tabs={[{ key: 'stage', label: st.name }, { key: 'docs', label: 'All documents', count: c.documents.length }, { key: 'elements', label: 'Elements', count: c.created_elements.length }, { key: 'post', label: 'Post-commissioning & issues' }]} />

      {tab === 'stage' && (<>
        {c.stage === 1 && (<>
          <Card title="Annexure A1 (fillable)" actions={!c.is_locked && <><Button size="sm" variant="secondary" onClick={() => run(() => api.put(`/ftc/cases/${id}/annexure/A1`, a1), 'A1 saved')}>Save</Button><Button size="sm" onClick={() => run(() => api.post(`/ftc/cases/${id}/generate/A1`), 'A1 PDF generated - sign and upload it')}>Generate PDF</Button></>}>
            <div className="grid gap-2 md:grid-cols-3">{Object.entries(a1).map(([k, v]) => <Field key={k} label={k.replace(/_/g, ' ')}><input disabled={c.is_locked} className={inputCls} value={v} onChange={(e) => setA1({ ...a1, [k]: e.target.value })} /></Field>)}</div>
          </Card>
          <A2Editor c={c} onChange={reload} />
        </>)}
        {c.stage === 2 && (
          <Card title={<>Trial-run notice (Format TR) <Badge>{c.format_tr_status}</Badge></>} actions={coord && c.format_tr_status === 'SUBMITTED' && <Button size="sm" variant="success" onClick={() => run(() => { const fd = new FormData(); fd.append('approve', 'true'); return api.post(`/ftc/cases/${id}/format-tr/decide`, fd) })}>Approve Format TR</Button>}>
            <p className="mb-2 text-xs text-slate-600">At least 7 working days before the trial run (IEGC Cl. 21). Stays open for withdrawal/re-upload; every version is kept. Current: {c.format_tr_date ?? '—'}</p>
            {c.is_requester && <div className="flex flex-wrap items-end gap-2">
              <Field label="Trial-run date"><input type="date" className={inputCls} value={tr.trial_run_date} onChange={(e) => setTr({ ...tr, trial_run_date: e.target.value })} /></Field>
              <Field label="Quantum (MW)"><input className={inputCls} inputMode="decimal" value={tr.quantum_mw} onChange={(e) => setTr({ ...tr, quantum_mw: e.target.value.replace(/[^0-9.]/g, '') })} /></Field>
              <Field label="Remarks"><input className={inputCls} value={tr.remarks} onChange={(e) => setTr({ ...tr, remarks: e.target.value })} /></Field>
              <Button onClick={() => run(() => api.post(`/ftc/cases/${id}/format-tr`, { ...tr, quantum_mw: Number(tr.quantum_mw) }), 'Format TR submitted and utilities notified')}>Submit notice</Button>
            </div>}
          </Card>
        )}
        {c.stage === 4 && coord && (
          <Card title="Pre-certificate (FTC Coordinator)" actions={<Button size="sm" onClick={() => run(() => api.put(`/ftc/cases/${id}/pre-certificate`, pre), 'Pre-certificate prepared')}>Save pre-certificate</Button>}>
            <div className="grid gap-2 md:grid-cols-3">{Object.entries(pre).map(([k, v]) => <Field key={k} label={k}><input className={inputCls} value={v} onChange={(e) => setPre({ ...pre, [k]: e.target.value })} /></Field>)}</div>
          </Card>
        )}
        {c.stage === 4 && c.stage_status === 'AWAITING_SIGNATURE' && (
          <Alert kind="warning">Certificate auto-generated (not visible to user). Head of RLDC must sign. {c.can_sign && <Button size="sm" className="ml-2" onClick={() => run(() => api.post(`/ftc/cases/${id}/sign-certificate`), 'Certificate signed and released')}>Digitally sign certificate</Button>}</Alert>
        )}
        <DocumentPanel docs={c.documents.filter((d: any) => st.annexures.some((a: any) => d.doc_category.startsWith(a.code)) || d.doc_category.startsWith('RLDC_'))}
          uploadUrl={`/ftc/cases/${id}/documents`} categories={[...st.annexures.map((a: any) => a.code), ...(c.is_requester ? [] : ['RLDC_UPLOAD'])]}
          labels={Object.fromEntries(st.annexures.map((a: any) => [a.code, a.label]))} required={st.annexures.filter((a: any) => a.required).map((a: any) => a.code)}
          canUpload={!c.is_locked || !c.is_requester || c.stage === 5} onChange={reload} title={`${st.name}: signed annexures & documents`} />
        <Card title="Actions">
          <div className="flex flex-wrap items-start gap-3">
            {c.is_requester && !c.is_locked && c.stage < 4 && <Button onClick={() => run(() => api.post(`/ftc/cases/${id}/submit`), 'Submitted to FTC Coordinator; application locked')}>Submit {st.name.split(' - ')[0]}</Button>}
            {coord && c.status === 'SUBMITTED' && c.stage <= 3 && CHECKLIST_FOR[c.stage] && (
              <div className="w-full max-w-xl"><ChecklistPanel code={CHECKLIST_FOR[c.stage]!} value={chk} onChange={setChk} editable /></div>
            )}
            {coord && (
              <div className="flex flex-wrap items-center gap-2">
                <input aria-label="Coordinator remarks" placeholder="Coordinator remarks" className={cls(inputCls, 'w-64')} value={remarks} onChange={(e) => setRemarks(e.target.value)} />
                {c.stage <= 2 && <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={nldc} onChange={(e) => setNldc(e.target.checked)} />Include NLDC consent{c.jurisdiction === 'NLDC' && ' (mandatory: NLDC jurisdiction)'}</label>}
                {(c.status === 'SUBMITTED' || (c.stage === 4 && c.stage_status === 'DRAFT')) && <Button onClick={() => run(() => api.post(`/ftc/cases/${id}/coordinator`, { action: 'FORWARD', checklist: chk, remarks, include_nldc: nldc }), 'Forwarded for departmental consent')}>Forward to departments</Button>}
                {['SUBMITTED', 'UNDER_REVIEW'].includes(c.status) && <Button variant="warning" onClick={() => run(() => api.post(`/ftc/cases/${id}/coordinator`, { action: 'RETURN', remarks }), 'Returned to user')}>Return to user</Button>}
                {c.status === 'UNDER_REVIEW' && <Button variant="success" onClick={() => run(() => api.post(`/ftc/cases/${id}/coordinator`, { action: 'ACCEPT', remarks }), 'Stage accepted')}>Accept stage</Button>}
                {c.stage === 3 && <Button variant="secondary" onClick={() => run(() => api.post(`/ftc/cases/${id}/send-to-beneficiaries`), 'C-annexures e-mailed to beneficiaries')}>Send C-annexures to beneficiaries</Button>}
                {c.stage === 5 && c.doco_status === 'SUBMITTED' && <><Button variant="success" onClick={() => run(() => { const fd = new FormData(); fd.append('approve', 'true'); return api.post(`/ftc/cases/${id}/doco/decide`, fd) }, 'DOCO accepted')}>Accept DOCO</Button><Button variant="warning" onClick={() => run(() => { const fd = new FormData(); fd.append('approve', 'false'); fd.append('remarks', remarks); return api.post(`/ftc/cases/${id}/doco/decide`, fd) })}>Return DOCO</Button></>}
              </div>
            )}
          </div>
        </Card>
        <ConsentPanel consents={c.consents} actUrl={(cid) => `/ftc/cases/${id}/consents/${cid}`} onChange={reload} title="Departmental consents (not visible to applicant)" />
      </>)}

      {tab === 'docs' && <DocumentPanel docs={c.documents} categories={['OTHER']} canUpload={false} onChange={reload} title="All documents (sorted by date/time)" />}
      {tab === 'elements' && (
        <Card title="Elements created in master database from Annexure A2">
          <SpreadsheetGrid exportName="ftc_elements" rows={c.created_elements} columns={[{ key: 'unique_element_id', label: 'Unique Element ID' }, { key: 'name', label: 'Element' }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> }, { key: 'realtime_enabled', label: 'Real-time enabled', render: (r) => <Badge color={r.realtime_enabled ? 'green' : 'slate'}>{r.realtime_enabled ? 'YES' : 'after Format IV'}</Badge> }]} />
          <p className="mt-2 text-xs text-slate-600">Charging date/time from real-time module: <b>{fmtDT(c.realtime_charging_time) || 'not yet charged'}</b></p>
        </Card>
      )}
      {tab === 'post' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Post-commissioning compliances"><SpreadsheetGrid exportName="compliances" compact rows={c.compliances} columns={[{ key: 'compliance_type', label: 'Type' }, { key: 'due_date', label: 'Due' }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> }, { key: 'timeline', label: 'Timeline', render: (r) => <Badge color={r.timeline === 'OK' ? 'green' : r.timeline === 'EXPIRED' ? 'red' : 'amber'}>{r.timeline}</Badge> }]} /></Card>
          <Card title="Real-time issues log (chronological)">
            <ul className="mb-2 max-h-56 space-y-1 overflow-y-auto text-xs">{c.issues.map((i: any, n: number) => <li key={n} className={cls('rounded p-1.5', i.direction === 'TO_REGS' ? 'bg-grid-50' : 'bg-amber-50')}><b>{i.by}</b> · {fmtDT(i.at)}<div>{i.message}</div></li>)}</ul>
            <div className="flex gap-1"><input aria-label="Issue message" className={inputCls} value={issue} onChange={(e) => setIssue(e.target.value)} /><Button onClick={() => run(async () => { await api.post(`/ftc/cases/${id}/issues`, { message: issue }); setIssue('') })}>Send</Button></div>
          </Card>
        </div>
      )}
    </div>
  )
}

export function FtcCompliancePage() {
  useRecentPages('Post-commissioning compliance')
  const { data, reload } = useAutoRefresh<any[]>('/ftc/compliance', undefined, { intervalMs: 10000 })
  const { user } = useAuth()
  const [sel, setSel] = useState<{ id: number; signer: string; file: File | null } | null>(null)
  const rows = data ?? []
  return (
    <div className="space-y-4">
      <PageHeader title="Post-commissioning compliance monitoring" subtitle="As-built model (3 months), final SLD, annual power quality, periodic tests - expiring soon / expired." />
      <div className="grid grid-cols-3 gap-3"><Stat label="Expired" value={rows.filter((r) => r.timeline === 'EXPIRED').length} tone="red" /><Stat label="Expiring ≤30 days" value={rows.filter((r) => r.timeline === 'EXPIRING_SOON').length} tone="amber" /><Stat label="Accepted" value={rows.filter((r) => r.status === 'ACCEPTED').length} tone="green" /></div>
      <SpreadsheetGrid exportName="post_comm_compliance" rows={rows} rowClassName={(r) => (r.timeline === 'EXPIRED' ? 'bg-red-50' : r.timeline === 'EXPIRING_SOON' ? 'bg-amber-50' : '')} columns={[
        { key: 'case_number', label: 'FTC case' }, { key: 'entity', label: 'REGS' }, { key: 'description', label: 'Compliance' }, { key: 'due_date', label: 'Due' },
        { key: 'days_left', label: 'Days left' }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> }, { key: 'signed_by', label: 'Signed by' },
        { key: 'x', label: 'Action', render: (r) => user?.is_external ? <Button size="sm" variant="secondary" onClick={() => setSel({ id: r.id, signer: '', file: null })}>Submit</Button>
          : r.status === 'SUBMITTED' ? <div className="flex gap-1">{[true, false].map((a) => <Button key={String(a)} size="sm" variant={a ? 'success' : 'danger'} onClick={() => { const fd = new FormData(); fd.append('approve', String(a)); api.post(`/ftc/compliance/${r.id}/decide`, fd).then(reload) }}>{a ? 'Accept' : 'Reject'}</Button>)}</div> : null },
      ]} />
      {sel && <Card title="Submit compliance document">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Undertaking signed by"><input className={inputCls} value={sel.signer} onChange={(e) => setSel({ ...sel, signer: e.target.value })} /></Field>
          <input type="file" aria-label="Compliance file" onChange={(e) => setSel({ ...sel, file: e.target.files?.[0] ?? null })} />
          <Button disabled={!sel.file || !sel.signer} onClick={async () => { const fd = new FormData(); fd.append('signed_by', sel.signer); fd.append('file', sel.file!); await api.post(`/ftc/compliance/${sel.id}/submit`, fd); setSel(null); reload() }}>Upload</Button>
        </div>
      </Card>}
    </div>
  )
}

export function StartupPowerPage() {
  useRecentPages('Start-up power')
  const { data, reload } = useAutoRefresh<any[]>('/ftc/startup-power', undefined, { intervalMs: 10000 })
  const { user } = useAuth()
  const [f, setF] = useState({ unit_details: '', quantum_mw: '', period_from: '', period_to: '' })
  const [err, setErr] = useState('')
  return (
    <div className="space-y-4">
      <PageHeader title="Grant of start-up power (Procedure for drawal of start-up power, 2014)" subtitle="Application → department consents → RLDC grant (copy to RPC) → weekly/monthly updates." />
      {err && <Alert kind="error">{err}</Alert>}
      {user?.is_external && <Card title="Apply">
        <div className="grid gap-2 md:grid-cols-5">
          <input aria-label="Unit details" placeholder="Unit details (size, MCR, auxiliaries)" className={inputCls} value={f.unit_details} onChange={(e) => setF({ ...f, unit_details: e.target.value })} />
          <input aria-label="Quantum MW" placeholder="Quantum MW" className={inputCls} value={f.quantum_mw} onChange={(e) => setF({ ...f, quantum_mw: e.target.value })} />
          <input aria-label="From" type="date" className={inputCls} value={f.period_from} onChange={(e) => setF({ ...f, period_from: e.target.value })} />
          <input aria-label="To" type="date" className={inputCls} value={f.period_to} onChange={(e) => setF({ ...f, period_to: e.target.value })} />
          <Button onClick={async () => { try { await api.post('/ftc/startup-power', { ...f, quantum_mw: Number(f.quantum_mw) }); reload() } catch (e) { setErr(errMsg(e)) } }}>Apply</Button>
        </div>
      </Card>}
      <SpreadsheetGrid exportName="startup_power" rows={data ?? []} columns={[{ key: 'case_number', label: 'Case' }, { key: 'entity', label: 'Generating station' }, { key: 'quantum_mw', label: 'Requested MW' }, { key: 'period_from', label: 'From' }, { key: 'period_to', label: 'To' },
        { key: 'grant_status', label: 'Status', render: (r) => <Badge>{r.grant_status}</Badge> }, { key: 'granted_quantum_mw', label: 'Granted MW' },
        { key: 'updates', label: 'Weekly updates', render: (r) => r.weekly_updates.length },
        { key: 'x', label: 'Action', render: (r) => !user?.is_external && r.grant_status === 'APPLIED' ? <Button size="sm" variant="success" onClick={() => api.post(`/ftc/startup-power/${r.id}/grant`, { approve: true }).then(reload)}>Grant</Button>
          : user?.is_external && r.grant_status === 'GRANTED' ? <Button size="sm" variant="secondary" onClick={() => { const q = prompt('Quantum to be availed this week (MW)'); if (q) api.post(`/ftc/startup-power/${r.id}/update`, { kind: 'WEEKLY', quantum_mw: Number(q) }).then(reload) }}>Weekly update</Button> : null }]} />
    </div>
  )
}

export function FtcReportsPage() {
  useRecentPages('FTC reports')
  const [kind, setKind] = useState('ftc')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const { data } = useAutoRefresh<any>(`/ftc/reports/${kind}`, { from_date: from || undefined, to_date: to || undefined }, { live: false })
  return (
    <div className="space-y-3">
      <PageHeader title="FTC reports" subtitle="FTC elements, COD elements and departmental comments with date and element-type filters." />
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Report"><select className={inputCls} value={kind} onChange={(e) => setKind(e.target.value)}><option value="ftc">First-time charged elements</option><option value="cod">COD elements</option><option value="comments">Comments report</option></select></Field>
        <Field label="From"><input type="date" className={inputCls} value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label="To"><input type="date" className={inputCls} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
        {['xlsx', 'pdf'].map((f) => <Button key={f} variant="secondary" onClick={() => download(`/ftc/reports/${kind}`, `ftc_${kind}.${f}`, { fmt: f, from_date: from || undefined, to_date: to || undefined })}>{f.toUpperCase()}</Button>)}
      </div>
      {data && <SpreadsheetGrid exportName={`ftc_${kind}`} rows={data.rows} columns={data.columns.map((c: any) => ({ key: c[0], label: c[1], exportValue: (r: any) => (c[0] === 'at' ? fmtDT(r.at) : r[c[0]]) }))} />}
    </div>
  )
}
