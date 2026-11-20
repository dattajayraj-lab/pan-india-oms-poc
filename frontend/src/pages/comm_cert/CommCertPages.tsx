// Communication System Certification screens (TS Cl. 11.4.3; FRD CC-*).
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, errMsg } from '../../api/client'
import { fmtDT, useAutoRefresh, useRecentPages } from '../../store/hooks'
import SpreadsheetGrid from '../../components/common/SpreadsheetGrid'
import CaseFlowchartTracker from '../../components/workflow/CaseFlowchartTracker'
import { CaseHeaderInfo, ConsentPanel, DocumentPanel } from '../../components/workflow/WorkflowPanels'
import { Alert, Badge, Button, Card, Field, LastUpdated, PageHeader, cls, inputCls } from '../../components/common/ui'

export function CommListPage() {
  useRecentPages('Communication certification')
  const { data, updatedAt } = useAutoRefresh<any[]>('/comm-cert/cases')
  return (
    <div>
      <PageHeader title="Communication System Certification" subtitle="OPGW, FOTE, auxiliary power, State CSP: CA-annexures → Stage-1 certificate → CB-annexures → Format III." actions={<><LastUpdated at={updatedAt} /><Link to="/comm-cert/new"><Button>+ New application</Button></Link></>} />
      <SpreadsheetGrid exportName="comm_cert" rows={data ?? []} columns={[
        { key: 'case_number', label: 'Case ID', render: (r) => <Link className="font-medium text-grid-700 hover:underline" to={`/comm-cert/${r.app_id}`}>{r.case_number}</Link>, exportValue: (r) => r.case_number },
        { key: 'element', label: 'Element' }, { key: 'comm_type', label: 'Type' }, { key: 'scope', label: 'Scope' }, { key: 'entity', label: 'Licensee' },
        { key: 'stage', label: 'Stage' }, { key: 'stage_status', label: 'Stage status', render: (r) => <Badge>{r.stage_status}</Badge> },
        { key: 'pending_with_role', label: 'Pending with' }, { key: 'created_at', label: 'Created', exportValue: (r) => fmtDT(r.created_at) }]} />
    </div>
  )
}

export function CommNewPage() {
  const nav = useNavigate()
  const [els, setEls] = useState<any[]>([])
  const [f, setF] = useState({ comm_element_id: '', scope: 'INTRA_REGIONAL', anticipated_sat_date: '' })
  const [err, setErr] = useState('')
  useEffect(() => { api.get('/master/comm-elements').then((r) => setEls(r.data)) }, [])
  return (
    <div className="max-w-xl space-y-3">
      <PageHeader title="Intimation of anticipated commissioning" subtitle="Not less than 7 days before anticipated SAT / integration." />
      {err && <Alert kind="error">{err}</Alert>}
      <Card><div className="space-y-3">
        <Field label="Communication element"><select className={inputCls} value={f.comm_element_id} onChange={(e) => setF({ ...f, comm_element_id: e.target.value })}><option value="">—</option>{els.map((e) => <option key={e.id} value={e.id}>{e.unique_comm_id} · {e.name}</option>)}</select></Field>
        <Field label="Scope"><select className={inputCls} value={f.scope} onChange={(e) => setF({ ...f, scope: e.target.value })}><option value="INTRA_REGIONAL">Inter-state / intra-regional</option><option value="INTER_REGIONAL">Inter-regional</option><option value="TRANS_NATIONAL">Trans-national</option></select></Field>
        <Field label="Anticipated SAT / integration date"><input type="date" className={inputCls} value={f.anticipated_sat_date} onChange={(e) => setF({ ...f, anticipated_sat_date: e.target.value })} /></Field>
        <Button onClick={async () => { try { const { data } = await api.post('/comm-cert/cases', { ...f, comm_element_id: Number(f.comm_element_id) }); nav(`/comm-cert/${data.app_id}`) } catch (e) { setErr(errMsg(e)) } }}>Create</Button>
      </div></Card>
    </div>
  )
}

export function CommDetailPage() {
  const { id } = useParams()
  useRecentPages(`Comm cert #${id}`)
  const { data: c, reload, updatedAt } = useAutoRefresh<any>(`/comm-cert/cases/${id}`, undefined, { intervalMs: 5000 })
  const [err, setErr] = useState('')
  const [route, setRoute] = useState('C')
  const [other, setOther] = useState('WRLDC')
  const [tp, setTp] = useState<string>('')
  const [ents, setEnts] = useState<any[]>([])
  const [sat, setSat] = useState('')
  useEffect(() => { api.get('/master/entities').then((r) => setEnts(r.data)).catch(() => undefined) }, [])
  if (!c) return null
  const run = async (fn: () => Promise<any>) => { try { await fn(); setErr(''); reload() } catch (e) { setErr(errMsg(e)) } }
  const st = c.stages.find((s: any) => s.no === c.stage)
  return (
    <div className="space-y-4">
      <PageHeader title={<>{c.case_number} <Badge>{c.status}</Badge> <Badge color="purple">Stage {c.stage}</Badge></>} subtitle={`${c.unique_comm_id} · ${c.element} · ${c.scope} · element ${c.element_status}`} actions={<LastUpdated at={updatedAt} />} />
      {err && <Alert kind="error">{err}</Alert>}
      <Card title="Tracking"><CaseHeaderInfo c={c} /><div className="mt-3"><CaseFlowchartTracker steps={c.tracker} /></div></Card>
      <DocumentPanel docs={c.documents} uploadUrl={`/comm-cert/cases/${id}/documents`} categories={st.annexures.map((a: any) => a.code)} labels={Object.fromEntries(st.annexures.map((a: any) => [a.code, a.label]))}
        required={st.annexures.filter((a: any) => a.required).map((a: any) => a.code)} onChange={reload} canUpload={!c.is_locked} title={`${st.name} documents`} />
      <Card title="Third-party / inter-regional consents">
        <div className="mb-2 flex flex-wrap gap-2">{c.third_party_consents.map((t: any) => <span key={t.entity_id} className="text-xs">{t.name} <Badge>{t.status}</Badge> {t.remarks}</span>)}{!c.third_party_consents.length && <span className="text-xs text-slate-500">None requested</span>}</div>
        {c.is_coordinator && <div className="flex gap-2"><select aria-label="Third party" className={cls(inputCls, 'w-72')} value={tp} onChange={(e) => setTp(e.target.value)}><option value="">Select entity…</option>{ents.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select><Button size="sm" disabled={!tp} onClick={() => run(() => api.post(`/comm-cert/cases/${id}/third-party`, { entity_ids: [Number(tp)] }))}>Request consent</Button></div>}
        {c.my_third_party?.status === 'PENDING' && <div className="flex gap-2">{[true, false].map((a) => <Button key={String(a)} size="sm" variant={a ? 'success' : 'danger'} onClick={() => run(() => { const fd = new FormData(); fd.append('approve', String(a)); return api.post(`/comm-cert/cases/${id}/third-party/respond`, fd) })}>{a ? 'Give consent' : 'Refuse'}</Button>)}</div>}
      </Card>
      <Card title="Actions">
        <div className="flex flex-wrap items-end gap-2">
          {!c.is_locked && !c.is_coordinator && <>{c.stage === 2 && <Field label="SAT completed on"><input type="date" className={inputCls} value={sat} onChange={(e) => setSat(e.target.value)} /></Field>}<Button onClick={() => run(() => { const fd = new FormData(); if (sat) fd.append('sat_completed_date', sat); return api.post(`/comm-cert/cases/${id}/submit`, fd) })}>Submit {st.name.split(' - ')[0]}</Button></>}
          {c.is_coordinator && <>
            {c.stage === 1 && !c.acknowledged_on && c.status === 'SUBMITTED' && <Button onClick={() => run(() => api.post(`/comm-cert/cases/${id}/coordinator`, { action: 'ACKNOWLEDGE' }))}>Acknowledge (Format II)</Button>}
            <Field label="Consent route"><select className={inputCls} value={route} onChange={(e) => setRoute(e.target.value)}><option value="C">C: own SCADA</option><option value="A">A: + other RLDC SCADA</option><option value="B">B: + other RLDC + NLDC SCADA</option></select></Field>
            {route !== 'C' && <Field label="Other RLDC"><select className={inputCls} value={other} onChange={(e) => setOther(e.target.value)}>{['NRLDC', 'ERLDC', 'WRLDC', 'SRLDC', 'NERLDC'].map((x) => <option key={x}>{x}</option>)}</select></Field>}
            <Button onClick={() => run(() => api.post(`/comm-cert/cases/${id}/coordinator`, { action: 'FORWARD', route, other_centre: other }))}>Forward</Button>
            <Button variant="warning" onClick={() => run(() => api.post(`/comm-cert/cases/${id}/coordinator`, { action: 'RETURN', remarks: 'Please correct annexures' }))}>Return</Button>
            <Button variant="success" onClick={() => run(() => api.post(`/comm-cert/cases/${id}/coordinator`, { action: 'ACCEPT' }))}>Accept & prepare certificate</Button>
          </>}
          {(c.can_sign_stage1 || c.can_sign_stage2) && <Button variant="success" onClick={() => run(() => api.post(`/comm-cert/cases/${id}/sign`))}>Digitally sign certificate</Button>}
        </div>
      </Card>
      <ConsentPanel consents={c.consents} actUrl={(cid) => `/comm-cert/cases/${id}/consents/${cid}`} onChange={reload} title="SCADA / Head consents (sequential)" />
    </div>
  )
}
