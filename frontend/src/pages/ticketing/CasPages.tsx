// Complaint Addressal System screens (TS Ch.5; FRD CAS-01..27).
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, download, errMsg } from '../../api/client'
import { useAuth } from '../../store/auth'
import { fmtDT, useAutoRefresh, useRecentPages } from '../../store/hooks'
import SpreadsheetGrid from '../../components/common/SpreadsheetGrid'
import CaseFlowchartTracker from '../../components/workflow/CaseFlowchartTracker'
import DynamicChart, { objToSeries } from '../../components/charts/DynamicChart'
import { Alert, Badge, Button, Card, Field, LastUpdated, Modal, PageHeader, Stat, Tabs, cls, inputCls } from '../../components/common/ui'

const ticketCols = [
  { key: 'ticket_number', label: 'Ticket ID', render: (r: any) => <Link className="font-medium text-grid-700 hover:underline" to={`/cas/${r.id}`}>{r.ticket_number}</Link>, exportValue: (r: any) => r.ticket_number },
  { key: 'subject', label: 'Subject' }, { key: 'module', label: 'Module' }, { key: 'centre', label: 'Centre' },
  { key: 'channel', label: 'Channel' }, { key: 'priority', label: 'Priority (AMC)' },
  { key: 'severity', label: 'Severity', render: (r: any) => r.severity ? <Badge color={r.severity === 1 ? 'red' : r.severity === 2 ? 'amber' : 'blue'}>S{r.severity}</Badge> : '—' },
  { key: 'escalation_level', label: 'Level', render: (r: any) => `L${r.escalation_level}` },
  { key: 'status', label: 'Status', render: (r: any) => <Badge>{r.status}</Badge> },
  { key: 'sla', label: 'SLA', render: (r: any) => (r.resolution_breached || r.response_breached ? <Badge color="red">BREACH</Badge> : r.severity ? <Badge color="green">OK</Badge> : '—'), exportValue: (r: any) => (r.resolution_breached ? 'BREACH' : 'OK') },
  { key: 'created_at', label: 'Logged', exportValue: (r: any) => fmtDT(r.created_at), render: (r: any) => fmtDT(r.created_at) },
]

export function TicketsPage() {
  const { t } = useTranslation()
  useRecentPages(t('modules.cas'))
  const [tab, setTab] = useState('ACTIVE')
  const { data, updatedAt } = useAutoRefresh<any[]>('/cas/tickets', { status: tab === 'ALL' ? undefined : tab })
  return (
    <div>
      <PageHeader title={t('modules.cas')} subtitle="Track, escalate, re-open and give feedback on complaints." actions={<><LastUpdated at={updatedAt} /><Link to="/cas/new"><Button>+ Lodge complaint</Button></Link></>} />
      <Tabs active={tab} onChange={setTab} tabs={[{ key: 'ACTIVE', label: 'Active' }, { key: 'COMPLETED', label: 'Completed' }, { key: 'ALL', label: 'All' }]} />
      <SpreadsheetGrid exportName="complaints" rows={data ?? []} columns={ticketCols}
        rowClassName={(r) => (r.resolution_breached ? 'bg-red-50/70' : '')} />
    </div>
  )
}

export function NewTicketPage() {
  const nav = useNavigate()
  const { user } = useAuth()
  const { i18n } = useTranslation()
  useRecentPages('Lodge complaint')
  const [meta, setMeta] = useState<any>(null)
  const [form, setForm] = useState({ module: '', subject: '', description: '', complaint_type: 'ISSUE', priority_requested: 'MEDIUM', centre_code: user?.centre?.code ?? 'NRLDC', channel: 'PORTAL', linked_ticket_id: '', comments: '', on_behalf_username: '' })
  const [file, setFile] = useState<File | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.get('/cas/meta').then((r) => setMeta(r.data)) }, [])
  const submit = async () => {
    const fd = new FormData()
    Object.entries(form).forEach(([k, v]) => v !== '' && fd.append(k, String(v)))
    if (file) fd.append('file', file)
    try {
      const { data } = await api.post('/cas/tickets', fd)
      nav(`/cas/${data.id}`)
    } catch (e) { setErr(errMsg(e)) }
  }
  if (!meta) return null
  return (
    <div className="max-w-3xl">
      <PageHeader title="Lodge a complaint" subtitle={`Complainant: ${user?.full_name} · ${user?.email} · ${user?.mobile} (pre-filled from login)`} />
      {err && <div className="mb-3"><Alert kind="error">{err}</Alert></div>}
      <Card>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Module" required>
            <select className={inputCls} value={form.module} onChange={(e) => setForm({ ...form, module: e.target.value })}>
              <option value="">— select —</option>
              {meta.modules.map((m: any) => <option key={m.key} value={m.key} disabled={!m.enabled} className={m.enabled ? '' : 'text-slate-300'}>{i18n.language === 'hi' ? m.name_hi : m.name_en}{m.enabled ? '' : ' (not authorised)'}</option>)}
            </select>
          </Field>
          <Field label="Complaint type"><select className={inputCls} value={form.complaint_type} onChange={(e) => setForm({ ...form, complaint_type: e.target.value })}>{meta.complaint_types.map((c: string) => <option key={c}>{c}</option>)}</select></Field>
          <Field label="Priority"><select className={inputCls} value={form.priority_requested} onChange={(e) => setForm({ ...form, priority_requested: e.target.value })}>{meta.priorities.map((c: string) => <option key={c}>{c}</option>)}</select></Field>
          <Field label="Escalate to establishment"><select className={inputCls} value={form.centre_code} onChange={(e) => setForm({ ...form, centre_code: e.target.value })}>{meta.centres.map((c: string) => <option key={c}>{c}</option>)}</select></Field>
          <Field label="Link earlier complaint"><select className={inputCls} value={form.linked_ticket_id} onChange={(e) => setForm({ ...form, linked_ticket_id: e.target.value })}><option value="">—</option>{meta.my_tickets.map((t: any) => <option key={t.id} value={t.id}>{t.ticket_number} · {t.subject}</option>)}</select></Field>
          {meta.is_staff && (
            <Field label="Channel (helpdesk)"><select className={inputCls} value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}>{['PORTAL', 'EMAIL', 'PHONE', 'WALKIN'].map((c) => <option key={c}>{c}</option>)}</select></Field>
          )}
          {meta.is_staff && form.channel !== 'PORTAL' && (
            <Field label="Complainant username (on behalf)"><input className={inputCls} value={form.on_behalf_username} onChange={(e) => setForm({ ...form, on_behalf_username: e.target.value })} /></Field>
          )}
        </div>
        <div className="mt-3 space-y-3">
          <Field label="Subject" required><input className={inputCls} value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} /></Field>
          <Field label="Details of complaint" required><textarea className={cls(inputCls, 'h-28')} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="Comments"><input className={inputCls} value={form.comments} onChange={(e) => setForm({ ...form, comments: e.target.value })} /></Field>
          <Field label="Attach image / document"><input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <Button onClick={submit} disabled={!form.module || !form.subject}>Submit complaint</Button>
        </div>
      </Card>
    </div>
  )
}

export function TicketDetailPage() {
  const { id } = useParams()
  useRecentPages(`Ticket #${id}`)
  const { data: t, reload, updatedAt } = useAutoRefresh<any>(`/cas/tickets/${id}`)
  const [meta, setMeta] = useState<any>(null)
  const [comment, setComment] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [internal, setInternal] = useState(false)
  const [assess, setAssess] = useState<{ priority?: string; severity?: string; tags?: string; assigned_team?: string }>({})
  const [rating, setRating] = useState(5)
  const [transfer, setTransfer] = useState('')
  const [err, setErr] = useState('')
  const { user } = useAuth()
  useEffect(() => { api.get('/cas/meta').then((r) => setMeta(r.data)) }, [])
  if (!t || !meta) return null
  const owner = t.complainant_user_id === user?.id
  const act = async (action: string, extra: Record<string, any> = {}) => {
    setErr('')
    const fd = new FormData()
    fd.append('action', action)
    fd.append('comment', comment)
    fd.append('internal', String(internal))
    Object.entries(extra).forEach(([k, v]) => fd.append(k, String(v)))
    if (file) fd.append('file', file)
    try { await api.post(`/cas/tickets/${id}/action`, fd); setComment(''); setFile(null); reload() } catch (e) { setErr(errMsg(e)) }
  }
  const doAssess = async () => {
    try {
      await api.post(`/cas/tickets/${id}/assess`, { priority: assess.priority || undefined, severity: assess.severity ? Number(assess.severity) : undefined, tags: assess.tags ? assess.tags.split(',').map((s) => s.trim()) : undefined, assigned_team: assess.assigned_team || undefined })
      reload()
    } catch (e) { setErr(errMsg(e)) }
  }
  return (
    <div className="space-y-4">
      <PageHeader title={<>{t.ticket_number} <Badge>{t.status}</Badge> <Badge color="purple">Level {t.escalation_level}</Badge></>} subtitle={t.subject}
        actions={<><LastUpdated at={updatedAt} /><Button variant="secondary" onClick={() => download('/cas/reports/TICKET', `ticket_${t.id}.pdf`, { ticket_id: t.id, fmt: 'pdf' })}>Ticket report (PDF)</Button></>} />
      {err && <Alert kind="error">{err}</Alert>}
      <Card title="Progress tracker"><CaseFlowchartTracker steps={t.tracker} /></Card>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Complaint details" className="lg:col-span-2">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm md:grid-cols-3">
            {[['Module', t.module], ['Type', t.complaint_type], ['Channel', t.channel], ['Centre', t.centre], ['Priority (requested)', t.priority_requested],
              ['Priority (AMC)', t.priority ?? '—'], ['Severity (RLDC/NLDC)', t.severity ? `S${t.severity}` : '—'], ['Complainant', t.complainant_name],
              ['Contact', t.complainant_contact], ['Response due', fmtDT(t.sla_response_due)], ['Resolution due', fmtDT(t.sla_resolution_due)],
              ['Tags', (t.tags ?? []).join(', ') || '—']].map(([k, v]) => (
              <div key={k as string}><dt className="text-xs text-slate-500">{k}</dt><dd className="font-medium">{v}</dd></div>))}
          </dl>
          <p className="mt-3 whitespace-pre-wrap rounded bg-slate-50 p-3 text-sm">{t.description}</p>
          {(t.response_breached || t.resolution_breached) && <div className="mt-2"><Alert kind="error">SLA breached: response delay {t.response_delay_min} min, resolution delay {t.resolution_delay_min} min.</Alert></div>}
          <h3 className="mt-4 text-sm font-semibold">History & communication</h3>
          <ol className="mt-2 space-y-2 border-l-2 border-grid-100 pl-3">
            {t.history.map((h: any, i: number) => (
              <li key={i} className="text-sm">
                <div><Badge color="blue">{h.event}</Badge> <b>{h.actor_name}</b> <span className="text-xs text-slate-500">{fmtDT(h.created_at)}</span>
                  {h.to_level !== null && h.to_level !== undefined && <span className="text-xs text-slate-500"> · L{h.from_level ?? '-'}→L{h.to_level}</span>}</div>
                {h.comment && <div className="text-slate-700">{h.comment}</div>}
                {h.attachment_doc_id && <button className="text-xs text-grid-600 underline" onClick={() => download(`/documents/${h.attachment_doc_id}/download`, 'attachment')}>📎 attachment</button>}
              </li>
            ))}
          </ol>
        </Card>
        <div className="space-y-4">
          {meta.is_staff && (
            <Card title="Assess (helpdesk / RLDC)">
              <div className="space-y-2">
                <Field label="Priority (AMC)"><select className={inputCls} value={assess.priority ?? ''} onChange={(e) => setAssess({ ...assess, priority: e.target.value })}><option value="" />{['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((p) => <option key={p}>{p}</option>)}</select></Field>
                <Field label="Severity (RLDC/NLDC)" hint="S1 30 min/2 h · S2 2 h/12 h · S3 1 d/2 d · S4 1 d/5 d"><select className={inputCls} value={assess.severity ?? ''} onChange={(e) => setAssess({ ...assess, severity: e.target.value })}><option value="" />{[1, 2, 3, 4].map((p) => <option key={p} value={p}>Severity {p}</option>)}</select></Field>
                <Field label="Tags (comma separated)"><input className={inputCls} value={assess.tags ?? ''} onChange={(e) => setAssess({ ...assess, tags: e.target.value })} /></Field>
                <Field label="Assign team"><input className={inputCls} value={assess.assigned_team ?? ''} onChange={(e) => setAssess({ ...assess, assigned_team: e.target.value })} /></Field>
                <Button onClick={doAssess}>Save assessment</Button>
              </div>
            </Card>
          )}
          <Card title="Actions">
            <div className="space-y-2">
              <textarea aria-label="Comment" placeholder="Comment / reply…" className={cls(inputCls, 'h-20')} value={comment} onChange={(e) => setComment(e.target.value)} />
              <input type="file" aria-label="Attachment" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              {meta.is_staff && <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} /> Internal note (hidden from stakeholder)</label>}
              <div className="flex flex-wrap gap-1.5">
                <Button size="sm" onClick={() => act('COMMENT')}>Comment</Button>
                {meta.is_staff && <Button size="sm" variant="secondary" onClick={() => act('REQUEST_INPUT')}>Ask for inputs</Button>}
                {owner && t.status === 'AWAITING_INPUT' && <Button size="sm" variant="secondary" onClick={() => act('PROVIDE_INPUT')}>Provide inputs</Button>}
                {!['RESOLVED', 'CLOSED'].includes(t.status) && t.escalation_level < 3 && <Button size="sm" variant="warning" onClick={() => act('ESCALATE')}>Escalate</Button>}
                {meta.is_staff && !['RESOLVED', 'CLOSED'].includes(t.status) && <Button size="sm" variant="success" onClick={() => act('RESOLVE')}>Resolve</Button>}
                {!['CLOSED'].includes(t.status) && <Button size="sm" variant="secondary" onClick={() => act('CLOSE')}>Close</Button>}
                {['RESOLVED', 'CLOSED'].includes(t.status) && <Button size="sm" variant="danger" onClick={() => act('REOPEN')}>Re-open</Button>}
              </div>
              <div className="flex items-center gap-1 pt-1">
                <select aria-label="Transfer target" className={cls(inputCls, 'w-32')} value={transfer} onChange={(e) => setTransfer(e.target.value)}><option value="">Transfer to…</option>{meta.centres.map((c: string) => <option key={c}>{c}</option>)}<option value="L2_SUPPORT">L2 support team</option><option value="DBA">DBA</option></select>
                <Button size="sm" variant="secondary" disabled={!transfer} onClick={() => act('TRANSFER', { target: transfer })}>Transfer</Button>
              </div>
              {owner && ['RESOLVED', 'CLOSED'].includes(t.status) && !t.feedback_rating && (
                <div className="flex items-center gap-1 pt-1">
                  <select aria-label="Rating" className={cls(inputCls, 'w-24')} value={rating} onChange={(e) => setRating(Number(e.target.value))}>{[5, 4, 3, 2, 1].map((r) => <option key={r} value={r}>{'★'.repeat(r)}</option>)}</select>
                  <Button size="sm" onClick={() => act('FEEDBACK', { rating })}>Give feedback</Button>
                </div>
              )}
              {t.feedback_rating && <div className="text-sm">Feedback: {'★'.repeat(t.feedback_rating)} {t.feedback_text}</div>}
            </div>
          </Card>
          <Card title="Attachments">
            {t.documents.length === 0 ? <div className="text-xs text-slate-500">None</div> : t.documents.map((d: any) => (
              <button key={d.id} className="block text-left text-xs text-grid-700 underline" onClick={() => download(`/documents/${d.id}/download`, d.auto_filename)}>{d.auto_filename} (v{d.version_no})</button>))}
          </Card>
        </div>
      </div>
    </div>
  )
}

export function CasDashboardsPage() {
  useRecentPages('CAS dashboards')
  const [list, setList] = useState<any[]>([])
  const [key, setKey] = useState('NRLDC_COORD')
  useEffect(() => { api.get('/cas/dashboards').then((r) => setList(r.data)) }, [])
  const { data: d, updatedAt } = useAutoRefresh<any>(`/cas/dashboards/${key}`)
  return (
    <div className="space-y-4">
      <PageHeader title="Complaint dashboards" subtitle="14 role-based dashboards with real-time auto update." actions={
        <><LastUpdated at={updatedAt} /><select aria-label="Dashboard" className={cls(inputCls, 'w-72')} value={key} onChange={(e) => setKey(e.target.value)}>{list.map((x) => <option key={x.key} value={x.key}>{x.title}</option>)}</select></>} />
      {d && (<>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Stat label="Total" value={d.total} /><Stat label="Pending" value={d.open} tone="amber" /><Stat label="Resolved" value={d.resolved} tone="green" />
          <Stat label="Avg resolution (h)" value={d.avg_resolution_hours} /><Stat label="SLA breached" value={d.sla_breached} tone="red" />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="14-day trend"><DynamicChart type="line" data={d.trend} xKey="date" series={['logged', 'resolved']} downloadName="cas_trend" /></Card>
          <Card title="By status"><DynamicChart type="pie" data={objToSeries(d.by_status)} xKey="name" series={['value']} downloadName="cas_status" /></Card>
          <Card title="By module"><DynamicChart type="bar" data={objToSeries(d.by_module)} xKey="name" series={['value']} downloadName="cas_module" /></Card>
          <Card title="By severity & escalation level"><DynamicChart type="bar" data={[...objToSeries(d.by_severity), ...objToSeries(d.by_level)]} xKey="name" series={['value']} downloadName="cas_severity" /></Card>
        </div>
        <Card title="Oldest pending complaints"><SpreadsheetGrid exportName="pending" rows={d.pending} columns={ticketCols} compact /></Card>
      </>)}
    </div>
  )
}

export function CasReportsPage() {
  useRecentPages('CAS reports')
  const [list, setList] = useState<any[]>([])
  const [code, setCode] = useState('CENTRE_NRLDC')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [res, setRes] = useState<any>(null)
  const [amc, setAmc] = useState(3000000)
  const [month, setMonth] = useState(() => { const d = new Date(); return `${d.getFullYear()}-${String(Math.floor(d.getMonth() / 3) * 3 + 1).padStart(2, '0')}` })
  const [pen, setPen] = useState<any>(null)
  useEffect(() => { api.get('/cas/reports').then((r) => setList(r.data.filter((x: any) => x.code !== 'TICKET'))) }, [])
  const params = { from_date: from || undefined, to_date: to || undefined }
  const run = () => api.get(`/cas/reports/${code}`, { params }).then((r) => setRes(r.data))
  const runPen = () => api.get('/cas/sla-penalty-report', { params: { from_month: month, quarterly_amc_value: amc } }).then((r) => setPen(r.data))
  return (
    <div className="space-y-4">
      <PageHeader title="Complaint reports" subtitle="14 pre-defined report templates; bilingual PDF / Excel / CSV." />
      <Card title="Standard reports">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Report"><select className={cls(inputCls, 'w-72')} value={code} onChange={(e) => setCode(e.target.value)}>{list.map((r) => <option key={r.code} value={r.code}>{r.name_en}</option>)}</select></Field>
          <Field label="From"><input type="date" className={inputCls} value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field label="To"><input type="date" className={inputCls} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
          <Button onClick={run}>Preview</Button>
          {['pdf', 'xlsx', 'csv'].map((f) => <Button key={f} variant="secondary" onClick={() => download(`/cas/reports/${code}`, `${code}.${f}`, { ...params, fmt: f })}>{f.toUpperCase()}</Button>)}
        </div>
        {res && <div className="mt-3"><div className="mb-1 text-xs text-slate-500">{res.title} · {res.subtitle}</div>
          <SpreadsheetGrid exportName={code} rows={res.rows} columns={res.columns.map((c: any) => ({ key: c[0], label: c[1], exportValue: (r: any) => (/_at$/.test(c[0]) ? fmtDT(r[c[0]]) : r[c[0]]) }))} compact /></div>}
      </Card>
      <Card title="Quarterly SLA downtime & AMC penalty calculation (submitted with AMC invoice)">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Quarter start month"><input type="month" className={inputCls} value={month} onChange={(e) => setMonth(e.target.value)} /></Field>
          <Field label="Quarterly AMC value (₹)"><input type="number" className={inputCls} value={amc} onChange={(e) => setAmc(Number(e.target.value))} /></Field>
          <Button onClick={runPen}>Calculate</Button>
          <Button variant="secondary" onClick={() => download('/cas/sla-penalty-report', 'sla_penalty.pdf', { from_month: month, quarterly_amc_value: amc, fmt: 'pdf' })}>PDF</Button>
          <Button variant="secondary" onClick={() => download('/cas/sla-penalty-report', 'sla_penalty.xlsx', { from_month: month, quarterly_amc_value: amc, fmt: 'xlsx' })}>Excel</Button>
        </div>
        {pen && (
          <div className="mt-3 space-y-3">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {pen.months.map((m: any) => <Stat key={m.month} label={m.month} value={`${m.availability_pct}%`} tone={m.penalty_pct ? 'red' : 'green'} sub={`Penalty ${m.penalty_pct}% · ₹${m.penalty_amount.toLocaleString('en-IN')}`} />)}
              <Stat label="Net payable" value={`₹${pen.net_payable.toLocaleString('en-IN')}`} sub={`Deduction ₹${pen.total_penalty.toLocaleString('en-IN')}`} />
            </div>
            <SpreadsheetGrid exportName="sla_tickets" rows={pen.tickets} compact columns={[{ key: 'ticket_number', label: 'Ticket' }, { key: 'severity', label: 'Sev' },
              { key: 'allowed_response_min', label: 'Allowed resp (min)' }, { key: 'actual_response_min', label: 'Actual resp (min)' },
              { key: 'allowed_resolution_min', label: 'Allowed resol (min)' }, { key: 'actual_resolution_min', label: 'Actual resol (min)' },
              { key: 'delay_min', label: 'Delay (min)' }, { key: 'breached', label: 'Breached', render: (r: any) => <Badge color={r.breached === 'YES' ? 'red' : 'green'}>{r.breached}</Badge> }]} />
          </div>
        )}
      </Card>
    </div>
  )
}

export function KbPage() {
  useRecentPages('FAQ / Knowledge base')
  const { data, reload } = useAutoRefresh<any[]>('/cas/kb', undefined, { live: false })
  const [meta, setMeta] = useState<any>(null)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ module: 'portal', question_en: '', question_hi: '', answer_en: '', answer_hi: '' })
  const { i18n } = useTranslation()
  useEffect(() => { api.get('/cas/meta').then((r) => setMeta(r.data)) }, [])
  const hi = i18n.language === 'hi'
  return (
    <div>
      <PageHeader title="FAQ / Knowledge base" subtitle="Built from resolved complaints and helpdesk entries." actions={meta?.is_staff && <Button onClick={() => setOpen(true)}>+ Add FAQ</Button>} />
      <div className="space-y-2">
        {(data ?? []).map((a) => (
          <details key={a.id} className="rounded border bg-white p-3">
            <summary className="cursor-pointer font-medium">{(hi && a.question_hi) || a.question_en} <Badge color="slate">{a.module}</Badge> {!a.is_published && <Badge color="amber">DRAFT</Badge>}</summary>
            <p className="mt-2 text-sm text-slate-700">{(hi && a.answer_hi) || a.answer_en}</p>
            {meta?.is_staff && !a.is_published && <Button size="sm" className="mt-2" onClick={() => api.patch(`/cas/kb/${a.id}`, { is_published: true }).then(reload)}>Publish</Button>}
          </details>
        ))}
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="New FAQ">
        <div className="space-y-2">
          {(['module', 'question_en', 'question_hi', 'answer_en', 'answer_hi'] as const).map((k) => (
            <Field key={k} label={k}><input className={inputCls} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></Field>))}
          <Button onClick={() => api.post('/cas/kb', form).then(() => { setOpen(false); reload() })}>Save</Button>
        </div>
      </Modal>
    </div>
  )
}
