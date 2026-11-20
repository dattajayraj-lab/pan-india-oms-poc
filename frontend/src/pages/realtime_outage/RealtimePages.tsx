// Real-Time Outage Management screens (TS Cl. 11.4.4; FRD RTO-*).
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, download, errMsg } from '../../api/client'
import { useAuth } from '../../store/auth'
import { fmtDT, useAutoRefresh, useLiveChannel, useRecentPages } from '../../store/hooks'
import SpreadsheetGrid from '../../components/common/SpreadsheetGrid'
import DynamicChart from '../../components/charts/DynamicChart'
import { Alert, Badge, Button, Card, Field, LastUpdated, Modal, PageHeader, Stat, Tabs, cls, inputCls } from '../../components/common/ui'

function useCentre() {
  const { activeCentre, user } = useAuth()
  return activeCentre !== 'ALL' ? activeCentre : user?.centre?.code === 'NLDC' ? 'NRLDC' : user?.centre?.code ?? 'NRLDC'
}
const localInput = (d = new Date()) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
const toIso = (v: string) => (v ? new Date(v).toISOString() : undefined)

/** Sticky control-room banner: active shift, in-charge, countdown, weather ticker, quick actions (plan §4.2). */
export function ControlRoomShiftBar() {
  const centre = useCentre()
  const nav = useNavigate()
  const { data } = useAutoRefresh<any>('/realtime/shifts/active', { centre })
  const { data: dash } = useAutoRefresh<any>('/realtime/dashboard', { centre })
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t) }, [])
  const a = data?.active
  const left = a ? Math.max(0, new Date(a.window_end + 'Z').getTime() - now) : 0
  const hh = Math.floor(left / 3600000), mm = Math.floor((left % 3600000) / 60000), ss = Math.floor((left % 60000) / 1000)
  return (
    <div className="sticky top-[72px] z-10 mb-5 flex flex-wrap items-center gap-3 rounded-xl bg-grid-950 px-4 py-2.5 text-xs text-white shadow-lift ring-1 ring-white/10">
      <span className="font-semibold">{centre}</span>
      {a ? <><Badge color="green">{a.shift_type} shift</Badge><span>In-charge: {a.incharge}</span><span>Handover in {hh}h {mm}m {ss}s</span></> : <Badge color="red">No active shift{data?.expected_next ? ` · next: ${data.expected_next}` : ''}</Badge>}
      <div className="min-w-0 flex-1 overflow-hidden whitespace-nowrap text-amber-300">
        <span className="inline-block animate-marquee">{(dash?.alerts ?? []).map((x: any) => `⚠ ${x.source}: ${x.message}`).join('   •   ') || 'No weather / SCADA alerts'}</span>
      </div>
      <div className="flex gap-1">
        <Button size="sm" variant="secondary" onClick={() => nav('/realtime/request')}>Request code</Button>
        <Button size="sm" variant="secondary" onClick={() => nav('/realtime/codes')}>Issue / due codes</Button>
        <Button size="sm" variant="secondary" onClick={() => nav('/realtime/request?cat=TRIPPED')}>Report tripping</Button>
        <Button size="sm" variant="secondary" onClick={() => nav('/realtime/shift')}>Shift handover</Button>
      </div>
    </div>
  )
}

export function ControlRoomPage() {
  useRecentPages('Control room')
  const centre = useCentre()
  const { user } = useAuth()
  const { data, updatedAt, reload } = useAutoRefresh<any>('/realtime/dashboard', { centre })
  const { data: gate } = useAutoRefresh<any>('/realtime/gate', undefined, { intervalMs: 10000 })
  const [freq, setFreq] = useState<{ t: string; f: number }[]>([])
  useLiveChannel(centre, () => reload())
  useEffect(() => { if (data) setFreq((p) => [...p.slice(-59), { t: new Date().toLocaleTimeString(), f: Number(data.tiles[0].value) }]) }, [data])
  if (!data) return null
  return (
    <div className="space-y-4">
      <ControlRoomShiftBar />
      <PageHeader title={`Real-time Outage Management · ${centre}`} subtitle="Planned, forced, emergency, tripping, FTC, anti-theft, AR, suo-moto, HV/LV and RE codes with consent engine." actions={<LastUpdated at={updatedAt} />} />
      {gate?.blocked && user?.is_external && <Alert kind="error">Code requests blocked until you fill: {gate.pending_exec.map((c: any) => c.code_number).join(', ')} {gate.pending_revival.map((u: any) => u.name).join(', ')} — <Link className="underline" to="/realtime/codes">go to pending entries</Link></Alert>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        {data.tiles.slice(0, 2).map((t: any) => <Stat key={t.key} label={t.label_en} value={t.value} />)}
        <Stat label="RE generation (MW)" value={data.re_generation_mw} tone="green" />
        <Stat label="Under outage" value={data.under_outage} tone="amber" />
        <Stat label="Tripped" value={data.tripped} tone="red" />
        <Stat label="Codes (24 h)" value={data.codes_today} />
        <Stat label="Pending consents" value={data.pending_consents} tone="amber" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Grid frequency (live)" className="lg:col-span-2"><DynamicChart type="line" height={200} data={freq} xKey="t" series={['f']} /></Card>
        <Card title="Pending requests by category">
          <ul className="space-y-1 text-sm">{Object.entries(data.pending_by_category).map(([k, v]) => <li key={k} className="flex justify-between"><span>{k}</span><Badge color="amber">{String(v)}</Badge></li>)}{!Object.keys(data.pending_by_category).length && <li className="text-slate-400">None</li>}</ul>
        </Card>
        <Card title="Units under outage"><ul className="text-sm">{data.units_out.map((u: any) => <li key={u.name}>{u.name} <span className="text-xs text-slate-500">since {fmtDT(u.since)}</span></li>)}{!data.units_out.length && <li className="text-slate-400">None</li>}</ul></Card>
        <Card title="Cumulative availability (hours since last restoration)" className="lg:col-span-2"><DynamicChart type="bar" height={200} data={data.availability_hours} xKey="element" series={['hours']} /></Card>
      </div>
    </div>
  )
}

export function ShiftPage() {
  useRecentPages('Shift management')
  const centre = useCentre()
  const { user } = useAuth()
  const { data, reload } = useAutoRefresh<any>('/realtime/shifts/active', { centre }, { intervalMs: 5000 })
  const { data: hist } = useAutoRefresh<any[]>('/realtime/shifts', { centre }, { intervalMs: 10000 })
  const [staffList, setStaffList] = useState<any[]>([])
  const [staff, setStaff] = useState<{ user_id: number; desk: string }[]>([])
  const [type, setType] = useState('MORNING')
  const [notes, setNotes] = useState({ handover_notes: '', important_events: '' })
  const [err, setErr] = useState('')
  const [popup, setPopup] = useState('')
  useEffect(() => { api.get('/realtime/staff', { params: { centre } }).then((r) => setStaffList(r.data)) }, [centre])
  useEffect(() => { if (data?.expected_next) setType(data.expected_next); if (data?.active) setNotes({ handover_notes: data.active.handover_notes, important_events: data.active.important_events }) }, [data?.expected_next, data?.active?.id]) // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (fn: () => Promise<any>) => { try { await fn(); setErr(''); reload() } catch (e) { const m = errMsg(e); if (m.startsWith('Wrong shift')) setPopup(m); else setErr(m) } }
  const a = data?.active
  return (
    <div className="space-y-4">
      <ControlRoomShiftBar />
      <PageHeader title="Shift management" subtitle="Strict Morning → Evening → Night sequence; previous shift closure required; sessions of previous shift auto-logged out." />
      {err && <Alert kind="error">{err}</Alert>}
      {!a ? (
        <Card title={`Create shift (${centre})`}>
          <div className="grid gap-3 md:grid-cols-3">
            <Field label="Shift"><select className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>{['MORNING', 'EVENING', 'NIGHT'].map((t) => <option key={t}>{t}</option>)}</select></Field>
            <div className="text-xs text-slate-600 md:col-span-2">Timings: {data && Object.entries(data.timings).map(([k, v]: any) => `${k} ${fmtDT(v[0]).slice(11, 16)}`).join(' · ')}<br />Expected next: <b>{data?.expected_next ?? 'any (first shift)'}</b></div>
          </div>
          <div className="mt-2 space-y-1">
            <div className="text-xs font-semibold">Assign executives & desks</div>
            {staffList.filter((s) => s.id !== user?.id).map((s) => {
              const sel = staff.find((x) => x.user_id === s.id)
              return (
                <div key={s.id} className="flex items-center gap-2 text-xs">
                  <input type="checkbox" aria-label={s.name} checked={!!sel} onChange={(e) => setStaff(e.target.checked ? [...staff, { user_id: s.id, desk: 'RTSD' }] : staff.filter((x) => x.user_id !== s.id))} />{s.name}
                  {sel && <select aria-label="Desk" className="rounded border text-xs" value={sel.desk} onChange={(e) => setStaff(staff.map((x) => (x.user_id === s.id ? { ...x, desk: e.target.value } : x)))}>{['RTSD', 'SCHEDULING', 'OUTAGE_DESK', 'SCADA_DESK'].map((d) => <option key={d}>{d}</option>)}</select>}
                </div>
              )
            })}
          </div>
          <Button className="mt-3" onClick={() => run(() => api.post('/realtime/shifts/open', { centre_code: centre, shift_type: type, staff }))}>Create {type.toLowerCase()} shift</Button>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title={`${a.shift_type} shift · ${a.shift_date}`} actions={<Badge color="green">OPEN</Badge>}>
            <div className="text-sm">In-charge: <b>{a.incharge}</b></div>
            <ul className="mt-1 text-xs">{a.staff.map((s: any) => <li key={s.user_id}>{s.name} · {s.desk}</li>)}</ul>
            {data.on_shift && <Button size="sm" variant="secondary" className="mt-2" onClick={() => run(() => api.post(`/realtime/shifts/${a.id}/join`))}>Bind my session to this shift</Button>}
          </Card>
          <Card title="Regular works checklist (before handover)">
            {a.works.map((w: any) => <label key={w.key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={w.done} onChange={(e) => run(() => api.patch(`/realtime/shifts/${a.id}/works`, { key: w.key, done: e.target.checked }))} />{w.text}</label>)}
          </Card>
          <Card title="Handover (shift in-charge)" className="lg:col-span-2">
            <div className="grid gap-2 md:grid-cols-2">
              <Field label="Handover notes"><textarea className={cls(inputCls, 'h-20')} value={notes.handover_notes} onChange={(e) => setNotes({ ...notes, handover_notes: e.target.value })} /></Field>
              <Field label="Important tripping events"><textarea className={cls(inputCls, 'h-20')} value={notes.important_events} onChange={(e) => setNotes({ ...notes, important_events: e.target.value })} /></Field>
            </div>
            <div className="mt-2 flex gap-2">
              <Button variant="secondary" onClick={() => run(() => api.put(`/realtime/shifts/${a.id}/handover`, notes))}>Save</Button>
              <Button variant="danger" onClick={() => run(async () => { await api.put(`/realtime/shifts/${a.id}/handover`, notes); await api.post(`/realtime/shifts/${a.id}/close`) })}>Submit closure & finalise report</Button>
              <Link to={`/realtime/shift-report?id=${a.id}`}><Button variant="ghost">Shift report draft</Button></Link>
            </div>
          </Card>
        </div>
      )}
      <Card title="Shift history"><SpreadsheetGrid exportName="shifts" compact rows={hist ?? []} columns={[{ key: 'shift_date', label: 'Date' }, { key: 'shift_type', label: 'Shift' }, { key: 'incharge', label: 'In-charge' }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> }, { key: 'report_status', label: 'Report' }, { key: 'x', label: '', render: (r) => <Link className="text-grid-700 underline" to={`/realtime/shift-report?id=${r.id}`}>Report</Link> }]} /></Card>
      <Modal open={!!popup} onClose={() => setPopup('')} title="Wrong shift selection"><Alert kind="error">{popup}</Alert></Modal>
    </div>
  )
}

const CATS: [string, string][] = [['PLANNED', 'Planned (approved list)'], ['FORCED', 'Forced outage'], ['EMERGENCY', 'Emergency outage'], ['TRIPPED', 'Report tripping'],
  ['FTC', 'First time charging code'], ['ANTI_THEFT', 'Anti-theft charging'], ['AR_OFF', 'AR enable/disable'], ['SUO_MOTO', 'Suo-moto'], ['SPS_TEST', 'SPS testing'],
  ['HOT_LINE', 'Hot line maintenance'], ['TAP_CHANGE', 'Tap changing'], ['OPPORTUNITY', 'Opportunity shutdown'], ['BREAKDOWN', 'Breakdown'], ['OTHER_ELEMENT', 'Element not in master DB'], ['MINOR_ALTERATION', 'Minor alteration (B6/B7/B8)']]

export function RequestCodePage() {
  useRecentPages('Request code')
  const centre = useCentre()
  const { user } = useAuth()
  const params = new URLSearchParams(location.search)
  const [cat, setCat] = useState(params.get('cat') ?? 'PLANNED')
  const [els, setEls] = useState<any[]>([])
  const [meta, setMeta] = useState<any>(null)
  const [reasons, setReasons] = useState<string[]>([])
  const [f, setF] = useState<any>({ grid_element_id: '', action: 'OPENING', reason: '', remarks: '', suo_moto_case_no: '', anti_theft_case: '1', planned_time: '', availability_head_proposed: 'SELF', other_element_desc: '', relay_flags: '', tripped_at: localInput(), expected_revival_at: '', fault_distance_km: '' })
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const { data: gate } = useAutoRefresh<any>('/realtime/gate', undefined, { intervalMs: 10000 })
  useEffect(() => {
    api.get('/master/elements', { params: { centre: user?.is_external ? undefined : centre } }).then((r) => setEls(r.data))
    api.get('/realtime/meta').then((r) => setMeta(r.data)); api.get('/realtime/reasons').then((r) => setReasons(r.data))
  }, [centre, user])
  const el = els.find((e) => String(e.id) === String(f.grid_element_id))
  const submit = async () => {
    try {
      if (cat === 'TRIPPED') {
        await api.post('/realtime/trippings', { grid_element_id: Number(f.grid_element_id), relay_flags: f.relay_flags, tripped_at: toIso(f.tripped_at), reason: f.reason, expected_revival_at: toIso(f.expected_revival_at) })
        setMsg({ kind: 'success', text: 'Tripping reported to RLDC; now request a code to attend the fault.' }); return
      }
      const { data } = await api.post('/realtime/requests', { request_category: cat, grid_element_id: f.grid_element_id ? Number(f.grid_element_id) : undefined, action: f.action, reason: f.reason, remarks: f.remarks,
        suo_moto_case_no: f.suo_moto_case_no ? Number(f.suo_moto_case_no) : undefined, anti_theft_case: cat === 'ANTI_THEFT' ? Number(f.anti_theft_case) : undefined,
        planned_time: toIso(f.planned_time), availability_head_proposed: f.availability_head_proposed, other_element_desc: f.other_element_desc, centre_code: centre,
        protection_details: cat === 'FORCED' ? { fault_distance_km: f.fault_distance_km, relay_flags: f.relay_flags } : {} })
      setMsg({ kind: 'success', text: `Request ${data.request_number} raised (${data.status}). Consents: ${data.consents.map((c: any) => c.entity).join(', ') || 'none required'}` })
    } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) }
  }
  return (
    <div className="space-y-4">
      <PageHeader title="Request code" subtitle="Requests route automatically to all associated stakeholders for consent; no code without consent." />
      {gate?.blocked && <Alert kind="error">Blocked: fill execution time for {gate.pending_exec.map((c: any) => c.code_number).join(', ')} / expected revival for {gate.pending_revival.map((u: any) => u.name).join(', ')}. <Link className="underline" to="/realtime/codes">Open pending entries</Link></Alert>}
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="flex flex-wrap gap-1">{CATS.map(([k, l]) => <button key={k} onClick={() => setCat(k)} className={cls('rounded border px-2 py-1 text-xs', cat === k ? 'border-grid-700 bg-grid-700 text-white' : 'bg-white')}>{l}</button>)}</div>
      <Card>
        <div className="grid gap-3 md:grid-cols-3">
          {cat === 'OTHER_ELEMENT' ? <Field label="Element description (not in master DB)"><input className={inputCls} value={f.other_element_desc} onChange={(e) => setF({ ...f, other_element_desc: e.target.value })} /></Field> : (
            <Field label="Element"><select className={inputCls} value={f.grid_element_id} onChange={(e) => setF({ ...f, grid_element_id: e.target.value })}><option value="">— select —</option>{els.map((e) => <option key={e.id} value={e.id}>{e.unique_element_id} · {e.name} ({e.status})</option>)}</select></Field>)}
          {cat !== 'TRIPPED' && <Field label="Action"><select className={inputCls} value={f.action} onChange={(e) => setF({ ...f, action: e.target.value })}><option value="OPENING">Opening / shutdown</option><option value="CHARGING">Charging / revival</option></select></Field>}
          <Field label="Reason"><input list="reasons" className={inputCls} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /><datalist id="reasons">{reasons.map((r) => <option key={r} value={r} />)}</datalist></Field>
          {cat === 'SUO_MOTO' && <Field label="Suo-moto case (Table 9)"><select className={inputCls} value={f.suo_moto_case_no} onChange={(e) => setF({ ...f, suo_moto_case_no: e.target.value })}><option value="" />{meta?.suo_moto_cases.map((s: any) => <option key={s.no} value={s.no}>{s.no}. {s.desc}{s.needs_scada_voltage ? ' (SCADA voltage)' : ''}</option>)}</select></Field>}
          {cat === 'ANTI_THEFT' && <Field label="Tower-collapse case"><select className={inputCls} value={f.anti_theft_case} onChange={(e) => setF({ ...f, anti_theft_case: e.target.value })}><option value="1">Case 1: from Station A to farthest healthy tower</option><option value="2">Case 2: from Station B to farthest healthy tower</option><option value="3">Case 3: from both stations</option></select></Field>}
          {cat === 'FORCED' && <><Field label="Fault distance (km)"><input className={inputCls} value={f.fault_distance_km} onChange={(e) => setF({ ...f, fault_distance_km: e.target.value })} /></Field><Field label="Relay flags"><input className={inputCls} value={f.relay_flags} onChange={(e) => setF({ ...f, relay_flags: e.target.value })} /></Field></>}
          {cat === 'TRIPPED' && <><Field label="Relay flags"><input className={inputCls} value={f.relay_flags} onChange={(e) => setF({ ...f, relay_flags: e.target.value })} /></Field><Field label="Time of tripping"><input type="datetime-local" max={localInput()} className={inputCls} value={f.tripped_at} onChange={(e) => setF({ ...f, tripped_at: e.target.value })} /></Field><Field label="Expected revival"><input type="datetime-local" className={inputCls} value={f.expected_revival_at} onChange={(e) => setF({ ...f, expected_revival_at: e.target.value })} /></Field></>}
          {['PLANNED', 'FTC', 'ANTI_THEFT'].includes(cat) && <Field label="Planned time"><input type="datetime-local" className={inputCls} value={f.planned_time} onChange={(e) => setF({ ...f, planned_time: e.target.value })} /></Field>}
          {['FORCED', 'EMERGENCY', 'PLANNED'].includes(cat) && <Field label="Availability head (proposed)"><select className={inputCls} value={f.availability_head_proposed} onChange={(e) => setF({ ...f, availability_head_proposed: e.target.value })}>{meta?.availability_heads.map((h: string) => <option key={h}>{h}</option>)}</select></Field>}
          <Field label="Remarks"><input className={inputCls} value={f.remarks} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></Field>
        </div>
        {el && <div className="mt-3 rounded bg-slate-50 p-2 text-xs">Owners: {el.owners.map((o: any) => `${o.entity} (${o.role})`).join(', ')} · Weather area: {el.weather_area}{el.notes.length > 0 && <div className="mt-1 text-amber-800">📝 Operator notes: {el.notes.map((n: any) => n.text).join(' | ')}</div>}{el.comments && <div>💬 {el.comments}</div>}</div>}
        <Button className="mt-3" onClick={submit}>{cat === 'TRIPPED' ? 'Report tripping' : 'Submit request'}</Button>
      </Card>
    </div>
  )
}

export function CodebookPage() {
  useRecentPages('Codebook')
  const centre = useCentre()
  const { user } = useAuth()
  const [tab, setTab] = useState('REQUESTS')
  const { data: reqs, reload: rr } = useAutoRefresh<any[]>('/realtime/requests', { centre, status: 'OPEN' })
  const { data: codes, reload: rc, updatedAt } = useAutoRefresh<any[]>('/realtime/codes', { centre, view: tab === 'REQUESTS' ? 'ALL' : tab })
  const { data: trips, reload: rt } = useAutoRefresh<any[]>('/realtime/trippings', { centre })
  const [exec, setExec] = useState<Record<number, string>>({})
  const [err, setErr] = useState('')
  const operator = !user?.is_external
  useLiveChannel(centre, () => { rr(); rc() })
  const run = async (fn: () => Promise<any>) => { try { await fn(); setErr(''); rr(); rc(); rt() } catch (e) { setErr(errMsg(e)) } }
  const codeCols = [
    { key: 'code_number', label: 'Code' }, { key: 'code_type', label: 'Type' }, { key: 'element', label: 'Element' }, { key: 'issued_by', label: 'Issued by' },
    { key: 'issued_at', label: 'Issued', exportValue: (r: any) => fmtDT(r.issued_at), render: (r: any) => fmtDT(r.issued_at) },
    { key: 'status', label: 'Status', render: (r: any) => <Badge>{r.status}</Badge> },
    { key: 'ends', label: 'End-1 / End-2', render: (r: any) => <span className="text-[11px]">{fmtDT(r.end1_exec_time) || '—'}<br />{r.two_ended ? fmtDT(r.end2_exec_time) || '—' : ''}</span> },
    { key: 'final_exec_time', label: 'Final', exportValue: (r: any) => fmtDT(r.final_exec_time), render: (r: any) => fmtDT(r.final_exec_time) },
    { key: 'x', label: 'Action', render: (r: any) => r.status === 'REVOKED' ? null : (
      <div className="flex flex-wrap items-center gap-1">
        {!r.final_exec_time && (user?.is_external ? r.my_end : true) && <><input aria-label="Execution time" type="datetime-local" max={localInput()} className="rounded border px-1 text-[11px]" value={exec[r.id] ?? ''} onChange={(e) => setExec({ ...exec, [r.id]: e.target.value })} />
          <Button size="sm" onClick={() => run(() => api.post(`/realtime/codes/${r.id}/execute`, { exec_time: toIso(exec[r.id] || localInput()), end: operator ? (r.end1_exec_time ? 'END2' : 'END1') : undefined }))}>Enter {r.my_end ?? ''} time</Button></>}
        {operator && !r.final_exec_time && <Button size="sm" variant="danger" onClick={() => run(() => api.post(`/realtime/codes/${r.id}/revoke`, { reason: 'Revoked by operator' }))}>Revoke</Button>}
      </div>) },
  ]
  return (
    <div className="space-y-4">
      <ControlRoomShiftBar />
      <PageHeader title="Codebook" subtitle="Requested codes (sheet), consent status, due for charging / outage, execution times from both ends, 1-hour validity." actions={<LastUpdated at={updatedAt} />} />
      {err && <Alert kind="error">{err}</Alert>}
      <Tabs active={tab} onChange={setTab} tabs={[{ key: 'REQUESTS', label: 'Requested codes', count: reqs?.length }, { key: 'DUE_CHARGING', label: 'Due for charging' }, { key: 'DUE_OUTAGE', label: 'Due for outage' }, { key: 'TODAY', label: 'Issued (24 h)' }, { key: 'TRIPS', label: 'Tripped elements', count: trips?.length }]} />
      {tab === 'REQUESTS' && <SpreadsheetGrid exportName="code_requests" rows={reqs ?? []} columns={[
        { key: 'request_number', label: 'Request' }, { key: 'category', label: 'Category' }, { key: 'action', label: 'Action' }, { key: 'element', label: 'Element' }, { key: 'requester_entity', label: 'Requester' },
        { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> },
        { key: 'consents', label: 'Consents', exportValue: (r) => r.consents.map((c: any) => `${c.entity}:${c.status}`).join(';'), render: (r) => <div className="space-y-0.5">{r.consents.map((c: any) => <div key={c.id} className="text-[11px]">{c.entity} <Badge>{c.info_only ? 'INFO' : c.status}</Badge>{c.mine && c.status === 'PENDING' && !c.info_only && <><Button size="sm" variant="success" onClick={() => run(() => api.post(`/realtime/requests/${r.id}/consent`, { approve: true }))}>Consent</Button><Button size="sm" variant="danger" onClick={() => run(() => api.post(`/realtime/requests/${r.id}/consent`, { approve: false, remarks: 'Not agreed' }))}>Deny</Button></>}</div>)}</div> },
        { key: 'weather', label: 'Weather', render: (r) => r.weather_alerts.length ? <span className="text-[11px] text-amber-700">⚠ {r.weather_alerts[0]}</span> : '' },
        { key: 'x', label: 'RLDC action', render: (r) => operator ? <div className="flex gap-1"><Button size="sm" disabled={!r.consents_complete && !['SUO_MOTO', 'TRIPPED', 'EMERGENCY'].includes(r.category)} title={r.consents_complete ? '' : 'Consent pending'} onClick={() => run(() => api.post(`/realtime/requests/${r.id}/issue-code`, {}))}>Issue code</Button><Button size="sm" variant="danger" onClick={() => run(() => api.post(`/realtime/requests/${r.id}/decide`, { approve: false, remarks: 'Not feasible' }))}>Disapprove</Button></div> : null },
      ]} />}
      {['DUE_CHARGING', 'DUE_OUTAGE', 'TODAY'].includes(tab) && <SpreadsheetGrid exportName="codes" rows={codes ?? []} columns={codeCols} rowClassName={(r) => (r.status === 'EXPIRED' ? 'bg-red-50' : '')} />}
      {tab === 'TRIPS' && <SpreadsheetGrid exportName="trippings" rows={trips ?? []} columns={[{ key: 'element', label: 'Element' }, { key: 'relay_flags', label: 'Relay flags' }, { key: 'tripped_at', label: 'Tripped', exportValue: (r) => fmtDT(r.tripped_at) }, { key: 'reason', label: 'Reason' }, { key: 'expected_revival_at', label: 'Expected revival', exportValue: (r) => fmtDT(r.expected_revival_at) },
        { key: 'x', label: '', render: (r) => operator && !r.acknowledged ? <Button size="sm" onClick={() => run(() => api.post(`/realtime/trippings/${r.id}/ack`))}>Acknowledge</Button> : r.acknowledged ? <Badge color="green">ACK</Badge> : null }]} />}
    </div>
  )
}

export function ElementListPage() {
  useRecentPages('Element list')
  const centre = useCentre()
  const { user } = useAuth()
  const [kv, setKv] = useState('')
  const { data, reload } = useAutoRefresh<any[]>('/master/elements', { centre: user?.is_external ? undefined : centre, voltage: kv || undefined }, { intervalMs: 5000 })
  const [sel, setSel] = useState<any>(null)
  const [note, setNote] = useState('')
  return (
    <div className="space-y-3">
      <PageHeader title="Element list" subtitle="Voltage-level tabs, live status, operator notes (append-only) and comments (overwritable)." />
      <Tabs active={kv} onChange={setKv} tabs={[{ key: '', label: 'All' }, { key: '765', label: '765 kV' }, { key: '400', label: '400 kV' }, { key: '220', label: '220 kV' }, { key: '33', label: '33 kV' }]} />
      <SpreadsheetGrid exportName="elements" rows={data ?? []} rowClassName={(r) => (r.status === 'TRIPPED' ? 'bg-red-50' : r.status === 'OUTAGE' ? 'bg-amber-50' : '')} columns={[
        { key: 'unique_element_id', label: 'ID', render: (r) => <button className="text-grid-700 underline" onClick={() => setSel(r)}>{r.unique_element_id}</button>, exportValue: (r) => r.unique_element_id },
        { key: 'name', label: 'Element' }, { key: 'element_type_label', label: 'Type' }, { key: 'voltage_kv', label: 'kV' }, { key: 'from_substation', label: 'From' }, { key: 'to_substation', label: 'To' },
        { key: 'owners', label: 'Owners', exportValue: (r) => r.owners.map((o: any) => o.entity).join(', ') }, { key: 'status', label: 'Status', render: (r) => <Badge>{r.status}</Badge> }]} />
      <Modal open={!!sel} onClose={() => setSel(null)} title={sel?.name ?? ''} wide>
        {sel && <div className="space-y-2 text-sm">
          <div className="grid grid-cols-2 gap-1 md:grid-cols-4">{['unique_element_id', 'element_type_label', 'voltage_kv', 'rating', 'length_km', 'from_region', 'to_region', 'ftc_date', 'cod_date', 'status'].map((k) => <div key={k}><div className="text-xs text-slate-500">{k}</div>{String(sel[k] ?? '—')}</div>)}</div>
          <div><b>Owners:</b> {sel.owners.map((o: any) => `${o.entity} (${o.role}${o.section_km ? `, ${o.section_km} km` : ''})`).join(', ')}</div>
          <div><b>Notes (append-only):</b><ul className="text-xs">{sel.notes.map((n: any, i: number) => <li key={i}>{n.by} · {n.at.slice(0, 16)}: {n.text}</li>)}</ul></div>
          {!user?.is_external && <div className="flex gap-1"><input aria-label="Note" className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} /><Button onClick={async () => { const r = await api.post(`/master/elements/${sel.id}/notes`, { text: note }); setSel({ ...sel, notes: r.data.notes }); setNote(''); reload() }}>Add note</Button></div>}
        </div>}
      </Modal>
    </div>
  )
}

export function ReMvarPage() {
  useRecentPages('RE single window')
  const centre = useCentre()
  const { data } = useAutoRefresh<any[]>('/realtime/re-plants', { centre }, { live: false })
  const [mode, setMode] = useState('FIXED_Q')
  const [vals, setVals] = useState<Record<number, string>>({})
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  return (
    <div className="space-y-3">
      <PageHeader title="Single window - RE plants MVAr / Vref / PF code" subtitle="Tick plants, enter values, one code issued to all selected plants (TS p.164)." />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="flex gap-2"><select aria-label="Mode" className={cls(inputCls, 'w-64')} value={mode} onChange={(e) => setMode(e.target.value)}><option value="FIXED_Q">Fixed-Q mode (MVAr)</option><option value="VOLTAGE">Voltage control (Vref kV)</option><option value="FIXED_PF">Fixed-PF mode</option></select>
        <Button onClick={async () => { try { const items = Object.entries(vals).filter(([, v]) => v !== '').map(([k, v]) => ({ element_id: Number(k), value: Number(v) })); const { data: c } = await api.post('/realtime/re-mvar', { mode, items }, { params: { centre } }); setMsg({ kind: 'success', text: `Code ${c.code_number} issued` }) } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) } }}>Issue code</Button></div>
      <SpreadsheetGrid exportName="re_plants" rows={data ?? []} columns={[{ key: 'pooling_station', label: 'Pooling station' }, { key: 'plant', label: 'RE plant' }, { key: 'rated_mw', label: 'Rated MW' }, { key: 'q_capability_mvar', label: 'Q capability (33%)' }, { key: 'evacuating_line', label: 'Evacuating line' }, { key: 'poi', label: 'POI' },
        { key: 'v', label: mode === 'FIXED_Q' ? 'MVAr' : mode === 'VOLTAGE' ? 'Vref kV' : 'PF', render: (r) => <input aria-label={`Value ${r.plant}`} className="w-20 rounded border px-1" value={vals[r.element_id] ?? ''} onChange={(e) => setVals({ ...vals, [r.element_id]: e.target.value })} /> }]} />
    </div>
  )
}

export function ShiftReportPage() {
  useRecentPages('Shift report')
  const id = new URLSearchParams(location.search).get('id')
  const centre = useCentre()
  const { data: hist } = useAutoRefresh<any[]>('/realtime/shifts', { centre }, { live: false })
  const sid = id ?? hist?.[0]?.id
  const { data } = useAutoRefresh<any>(sid ? `/realtime/shifts/${sid}/report` : null, undefined, { intervalMs: 10000 })
  if (!data) return <PageHeader title="Shift report" subtitle="No shift yet" />
  const r = data.report
  return (
    <div className="space-y-3">
      <PageHeader title={`Shift report · ${r.shift} · ${r.centre}`} subtitle={`In-charge ${r.incharge}`} actions={<><Badge>{data.status}</Badge>{['pdf', 'xlsx'].map((f) => <Button key={f} variant="secondary" onClick={() => download(`/realtime/shifts/${sid}/report`, `shift_report.${f}`, { fmt: f })}>{f.toUpperCase()}</Button>)}</>} />
      <div className="grid grid-cols-3 gap-3"><Stat label="Max frequency" value={r.frequency.max} /><Stat label="Min frequency" value={r.frequency.min} /><Stat label="% time in IEGC band" value={r.frequency.pct_in_band} /></div>
      <Card title="Codes issued"><SpreadsheetGrid exportName="shift_codes" compact rows={r.codes} columns={[{ key: 'code', label: 'Code' }, { key: 'type', label: 'Type' }, { key: 'element', label: 'Element' }, { key: 'by', label: 'By' }, { key: 'executed', label: 'Executed', exportValue: (x) => fmtDT(x.executed) }]} /></Card>
      <div className="grid gap-3 md:grid-cols-3">
        <Card title="Trippings"><ul className="text-xs">{r.trippings.map((t: any, i: number) => <li key={i}>{t.element}: {t.reason}</li>)}</ul></Card>
        <Card title="Units under outage"><ul className="text-xs">{r.units_under_outage.map((u: any) => <li key={u.unit}>{u.unit}</li>)}</ul></Card>
        <Card title="SPS status"><ul className="text-xs">{r.sps.map((s: any) => <li key={s.sps_id}>{s.sps_id} <Badge>{s.status}</Badge></li>)}</ul></Card>
      </div>
      <Card title="Handover"><p className="whitespace-pre-wrap text-sm">{r.handover_notes}</p><p className="text-sm text-red-700">{r.important_events}</p></Card>
    </div>
  )
}

export function ElogPage() {
  useRecentPages('E-logbook')
  const centre = useCentre()
  const [cat, setCat] = useState('GRID_EVENT')
  const { data, reload } = useAutoRefresh<any[]>('/realtime/elog', { centre, category: cat }, { intervalMs: 5000 })
  const [f, setF] = useState({ title: '', body: '', entity_name: '' })
  return (
    <div className="space-y-3">
      <PageHeader title="Control-room e-logbook" subtitle="Grid events / flash reports, grid operation messages, curtailment, technical orders, STOA/T-GNA notes." />
      <Tabs active={cat} onChange={setCat} tabs={['GRID_EVENT', 'GRID_OPS', 'CURTAILMENT', 'TECH_ORDER', 'STOA', 'NOTE'].map((k) => ({ key: k, label: k.replace('_', ' ') }))} />
      <Card><div className="grid gap-2 md:grid-cols-4">
        <input aria-label="Title" placeholder="Title" className={inputCls} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
        <input aria-label="Details" placeholder="Details" className={inputCls} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} />
        <input aria-label="Entity / e-mail" placeholder="Entity / e-mail (grid ops)" className={inputCls} value={f.entity_name} onChange={(e) => setF({ ...f, entity_name: e.target.value })} />
        <Button onClick={() => api.post('/realtime/elog', { ...f, category: cat, centre_code: centre }).then(() => { setF({ title: '', body: '', entity_name: '' }); reload() })}>Add</Button>
      </div></Card>
      <SpreadsheetGrid exportName={`elog_${cat}`} rows={data ?? []} columns={[{ key: 'created_at', label: 'Time', exportValue: (r) => fmtDT(r.created_at), render: (r) => fmtDT(r.created_at) }, { key: 'title', label: 'Title' }, { key: 'body', label: 'Details' }, { key: 'entity_name', label: 'Entity' }, { key: 'by', label: 'By' },
        { key: 'x', label: '', render: (r) => <Button size="sm" variant="danger" onClick={() => api.delete(`/realtime/elog/${r.id}`).then(reload)}>Delete</Button> }]} />
    </div>
  )
}
