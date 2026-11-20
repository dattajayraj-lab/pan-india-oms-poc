// Outage Coordination, Availability, Protection, Message Alerts and SPS screens (TS Cl. 11.4.5-11.4.9; FRD OC-*, AV-*, PT-*, MA-*, SPS-*).
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, download, errMsg } from '../../api/client'
import { useAuth } from '../../store/auth'
import { fmtDT, useAutoRefresh, useRecentPages } from '../../store/hooks'
import SpreadsheetGrid from '../../components/common/SpreadsheetGrid'
import DynamicChart, { objToSeries } from '../../components/charts/DynamicChart'
import { Alert, Badge, Button, Card, Field, LastUpdated, Modal, PageHeader, Stat, Tabs, cls, inputCls } from '../../components/common/ui'

const toIso = (v: string) => (v ? new Date(v).toISOString() : undefined)
const centreOf = (a: string, u: any) => (a !== 'ALL' ? a : u?.centre?.code === 'NLDC' ? 'NRLDC' : u?.centre?.code ?? 'NRLDC')

// ------------------------------------------------------------------ Outage coordination
export function OutagePlansPage() {
  useRecentPages('Shutdown requests')
  const { user, activeCentre, hasRole } = useAuth()
  const [tab, setTab] = useState('')
  const { data, reload, updatedAt } = useAutoRefresh<any[]>('/outage/plans', { route: tab || undefined }, { intervalMs: 5000 })
  const [sel, setSel] = useState<number[]>([])
  const [err, setErr] = useState('')
  const run = async (fn: () => Promise<any>) => { try { await fn(); setErr(''); setSel([]); reload() } catch (e) { setErr(errMsg(e)) } }
  const rpc = hasRole('RPC')
  const coord = hasRole('OUTAGE_COORDINATOR')
  return (
    <div className="space-y-3">
      <PageHeader title="Outage Coordination" subtitle="OCC/RPC (M+2, 26th–5th), D-3, D-2, emergency and non-auto (Req. for AR) shutdowns; inter-regional via NLDC; D-1 approval feeds the control room."
        actions={<><LastUpdated at={updatedAt} /><Link to="/outage/new"><Button>+ New request</Button></Link><Button variant="secondary" onClick={() => download('/outage/utility-sheets', 'utility_sheets.xlsx', { fmt: 'xlsx', centre: centreOf(activeCentre, user) })}>Utility-wise sheets</Button></>} />
      {err && <Alert kind="error">{err}</Alert>}
      <Tabs active={tab} onChange={setTab} tabs={[{ key: '', label: 'All' }, { key: 'OCC_M2', label: 'OCC (M+2)' }, { key: 'D3', label: 'D-3' }, { key: 'D2', label: 'D-2' }, { key: 'NON_AUTO', label: 'Non-auto (AR)' }]} />
      {(rpc || coord) && sel.length > 0 && (
        <div className="flex flex-wrap gap-1 rounded bg-grid-50 p-2 text-xs">{sel.length} selected:
          {rpc && <>{['ENABLE_LATE', 'FORWARD', 'OCC_APPROVE', 'OCC_REJECT'].map((a) => <Button key={a} size="sm" variant={a === 'OCC_REJECT' ? 'danger' : 'secondary'} onClick={() => run(() => api.post('/outage/rpc', { plan_ids: sel, action: a, remarks: a === 'OCC_APPROVE' ? 'Approved in OCC' : '' }))}>{a.replace('_', ' ')}</Button>)}</>}
        </div>
      )}
      <SpreadsheetGrid exportName="shutdown_requests" rows={data ?? []} columns={[
        { key: 's', label: '', render: (r) => <input type="checkbox" aria-label={`select ${r.reference_number}`} checked={sel.includes(r.id)} onChange={(e) => setSel(e.target.checked ? [...sel, r.id] : sel.filter((x) => x !== r.id))} /> },
        { key: 'reference_number', label: 'Ref' }, { key: 'occ_number', label: 'OCC' }, { key: 'plan_route', label: 'Route' }, { key: 'element', label: 'Element' }, { key: 'owner', label: 'Owner' },
        { key: 'req_from', label: 'From', exportValue: (r) => fmtDT(r.req_from), render: (r) => fmtDT(r.req_from) }, { key: 'req_to', label: 'To', exportValue: (r) => fmtDT(r.req_to), render: (r) => fmtDT(r.req_to) },
        { key: 'daily_or_continuous', label: 'D/C' }, { key: 'reason', label: 'Reason' }, { key: 'availability_head_proposed', label: 'Avail. head' },
        { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> }, { key: 'nldc_status', label: 'NLDC', render: (r) => r.nldc_status !== 'NA' ? <Badge>{r.nldc_status}</Badge> : '' },
        { key: 'x', label: '', render: (r) => <div className="flex gap-1">
          {coord && <Button size="sm" variant="secondary" onClick={() => run(() => api.post(`/outage/plans/${r.id}/rldc-review`, { rldc_comments: 'Reviewed', availability_head_rldc: r.availability_head_proposed, category_code: 'C01' }))}>RLDC review</Button>}
          {hasRole('NLDC_USER') && r.nldc_status === 'PENDING' && <Button size="sm" onClick={() => run(() => { const fd = new FormData(); fd.append('approve', 'true'); return api.post(`/outage/plans/${r.id}/nldc`, fd) })}>NLDC approve</Button>}
          {user?.is_external && r.status === 'OCC_APPROVED' && <Button size="sm" onClick={() => run(() => api.post(`/outage/plans/${r.id}/apply-d3`))}>Apply D-3</Button>}
        </div> },
      ]} />
    </div>
  )
}

export function NewOutagePage() {
  useRecentPages('New shutdown request')
  const { user, activeCentre } = useAuth()
  const [els, setEls] = useState<any[]>([])
  const [f, setF] = useState<any>({ grid_element_id: '', req_from: '', req_to: '', daily_or_continuous: 'CONTINUOUS', request_type: 'MAINTENANCE', reason: '', requester_remarks: '', availability_comments: '', availability_head_proposed: 'SELF', non_auto_ar: false })
  const [route, setRoute] = useState<any>(null)
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  useEffect(() => { api.get('/master/elements', { params: { centre: user?.is_external ? undefined : centreOf(activeCentre, user) } }).then((r) => setEls(r.data)) }, [user, activeCentre])
  useEffect(() => { if (f.grid_element_id) api.get('/outage/route-preview', { params: { grid_element_id: f.grid_element_id } }).then((r) => setRoute(r.data)) }, [f.grid_element_id])
  return (
    <div className="max-w-3xl space-y-3">
      <PageHeader title="New shutdown request" subtitle="Route (OCC / D-3 / D-2) is determined from ownership and voltage (TS Table 12)." />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <Card><div className="grid gap-3 md:grid-cols-2">
        <Field label="Element"><select className={inputCls} value={f.grid_element_id} onChange={(e) => setF({ ...f, grid_element_id: e.target.value })}><option value="">—</option>{els.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></Field>
        <div className="text-xs">{route && <>Route: <Badge color="purple">{route.route}</Badge> {route.route === 'OCC_M2' && <>Target month {route.target_month} · window {route.occ_window_open ? <Badge color="green">open</Badge> : <Badge color="red">closed - RPC must enable</Badge>}</>} {route.via_nldc && <Badge color="blue">via NLDC</Badge>}</>}</div>
        <Field label="From"><input type="datetime-local" className={inputCls} value={f.req_from} onChange={(e) => setF({ ...f, req_from: e.target.value })} /></Field>
        <Field label="To"><input type="datetime-local" className={inputCls} value={f.req_to} onChange={(e) => setF({ ...f, req_to: e.target.value })} /></Field>
        <Field label="Daily / continuous"><select className={inputCls} value={f.daily_or_continuous} onChange={(e) => setF({ ...f, daily_or_continuous: e.target.value })}><option>CONTINUOUS</option><option>DAILY</option></select></Field>
        <Field label="Request type"><select className={inputCls} value={f.request_type} onChange={(e) => setF({ ...f, request_type: e.target.value })}>{['MAINTENANCE', 'CONSTRUCTION', 'DIVERSION', 'OPGW', 'TESTING'].map((x) => <option key={x}>{x}</option>)}</select></Field>
        <Field label="Reason" required><input className={inputCls} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field>
        <Field label="Availability head (proposed)"><select className={inputCls} value={f.availability_head_proposed} onChange={(e) => setF({ ...f, availability_head_proposed: e.target.value })}>{['SELF', 'OTHERS', 'SYSTEM', 'CONSTRUCTION', 'DIVERSION', 'HVDC_SELF', 'HVDC_OTHERS', 'KITE', 'WEATHER'].map((x) => <option key={x}>{x}</option>)}</select></Field>
        <Field label="Requester comments for availability"><input className={inputCls} value={f.availability_comments} onChange={(e) => setF({ ...f, availability_comments: e.target.value })} /></Field>
        <Field label="Remarks"><input className={inputCls} value={f.requester_remarks} onChange={(e) => setF({ ...f, requester_remarks: e.target.value })} /></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.non_auto_ar} onChange={(e) => setF({ ...f, non_auto_ar: e.target.checked })} /> Non-auto mode (Req. for AR) – excluded from availability</label>
      </div>
      <Button className="mt-3" onClick={async () => { try { const { data } = await api.post('/outage/plans', { ...f, grid_element_id: Number(f.grid_element_id), req_from: toIso(f.req_from), req_to: toIso(f.req_to) }); setMsg({ kind: 'success', text: `${data.reference_number} submitted (${data.plan_route}, ${data.status})` }) } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) } }}>Submit</Button></Card>
    </div>
  )
}

export function D1Page() {
  useRecentPages('D-1 approval')
  const { data, reload } = useAutoRefresh<any[]>('/outage/plans', undefined, { intervalMs: 5000 })
  const [sel, setSel] = useState<any>(null)
  const [c, setC] = useState({ comment_coordinator: '', comment_hod: '', comment_head: '' })
  const [file, setFile] = useState<File | null>(null)
  const [err, setErr] = useState('')
  const rows = (data ?? []).filter((p) => ['D3_APPLIED', 'OCC_APPROVED', 'RLDC_REVIEW', 'SUBMITTED'].includes(p.status))
  const decide = async (approve: boolean) => {
    const fd = new FormData(); fd.append('approve', String(approve)); Object.entries(c).forEach(([k, v]) => fd.append(k, v)); if (file) fd.append('study_file', file)
    try { await api.post(`/outage/plans/${sel.id}/d1`, fd); setSel(null); reload() } catch (e) { setErr(errMsg(e)) }
  }
  return (
    <div className="space-y-3">
      <PageHeader title="D-1 approval" subtitle="Final decision with PSS/E study (outside OMS), weather check and comments; approved shutdowns flow to the control room." actions={<Button variant="secondary" onClick={() => download('/outage/d1-list', 'd1_list.pdf', { fmt: 'pdf' })}>D-1 list (PDF)</Button>} />
      <SpreadsheetGrid exportName="d1_pending" rows={rows} columns={[{ key: 'reference_number', label: 'Ref' }, { key: 'element', label: 'Element' }, { key: 'req_from', label: 'From', exportValue: (r) => fmtDT(r.req_from), render: (r) => fmtDT(r.req_from) }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> },
        { key: 'w', label: 'Weather', render: (r) => r.weather_alerts.length ? <span className="text-xs text-amber-700">⚠ {r.weather_alerts[0]}</span> : <span className="text-xs text-emerald-700">Clear</span> },
        { key: 'x', label: '', render: (r) => <Button size="sm" onClick={() => { setSel(r); setErr('') }}>Decide</Button> }]} />
      <Modal open={!!sel} onClose={() => setSel(null)} title={`D-1 decision: ${sel?.reference_number}`}>
        {sel && <div className="space-y-2">
          {err && <Alert kind="error">{err}</Alert>}
          <div className="text-sm">{sel.element} · {fmtDT(sel.req_from)} → {fmtDT(sel.req_to)} · {sel.reason}</div>
          {(['comment_coordinator', 'comment_hod', 'comment_head'] as const).map((k, i) => <Field key={k} label={['Comment 1 (Outage Coordinator)', 'Comment 2 (HoD/Sub-Head SO)', 'Comment 3 (Head of RLDC)'][i]}><input className={inputCls} value={c[k]} onChange={(e) => setC({ ...c, [k]: e.target.value })} /></Field>)}
          <Field label="Study file (PDF/JPEG)"><input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <div className="flex gap-2"><Button variant="success" onClick={() => decide(true)}>Approve</Button><Button variant="danger" onClick={() => decide(false)}>Reject</Button></div>
        </div>}
      </Modal>
    </div>
  )
}

// ------------------------------------------------------------------ Availability
export function AvailabilitySheetPage() {
  useRecentPages('Availability review sheet')
  const { user } = useAuth()
  const now = new Date()
  const [month, setMonth] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
  const { data, reload } = useAutoRefresh<any>('/availability/sheet', { month }, { intervalMs: 10000 })
  const [tab, setTab] = useState('')
  const [obj, setObj] = useState<any>(null)
  const [err, setErr] = useState('')
  const tabs = Object.keys(data?.tabs ?? {})
  const cur = tab || tabs[0]
  const act = async (id: number, body: any) => { try { await api.post(`/availability/records/${id}/action`, body); setErr(''); setObj(null); reload() } catch (e) { setErr(errMsg(e)) } }
  return (
    <div className="space-y-3">
      <PageHeader title="Monthly outage review sheet (availability)" subtitle={data ? `Generated ${data.generated_on} · Accept/Object by ${data.objection_deadline} · published ${data.publish_on}` : ''}
        actions={<><input aria-label="Month" type="month" className={inputCls} value={month} onChange={(e) => setMonth(e.target.value)} /><Button variant="secondary" onClick={() => download('/availability/sheet/export', `availability_${month}.xlsx`, { month })}>Excel</Button></>} />
      {err && <Alert kind="error">{err}</Alert>}
      <Tabs active={cur ?? ''} onChange={setTab} tabs={tabs.map((t) => ({ key: t, label: t, count: data.tabs[t].length }))} />
      {cur && <SpreadsheetGrid exportName={`availability_${cur}`} rows={data.tabs[cur]} rowClassName={(r) => (r.is_locked ? 'bg-emerald-50' : r.user_action === 'OBJECTED' ? 'bg-amber-50' : '')} columns={[
        { key: 'element_uid', label: 'Element ID' }, { key: 'element', label: 'Element' }, { key: 'owner', label: 'Owner' },
        { key: 'outage_start', label: 'Outage', exportValue: (r) => fmtDT(r.outage_start), render: (r) => fmtDT(r.outage_start) }, { key: 'outage_end', label: 'Charging', exportValue: (r) => fmtDT(r.outage_end), render: (r) => fmtDT(r.outage_end) },
        { key: 'hours', label: 'Hours' }, { key: 'availability_head', label: 'Head' }, { key: 'category_code', label: 'Cat.' },
        { key: 'user_action', label: 'Licensee', render: (r) => <Badge>{r.user_action}</Badge> }, { key: 'rldc_verified_status', label: 'RLDC' }, { key: 'rpc_status', label: 'RPC' },
        { key: 'x', label: '', render: (r) => user?.is_external && !r.is_locked ? <div className="flex gap-1"><Button size="sm" variant="success" onClick={() => act(r.id, { action: 'ACCEPT' })}>Accept</Button><Button size="sm" variant="warning" onClick={() => setObj({ id: r.id, modified_outage_time: '', modified_charging_time: '', modified_head: r.availability_head, comments: '' })}>Object</Button></div> : r.is_locked ? '🔒' : null },
      ]} />}
      <Modal open={!!obj} onClose={() => setObj(null)} title="Object – propose modifications">
        {obj && <div className="space-y-2">
          <Field label="Modified outage time"><input type="datetime-local" className={inputCls} value={obj.modified_outage_time} onChange={(e) => setObj({ ...obj, modified_outage_time: e.target.value })} /></Field>
          <Field label="Modified charging time"><input type="datetime-local" className={inputCls} value={obj.modified_charging_time} onChange={(e) => setObj({ ...obj, modified_charging_time: e.target.value })} /></Field>
          <Field label="Modified availability head"><input className={inputCls} value={obj.modified_head} onChange={(e) => setObj({ ...obj, modified_head: e.target.value })} /></Field>
          <Field label="Comments"><input className={inputCls} value={obj.comments} onChange={(e) => setObj({ ...obj, comments: e.target.value })} /></Field>
          <Button onClick={() => act(obj.id, { action: 'OBJECT', modified_outage_time: toIso(obj.modified_outage_time), modified_charging_time: toIso(obj.modified_charging_time), modified_head: obj.modified_head, comments: obj.comments })}>Submit objection</Button>
        </div>}
      </Modal>
    </div>
  )
}

export function AvailabilityVerifyPage() {
  useRecentPages('Availability verification')
  const now = new Date()
  const [month, setMonth] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
  const { data, reload } = useAutoRefresh<any>('/availability/sheet', { month }, { intervalMs: 10000 })
  const { data: meta } = useAutoRefresh<any>('/availability/meta', undefined, { live: false })
  const [sel, setSel] = useState<number[]>([])
  const [bif, setBif] = useState<any>(null)
  const [err, setErr] = useState('')
  const rows = Object.values(data?.tabs ?? {}).flat() as any[]
  const run = async (fn: () => Promise<any>) => { try { await fn(); setErr(''); setSel([]); reload() } catch (e) { setErr(errMsg(e)) } }
  return (
    <div className="space-y-3">
      <PageHeader title="Availability coordinator verification" subtitle="Stakeholder comments → Protection verification → verify (not approve) → forward to RPC; outage bifurcation." actions={<input aria-label="Month" type="month" className={inputCls} value={month} onChange={(e) => setMonth(e.target.value)} />} />
      {err && <Alert kind="error">{err}</Alert>}
      <div className="flex flex-wrap gap-1">{['SEND_TO_PROTECTION', 'VERIFY', 'NOT_VERIFY', 'FORWARD_RPC'].map((a) => <Button key={a} size="sm" variant="secondary" disabled={!sel.length} onClick={() => run(() => api.post('/availability/coordinator', { record_ids: sel, action: a, comment: '' }))}>{a.replace(/_/g, ' ')}</Button>)}</div>
      <SpreadsheetGrid exportName="availability_verify" rows={rows} columns={[
        { key: 's', label: '', render: (r) => <input type="checkbox" aria-label="select" checked={sel.includes(r.id)} onChange={(e) => setSel(e.target.checked ? [...sel, r.id] : sel.filter((x) => x !== r.id))} /> },
        { key: 'element', label: 'Element' }, { key: 'owner', label: 'Owner' }, { key: 'hours', label: 'Hours' }, { key: 'availability_head', label: 'Head' }, { key: 'user_action', label: 'Licensee', render: (r) => <Badge>{r.user_action}</Badge> },
        { key: 'proposed', label: 'Proposed', exportValue: (r) => JSON.stringify(r.proposed_changes), render: (r) => <span className="text-[11px]">{r.proposed_changes?.comments}</span> },
        { key: 'protection_remarks', label: 'Protection' }, { key: 'rldc_verified_status', label: 'Verified' }, { key: 'rpc_status', label: 'RPC' },
        { key: 'x', label: '', render: (r) => meta?.is_protection && r.sent_to_protection ? <Button size="sm" onClick={() => { const t = prompt('Protection dept. comments'); if (t) run(() => { const fd = new FormData(); fd.append('remarks', t); return api.post(`/availability/records/${r.id}/protection`, fd) }) }}>Protection remarks</Button>
          : <Button size="sm" variant="ghost" onClick={() => setBif({ r, segs: [{ start: r.outage_start, end: '', head: 'DEEMED', category_code: 'C14' }, { start: '', end: r.outage_end, head: 'SELF', category_code: '' }] })}>Bifurcate</Button> },
      ]} />
      <Modal open={!!bif} onClose={() => setBif(null)} title="Bifurcate outage into segments" wide>
        {bif && <div className="space-y-2 text-sm">
          <div>{bif.r.element}: {fmtDT(bif.r.outage_start)} → {fmtDT(bif.r.outage_end)}</div>
          <Field label="Split at (date/time)"><input type="datetime-local" className={inputCls} onChange={(e) => { const iso = toIso(e.target.value); setBif({ ...bif, segs: [{ ...bif.segs[0], end: iso }, { ...bif.segs[1], start: iso }] }) }} /></Field>
          {bif.segs.map((s: any, i: number) => <div key={i} className="flex gap-2"><span>Segment {i + 1}</span><select aria-label="Head" className={inputCls} value={s.head} onChange={(e) => setBif({ ...bif, segs: bif.segs.map((x: any, j: number) => (j === i ? { ...x, head: e.target.value } : x)) })}>{meta?.heads.map((h: string) => <option key={h}>{h}</option>)}</select>
            <select aria-label="Category" className={inputCls} value={s.category_code} onChange={(e) => setBif({ ...bif, segs: bif.segs.map((x: any, j: number) => (j === i ? { ...x, category_code: e.target.value } : x)) })}><option value="" />{meta?.category_codes.map((c: any) => <option key={c.code} value={c.code}>{c.code} {c.description}</option>)}</select></div>)}
          <Button onClick={() => run(async () => { const iso = (v: string) => (v.endsWith('Z') || v.includes('+') ? v : v + 'Z'); await api.post(`/availability/records/${bif.r.id}/bifurcate`, { segments: bif.segs.map((s: any) => ({ ...s, start: iso(s.start), end: iso(s.end) })) }); setBif(null) })}>Save bifurcation</Button>
        </div>}
      </Modal>
    </div>
  )
}

// ------------------------------------------------------------------ Protection
export function ProtectionEventsPage() {
  useRecentPages('Tripping events')
  const { data, reload, updatedAt } = useAutoRefresh<any[]>('/protection/events', undefined, { intervalMs: 10000 })
  const { data: meta } = useAutoRefresh<any>('/protection/meta', undefined, { live: false })
  const [cands, setCands] = useState<any[] | null>(null)
  const [pick, setPick] = useState<number[]>([])
  const [cat, setCat] = useState('GI-1')
  const counts = Object.entries((data ?? []).reduce((a: any, e) => ({ ...a, [e.category]: (a[e.category] ?? 0) + 1 }), {}))
  return (
    <div className="space-y-3">
      <PageHeader title="Protection & Tripping Studies" subtitle="Events from OMS outage records; FIR/DR/EL/TR from End-1 and End-2; flash (8 h), DR/EL (24 h), detailed (7 days)." actions={<><LastUpdated at={updatedAt} />{meta?.is_coordinator && <Button onClick={() => api.get('/protection/candidates').then((r) => setCands(r.data))}>+ Create event from trippings</Button>}</>} />
      <div className="grid gap-3 md:grid-cols-3">
        <Stat label="Events" value={data?.length ?? 0} /><Stat label="Pending files" value={(data ?? []).reduce((a, e) => a + e.pending_files, 0)} tone="amber" />
        <Card title="GD / GI distribution"><DynamicChart type="pie" height={140} data={counts.map(([k, v]) => ({ name: k, value: v }))} xKey="name" series={['value']} /></Card>
      </div>
      <SpreadsheetGrid exportName="tripping_events" rows={data ?? []} columns={[
        { key: 'event_code', label: 'Event', render: (r) => <Link className="text-grid-700 underline" to={`/protection/${r.id}`}>{r.event_code}</Link>, exportValue: (r) => r.event_code },
        { key: 'category', label: 'Category', render: (r) => <Badge color={r.category.startsWith('GD') ? 'red' : 'amber'}>{r.category}</Badge> }, { key: 'title', label: 'Elements' },
        { key: 'occurred_at', label: 'Occurred', exportValue: (r) => fmtDT(r.occurred_at), render: (r) => fmtDT(r.occurred_at) },
        { key: 'sub', label: 'FIR / DR / EL / TR', exportValue: (r) => JSON.stringify(r.submission), render: (r) => <span className="text-[11px]">{Object.entries(r.submission).map(([s, v]: any) => `${s}: ${['FIR', 'DR', 'EL', 'TR'].map((k) => (v[k] ? '✓' : '✗')).join('')}`).join(' · ')}</span> },
        { key: 'od', label: 'Overdue', render: (r) => Object.entries(r.overdue).filter(([, v]) => v).map(([k]) => <Badge key={k} color="red">{k}</Badge>) },
        { key: 'rldc_validation_status', label: 'Validation' }]} />
      <Modal open={!!cands} onClose={() => setCands(null)} title="Create event record" wide>
        <div className="space-y-2">
          {cands?.map((c) => <label key={c.id} className={cls('flex items-center gap-2 text-sm', c.used && 'text-slate-400')}><input type="checkbox" checked={pick.includes(c.id)} onChange={(e) => setPick(e.target.checked ? [...pick, c.id] : pick.filter((x) => x !== c.id))} />{c.element} · {fmtDT(c.tripped_at)} · {c.reason}{c.used && ' (already in an event)'}</label>)}
          <select aria-label="Category" className={inputCls} value={cat} onChange={(e) => setCat(e.target.value)}>{meta?.categories.map((x: string) => <option key={x}>{x}</option>)}</select>
          <Button disabled={!pick.length} onClick={() => api.post('/protection/events', { tripping_report_ids: pick, category: cat }).then(() => { setCands(null); setPick([]); reload() })}>Create event</Button>
        </div>
      </Modal>
    </div>
  )
}

export function ProtectionEventPage() {
  const { id } = useParams()
  useRecentPages(`Event #${id}`)
  const { data: ev, reload } = useAutoRefresh<any>(`/protection/events/${id}`, undefined, { intervalMs: 10000 })
  const [fir, setFir] = useState<Record<string, string>>({ cause: '', relay_indication: '', loss_of_load_mw: '', restoration: '', remedial_action: '' })
  const [end, setEnd] = useState('END1')
  const [kind, setKind] = useState('DR_MAIN1')
  const [file, setFile] = useState<File | null>(null)
  const [err, setErr] = useState('')
  if (!ev) return null
  const run = async (fn: () => Promise<any>) => { try { await fn(); setErr(''); reload() } catch (e) { setErr(errMsg(e)) } }
  const ends = ev.is_coordinator ? Object.keys(ev.submission) : ev.my_ends
  return (
    <div className="space-y-3">
      <PageHeader title={<>{ev.event_code} <Badge>{ev.category}</Badge></>} subtitle={ev.title} actions={<Button variant="secondary" onClick={() => download(`/protection/events/${id}/bulk-download`, `${ev.event_code}.zip`)}>Download all files (zip)</Button>} />
      {err && <Alert kind="error">{err}</Alert>}
      <div className="grid gap-3 md:grid-cols-3">
        <Stat label="Flash report due" value={fmtDT(ev.flash_due_at).slice(0, 16)} tone={ev.overdue.flash ? 'red' : 'grid'} />
        <Stat label="DR/EL due" value={fmtDT(ev.dr_el_due_at).slice(0, 16)} tone={ev.overdue.dr_el ? 'red' : 'grid'} />
        <Stat label="Detailed report due" value={fmtDT(ev.detailed_due_at).slice(0, 16)} tone={ev.overdue.detailed ? 'red' : 'grid'} />
      </div>
      <Card title="Your end">{ends.length ? <select aria-label="End" className={cls(inputCls, 'w-32')} value={end} onChange={(e) => setEnd(e.target.value)}>{ends.map((x: string) => <option key={x}>{x}</option>)}</select> : <span className="text-sm text-slate-500">View only</span>}</Card>
      {ends.length > 0 && <div className="grid gap-3 lg:grid-cols-2">
        <Card title={`FIR (${end}) – fillable, editable`} actions={<Button size="sm" onClick={() => run(() => api.put(`/protection/events/${id}/fir`, { end, data: fir }))}>Save FIR</Button>}>
          <div className="grid gap-2 md:grid-cols-2">{Object.entries(fir).map(([k, v]) => <Field key={k} label={k.replace(/_/g, ' ')}><input className={inputCls} value={v} onChange={(e) => setFir({ ...fir, [k]: e.target.value })} /></Field>)}</div>
          {ev.fir[end] && <p className="mt-1 text-[11px] text-slate-500">Last updated {ev.fir[end]._updated_at?.slice(0, 16)} by {ev.fir[end]._by}</p>}
        </Card>
        <Card title={`Upload DR / EL / TR / reports (${end})`}>
          <div className="flex flex-wrap gap-2"><select aria-label="Kind" className={inputCls} value={kind} onChange={(e) => setKind(e.target.value)}>{['DR_MAIN1', 'DR_MAIN2', 'DR_BACKUP', 'EL', 'TR', 'FLASH_REPORT', 'DETAILED_REPORT'].map((k) => <option key={k}>{k}</option>)}</select>
            <input type="file" aria-label="Protection file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <Button disabled={!file} onClick={() => run(() => { const fd = new FormData(); fd.append('kind', kind); fd.append('end', end); fd.append('file', file!); return api.post(`/protection/events/${id}/files`, fd) })}>Upload</Button></div>
          <p className="mt-1 text-[11px] text-slate-500">DR: .dat/.cfg/.pdf (Main-1 or Main-2 mandatory) · EL: pdf/image · TR: pdf. Users cannot replace DR/EL/TR once uploaded.</p>
        </Card>
      </div>}
      <Card title="Files">
        <SpreadsheetGrid exportName="protection_files" compact rows={ev.documents} columns={[{ key: 'end_side', label: 'End' }, { key: 'doc_category', label: 'Kind' }, { key: 'auto_filename', label: 'File' }, { key: 'uploader_name', label: 'By' }, { key: 'created_at', label: 'At', exportValue: (r) => fmtDT(r.created_at) },
          { key: 'x', label: '', render: (r) => ev.is_coordinator && !r.doc_category.startsWith('DELETED') ? <Button size="sm" variant="danger" onClick={() => { const t = prompt('Remarks for deletion'); if (t) run(() => api.delete(`/protection/events/${id}/files/${r.id}`, { params: { remarks: t } })) }}>Delete</Button> : null }]} />
      </Card>
      {ev.is_coordinator && <Card title="RLDC validation & corrective actions"><div className="flex gap-2"><Button variant="success" onClick={() => run(() => { const fd = new FormData(); fd.append('ok', 'true'); return api.post(`/protection/events/${id}/validate`, fd) })}>Validate</Button><Button variant="warning" onClick={() => run(() => { const fd = new FormData(); fd.append('ok', 'false'); fd.append('remarks', 'Reports incomplete'); return api.post(`/protection/events/${id}/validate`, fd) })}>Request re-upload</Button></div></Card>}
    </div>
  )
}

export function PscPage() {
  useRecentPages('PSC tracker')
  const { data, reload } = useAutoRefresh<any[]>('/protection/psc', undefined, { intervalMs: 10000 })
  const { hasRole } = useAuth()
  return (
    <div className="space-y-3">
      <PageHeader title="Protection Sub-Committee (PSC) tracker" subtitle="Agenda records from events, recommendations, utility action and compliance status." />
      <SpreadsheetGrid exportName="psc" rows={data ?? []} columns={[{ key: 'psc_record_code', label: 'PSC record' }, { key: 'event_code', label: 'Event' }, { key: 'category', label: 'GD/GI' }, { key: 'psc_meeting_no', label: 'Meeting' }, { key: 'recommendations', label: 'Recommendations' }, { key: 'utility_action_taken', label: 'Utility action' },
        { key: 'compliance_status', label: 'Status', render: (r) => hasRole('PROTECTION_COORDINATOR') ? <select aria-label="Compliance" className="rounded border text-xs" value={r.compliance_status} onChange={(e) => api.patch(`/protection/psc/${r.id}`, { compliance_status: e.target.value }).then(reload)}>{['COMPLIED', 'PARTIAL', 'NOT_COMPLIED'].map((x) => <option key={x}>{x}</option>)}</select> : <Badge>{r.compliance_status}</Badge> },
        { key: 'resolved_by_rldc', label: 'Resolved', render: (r) => (r.resolved_by_rldc ? 'Yes' : 'No') }]} />
    </div>
  )
}

export function SoprPage() {
  useRecentPages('SOPR')
  const now = new Date()
  const [month, setMonth] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
  const { data, reload } = useAutoRefresh<any[]>('/protection/sopr', { month }, { live: false })
  const { user } = useAuth()
  const [f, setF] = useState({ dependability: '1', security: '1', reliability: '1', comments: '' })
  const [msg, setMsg] = useState('')
  return (
    <div className="space-y-3">
      <PageHeader title="Monthly protection performance indices (SOPR)" subtitle="D, S, R indices (0–1) by utilities with non-zero trippings; reminder on the 10th." actions={<input aria-label="Month" type="month" className={inputCls} value={month} onChange={(e) => setMonth(e.target.value)} />} />
      {msg && <Alert kind="info">{msg}</Alert>}
      {user?.is_external && <Card title="Submit"><div className="flex flex-wrap gap-2">{(['dependability', 'security', 'reliability'] as const).map((k) => <Field key={k} label={k}><input className={inputCls} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></Field>)}<Field label="Comments"><input className={inputCls} value={f.comments} onChange={(e) => setF({ ...f, comments: e.target.value })} /></Field>
        <Button onClick={() => api.post('/protection/sopr', { month, dependability: Number(f.dependability), security: Number(f.security), reliability: Number(f.reliability), comments: f.comments }).then(() => { setMsg('Submitted'); reload() }).catch((e) => setMsg(errMsg(e)))}>Submit</Button></div></Card>}
      <SpreadsheetGrid exportName="sopr_status" rows={data ?? []} columns={[{ key: 'entity', label: 'Utility' }, { key: 'trippings', label: 'Trippings' }, { key: 'submitted', label: 'Submitted', render: (r) => <Badge color={r.submitted ? 'green' : 'red'}>{r.submitted ? 'YES' : 'NO'}</Badge> }, { key: 'D', label: 'D' }, { key: 'S', label: 'S' }, { key: 'R', label: 'R' }]} />
    </div>
  )
}

// ------------------------------------------------------------------ Message alerts
export function AlertsPage() {
  useRecentPages('Send alert')
  const { user, activeCentre } = useAuth()
  const [tpls, setTpls] = useState<any[]>([])
  const [tg, setTg] = useState<any>(null)
  const [code, setCode] = useState('FREQ_DEVIATION')
  const [targets, setTargets] = useState<string[]>([])
  const [payload, setPayload] = useState<Record<string, string>>({})
  const [res, setRes] = useState<any>(null)
  const [err, setErr] = useState('')
  const [flash, setFlash] = useState({ subject: '', html: '', recipients: '' })
  useEffect(() => { api.get('/alerts/templates').then((r) => setTpls(r.data)); api.get('/alerts/targets').then((r) => setTg(r.data)) }, [])
  const t = tpls.find((x) => x.code === code)
  const options: string[] = !t || !tg ? [] : t.category === 'RE_GEN' ? tg.RE_GEN.flatMap((p: any) => p.generators) : tg[t.category] ?? []
  const send = async (preview: boolean) => { try { setRes((await api.post('/alerts/send', { template_code: code, category: t.category, targets, payload: { frequency: tg?.live.frequency, ...payload }, preview, centre_code: centreOf(activeCentre, user) })).data); setErr('') } catch (e) { setErr(errMsg(e)) } }
  return (
    <div className="space-y-3">
      <PageHeader title="Message Alerts" subtitle="Violation messages by State / RE generator (pooling station) / Miscellaneous with per-contact Alert / Emergency / Extreme flags." />
      {err && <Alert kind="error">{err}</Alert>}
      <div className="grid gap-3 lg:grid-cols-3">
        <Card title="Violation templates">
          <div className="space-y-1">{tpls.map((x) => <button key={x.code} onClick={() => { setCode(x.code); setTargets([]); setRes(null) }} className={cls('block w-full rounded px-2 py-1 text-left text-xs', code === x.code ? 'bg-grid-700 text-white' : 'hover:bg-slate-100')}>{x.name_en} <span className="opacity-70">({x.category}, {x.severity})</span></button>)}</div>
        </Card>
        <Card title={t?.name_en ?? 'Template'} className="lg:col-span-2">
          {t && <div className="space-y-2">
            <div className="rounded bg-slate-50 p-2 font-mono text-xs">{t.sms_template}</div>
            <div className="grid gap-2 md:grid-cols-3">{t.fields.filter((f: any) => !['utility', 'generator', 'centre'].includes(f.key)).map((f: any) => <Field key={f.key} label={f.label}><input className={inputCls} value={payload[f.key] ?? (f.key === 'frequency' ? String(tg?.live.frequency ?? '') : '')} onChange={(e) => setPayload({ ...payload, [f.key]: e.target.value })} /></Field>)}</div>
            <div className="text-xs font-semibold">Recipients ({t.category})</div>
            <div className="flex flex-wrap gap-2">{options.map((o) => <label key={o} className="flex items-center gap-1 text-xs"><input type="checkbox" checked={targets.includes(o)} onChange={(e) => setTargets(e.target.checked ? [...targets, o] : targets.filter((x) => x !== o))} />{o}</label>)}</div>
            <div className="flex gap-2"><Button variant="secondary" onClick={() => send(true)}>Preview</Button><Button onClick={() => send(false)}>Send SMS + e-mail</Button></div>
            {res && <div className="text-xs">{res.messages.map((m: any) => <div key={m.target} className="border-t py-1"><b>{m.target}</b> → {m.sms} {!res.preview && <Badge color="green">{m.recipients} sent</Badge>}</div>)}</div>}
          </div>}
        </Card>
      </div>
      <Card title="Flash report (rich text, e-mail)">
        <div className="grid gap-2 md:grid-cols-3"><input aria-label="Subject" placeholder="Subject" className={inputCls} value={flash.subject} onChange={(e) => setFlash({ ...flash, subject: e.target.value })} /><input aria-label="Recipients" placeholder="Recipients (comma separated)" className={inputCls} value={flash.recipients} onChange={(e) => setFlash({ ...flash, recipients: e.target.value })} />
          <Button onClick={() => api.post('/alerts/flash-report', { subject: flash.subject, html: flash.html, recipients: flash.recipients.split(',').map((s) => s.trim()).filter(Boolean) }).then(() => setFlash({ subject: '', html: '', recipients: '' }))}>Send flash report</Button></div>
        <div contentEditable aria-label="Flash report body" className="mt-2 min-h-[80px] rounded border p-2 text-sm" onInput={(e) => setFlash({ ...flash, html: (e.target as HTMLDivElement).innerHTML })} suppressContentEditableWarning>Type the flash report… use Ctrl+B / Ctrl+I / Ctrl+U for formatting.</div>
      </Card>
    </div>
  )
}

export function ContactsPage() {
  useRecentPages('Contact directory')
  const { data, reload } = useAutoRefresh<any[]>('/alerts/contacts', undefined, { live: false })
  const [tab, setTab] = useState('')
  const orgs = [...new Set((data ?? []).map((c) => c.organisation))]
  const flag = (r: any, field: string, sev: string) => <input type="checkbox" aria-label={`${field} ${sev}`} checked={!!r[field]?.[sev]} onChange={(e) => api.patch(`/alerts/contacts/${r.id}`, { [field]: { ...r[field], [sev]: e.target.checked } }).then(reload)} />
  return (
    <div className="space-y-3">
      <PageHeader title="Contact directory" subtitle="Editable recipients with enable/disable per number/e-mail and per severity (Alert / Emergency / Extreme)." actions={<Button onClick={() => { const n = prompt('Name'); const o = prompt('Organisation'); if (n && o) api.post('/alerts/contacts', { name: n, organisation: o, category: 'MISC' }).then(reload) }}>+ Contact</Button>} />
      <Tabs active={tab} onChange={setTab} tabs={[{ key: '', label: 'All' }, ...orgs.map((o) => ({ key: o, label: o }))]} />
      <SpreadsheetGrid exportName="contacts" rows={(data ?? []).filter((c) => !tab || c.organisation === tab)} onCellEdit={(r, k, v) => api.patch(`/alerts/contacts/${r.id}`, { [k]: v }).then(reload)} columns={[
        { key: 'name', label: 'Name', editable: true }, { key: 'designation', label: 'Designation', editable: true }, { key: 'organisation', label: 'Organisation' }, { key: 'category', label: 'Category', editable: true, options: ['STATE', 'RE_GEN', 'MISC'] },
        { key: 'phone1', label: 'Phone 1', editable: true }, { key: 'email1', label: 'E-mail 1', editable: true },
        ...['ALERT', 'EMERGENCY', 'EXTREME'].flatMap((s) => [{ key: `sms_${s}`, label: `SMS ${s.slice(0, 5)}`, render: (r: any) => flag(r, 'alert_sms_flags_json', s) }, { key: `em_${s}`, label: `Mail ${s.slice(0, 5)}`, render: (r: any) => flag(r, 'alert_email_flags_json', s) }]),
        { key: 'x', label: '', render: (r) => <Button size="sm" variant="danger" onClick={() => api.delete(`/alerts/contacts/${r.id}`).then(reload)}>✕</Button> }]} />
    </div>
  )
}

export function AlertHistoryPage() {
  useRecentPages('Message history')
  const { data } = useAutoRefresh<any>('/alerts/history', undefined, { intervalMs: 10000 })
  return (
    <div className="space-y-3">
      <PageHeader title="Constituent-wise status of past messages" />
      {data && <div className="grid gap-3 md:grid-cols-2"><Card title="By constituent"><DynamicChart type="bar" height={180} data={objToSeries(data.by_target)} xKey="name" series={['value']} /></Card><Card title="By template"><DynamicChart type="pie" height={180} data={objToSeries(data.by_template)} xKey="name" series={['value']} /></Card></div>}
      <SpreadsheetGrid exportName="message_history" rows={data?.rows ?? []} columns={[{ key: 'sent_at', label: 'Sent', exportValue: (r) => fmtDT(r.sent_at), render: (r) => fmtDT(r.sent_at) }, { key: 'target', label: 'Constituent' }, { key: 'template', label: 'Template' }, { key: 'sms', label: 'Message' }, { key: 'recipients', label: 'Recipients' }]} />
    </div>
  )
}

// ------------------------------------------------------------------ SPS
export function SpsPage() {
  useRecentPages('SPS status')
  const { data, reload, updatedAt } = useAutoRefresh<any[]>('/sps/schemes')
  const [tl, setTl] = useState<{ s: any; rows: any[] } | null>(null)
  const rows = data ?? []
  return (
    <div className="space-y-3">
      <PageHeader title="SPS healthiness" subtitle="Real-time ON / OFF / degraded status of System Protection Schemes; user and SCADA updates; timeline and Excel export." actions={<><LastUpdated at={updatedAt} /><Button variant="secondary" onClick={() => download('/sps/schemes', 'sps_status.xlsx', { fmt: 'xlsx' })}>Excel</Button></>} />
      <div className="grid grid-cols-3 gap-3"><Stat label="ON" value={rows.filter((r) => r.status === 'ON').length} tone="green" /><Stat label="OFF" value={rows.filter((r) => r.status === 'OFF').length} tone="red" /><Stat label="Degraded" value={rows.filter((r) => r.status === 'DEGRADED').length} tone="amber" /></div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-3 xl:grid-cols-5">{rows.map((s) => (
        <div key={s.id} className={cls('rounded-lg border-2 p-3 text-sm', s.status === 'ON' ? 'border-emerald-400 bg-emerald-50' : s.status === 'OFF' ? 'border-red-400 bg-red-50' : 'border-amber-400 bg-amber-50')}>
          <div className="font-semibold">{s.sps_id}</div><div className="text-xs">{s.sps_name}</div><div className="mt-1 text-[11px] text-slate-500">{fmtDT(s.updated_at)}</div>
          <div className="mt-2 flex gap-1">{['ON', 'OFF', 'DEGRADED'].map((st) => <Button key={st} size="sm" variant={st === s.status ? 'primary' : 'secondary'} onClick={() => api.post(`/sps/schemes/${s.id}/status`, { status: st }).then(reload)}>{st}</Button>)}
            <Button size="sm" variant="ghost" onClick={() => api.get(`/sps/schemes/${s.id}/timeline`).then((r) => setTl({ s, rows: r.data }))}>Timeline</Button></div>
        </div>))}</div>
      <Modal open={!!tl} onClose={() => setTl(null)} title={`Timeline ${tl?.s.sps_id}`} wide>
        {tl && <DynamicChart type="line" height={220} data={tl.rows.map((r) => ({ at: fmtDT(r.at).slice(0, 16), state: r.status === 'ON' ? 1 : r.status === 'DEGRADED' ? 0.5 : 0 }))} xKey="at" series={['state']} />}
        <SpreadsheetGrid exportName="sps_timeline" compact rows={tl?.rows ?? []} columns={[{ key: 'at', label: 'At', exportValue: (r) => fmtDT(r.at) }, { key: 'status', label: 'Status' }, { key: 'source', label: 'Source' }, { key: 'remarks', label: 'Remarks' }]} />
      </Modal>
    </div>
  )
}
