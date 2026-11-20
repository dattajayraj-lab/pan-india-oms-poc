// MIS & Reporting: template-driven report builder, 300-graph explorer, generation outage & ENS, BI views (TS Cl. 11.4.10, 11.2(e), 2.7).
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, download, errMsg } from '../../api/client'
import { useAuth } from '../../store/auth'
import { useAutoRefresh, useRecentPages } from '../../store/hooks'
import SpreadsheetGrid from '../../components/common/SpreadsheetGrid'
import DynamicChart from '../../components/charts/DynamicChart'
import { Alert, Badge, Button, Card, Field, PageHeader, Tabs, cls, inputCls } from '../../components/common/ui'

const fmtCols = (cols: any[]) => cols.map((c: any) => ({ key: c[0], label: c[2] ? `${c[2]} / ${c[1]}` : c[1] }))

export function ReportBuilderPage() {
  useRecentPages('MIS report builder')
  const { i18n } = useTranslation()
  const { data: tpls, reload } = useAutoRefresh<any[]>('/mis/templates', undefined, { live: false })
  const { data: meta } = useAutoRefresh<any>('/mis/meta', undefined, { live: false })
  const [code, setCode] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [res, setRes] = useState<any>(null)
  const [cfg, setCfg] = useState<any>({ source: 'codes', group_by: ['centre'], field: 'count', fn: 'sum' })
  const [nt, setNt] = useState({ code: '', name_en: '', name_hi: '', emails: '' })
  const [msg, setMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const hi = i18n.language === 'hi'
  const qc = () => ({ source: cfg.source, group_by: cfg.group_by, aggregates: [{ field: cfg.field, fn: cfg.fn }] })
  const preview = async () => setRes((await api.get(`/mis/reports/${code}`, { params: { from_date: from || undefined, to_date: to || undefined } })).data)
  const params = { from_date: from || undefined, to_date: to || undefined }
  return (
    <div className="space-y-4">
      <PageHeader title="MIS report builder" subtitle="Standard and ad-hoc reports from one non-hard-coded engine; web preview → bilingual PDF / Excel / CSV (Hindi before English); e-mail & schedule." />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <Card title="Run a report">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Template"><select className={cls(inputCls, 'w-96')} value={code} onChange={(e) => { setCode(e.target.value); setRes(null) }}><option value="">— select —</option>{tpls?.map((t) => <option key={t.code} value={t.code}>[{t.module}] {hi ? t.name_hi || t.name_en : t.name_en}{t.is_standard ? '' : ' (custom)'}</option>)}</select></Field>
          <Field label="From"><input type="date" className={inputCls} value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field label="To"><input type="date" className={inputCls} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
          <Button disabled={!code} onClick={preview}>Preview</Button>
          {['pdf', 'xlsx', 'csv'].map((f) => <Button key={f} variant="secondary" disabled={!code} onClick={() => download(`/mis/reports/${code}`, `${code}.${f}`, { ...params, fmt: f })}>{f.toUpperCase()}</Button>)}
          <Button variant="ghost" disabled={!code} onClick={async () => { const r = prompt('E-mail recipients (comma separated)'); if (r) { await api.post(`/mis/reports/${code}/email`, { recipients: r.split(',').map((s) => s.trim()) }); setMsg({ kind: 'success', text: 'Report e-mailed' }) } }}>E-mail</Button>
        </div>
        {res && <div className="mt-3 space-y-2">
          {res.rows.length > 0 && res.columns.length >= 2 && typeof res.rows[0][res.columns[res.columns.length - 1][0]] === 'number' && (
            <DynamicChart type="bar" height={220} data={res.rows.slice(0, 40)} xKey={res.columns[0][0]} series={[res.columns[res.columns.length - 1][0]]} downloadName={code} />)}
          <SpreadsheetGrid exportName={code} rows={res.rows} columns={fmtCols(res.columns)} />
        </div>}
      </Card>
      <Card title="Ad-hoc report (no code): pick data source, group-by and aggregate">
        {meta && <div className="grid gap-2 md:grid-cols-5">
          <Field label="Data source"><select className={inputCls} value={cfg.source} onChange={(e) => setCfg({ ...cfg, source: e.target.value, group_by: [meta.datasets[e.target.value].group_by[0]], field: 'count' })}>{Object.keys(meta.datasets).map((d) => <option key={d}>{d}</option>)}</select></Field>
          <Field label="Group by (multi)"><select multiple className={cls(inputCls, 'h-24')} value={cfg.group_by} onChange={(e) => setCfg({ ...cfg, group_by: Array.from(e.target.selectedOptions).map((o) => o.value) })}>{meta.datasets[cfg.source].group_by.map((g: string) => <option key={g}>{g}</option>)}</select></Field>
          <Field label="Measure"><select className={inputCls} value={cfg.field} onChange={(e) => setCfg({ ...cfg, field: e.target.value })}>{meta.datasets[cfg.source].numeric.map((n: string) => <option key={n}>{n}</option>)}</select></Field>
          <Field label="Function"><select className={inputCls} value={cfg.fn} onChange={(e) => setCfg({ ...cfg, fn: e.target.value })}>{meta.functions.map((f: string) => <option key={f}>{f}</option>)}</select></Field>
          <div className="flex items-end"><Button onClick={async () => setRes({ ...(await api.post('/mis/run', { query_config: qc(), from_date: from || undefined, to_date: to || undefined })).data })}>Run</Button></div>
        </div>}
        <div className="mt-3 grid gap-2 md:grid-cols-5">
          <input aria-label="Template code" placeholder="TEMPLATE_CODE" className={inputCls} value={nt.code} onChange={(e) => setNt({ ...nt, code: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '_') })} />
          <input aria-label="Name EN" placeholder="Report name (EN)" className={inputCls} value={nt.name_en} onChange={(e) => setNt({ ...nt, name_en: e.target.value })} />
          <input aria-label="Name HI" placeholder="रिपोर्ट नाम (हिं)" className={inputCls} value={nt.name_hi} onChange={(e) => setNt({ ...nt, name_hi: e.target.value })} />
          <input aria-label="Schedule e-mails" placeholder="Daily e-mail to (optional)" className={inputCls} value={nt.emails} onChange={(e) => setNt({ ...nt, emails: e.target.value })} />
          <Button variant="success" onClick={async () => { try { await api.post('/mis/templates', { code: nt.code, name_en: nt.name_en, name_hi: nt.name_hi, module: 'mis', query_config: qc(), schedule_cron: nt.emails ? '0 9 * * *' : '', distribution_emails: nt.emails ? nt.emails.split(',').map((s) => s.trim()) : [] }); setMsg({ kind: 'success', text: `Template ${nt.code} saved` }); reload() } catch (e) { setMsg({ kind: 'error', text: errMsg(e) }) } }}>Save as template</Button>
        </div>
      </Card>
    </div>
  )
}

function ChartTile({ c, centre }: { c: any; centre: string }) {
  const { i18n } = useTranslation()
  const { data } = useAutoRefresh<any>(`/mis/charts/${c.code}/data`, { centre }, { intervalMs: 15000 })
  return (
    <Card title={<span className="text-xs">{c.code} · {i18n.language === 'hi' ? c.title_hi : c.title_en}</span>}>
      {data ? (data.data.length ? <DynamicChart type={data.type} height={200} data={data.data.slice(0, 30)} xKey={data.x} series={data.series.slice(0, 8)} downloadName={c.code} /> : <div className="py-8 text-center text-xs text-slate-400">No data yet</div>) : null}
    </Card>
  )
}

export function GraphExplorerPage() {
  useRecentPages('Graph explorer')
  const { activeCentre } = useAuth()
  const [module, setModule] = useState('realtime')
  const [page, setPage] = useState(0)
  const { data } = useAutoRefresh<any[]>('/mis/charts', { module }, { live: false })
  const list = data ?? []
  return (
    <div className="space-y-3">
      <PageHeader title="Graph explorer" subtitle="30 initial interactive graphs per module (300 total), auto-refreshing, with PNG/CSV download; sidebar navigation by module." />
      <Tabs active={module} onChange={(m) => { setModule(m); setPage(0) }} tabs={['registration', 'ftc', 'comm_cert', 'realtime', 'availability', 'protection', 'outage_coord', 'alerts', 'sps', 'mis'].map((m) => ({ key: m, label: m, count: 30 }))} />
      <div className="flex items-center gap-2 text-xs">{[0, 1, 2, 3, 4].map((p) => <button key={p} className={cls('rounded px-2 py-1', page === p ? 'bg-grid-700 text-white' : 'bg-white')} onClick={() => setPage(p)}>Graphs {p * 6 + 1}–{p * 6 + 6}</button>)}</div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{list.slice(page * 6, page * 6 + 6).map((c) => <ChartTile key={c.code} c={c} centre={activeCentre} />)}</div>
    </div>
  )
}

export function GenerationOutagePage() {
  useRecentPages('Generation outage & ENS')
  const [view, setView] = useState('GEN_OUTAGE_UNIT')
  const { data } = useAutoRefresh<any>(`/mis/reports/${view}`, undefined, { intervalMs: 30000 })
  const { data: npmc } = useAutoRefresh<any>('/mis/reports/NPMC_DAILY', undefined, { intervalMs: 30000 })
  const key = data?.columns?.[0]?.[0]
  return (
    <div className="space-y-3">
      <PageHeader title="Generation outage duration & Energy Not Served" subtitle="Unit / plant / ownership / fuel / location-wise; ENS split by state entitlement; NPMC daily template." actions={<><Button variant="secondary" onClick={() => download(`/mis/reports/${view}`, `${view}.xlsx`, { fmt: 'xlsx' })}>Excel</Button><Button variant="secondary" onClick={() => download('/mis/reports/NPMC_DAILY', 'NPMC_daily.xlsx', { fmt: 'xlsx' })}>NPMC daily (Excel)</Button></>} />
      <Tabs active={view} onChange={setView} tabs={['UNIT', 'PLANT', 'OWNER', 'FUEL', 'LOCATION'].map((k) => ({ key: `GEN_OUTAGE_${k}`, label: k }))} />
      {data && <><Card><DynamicChart type="bar" height={220} data={data.rows} xKey={key} series={['outage_hours', 'ens_mwh']} downloadName={view} /></Card>
        <SpreadsheetGrid exportName={view} rows={data.rows} columns={fmtCols(data.columns)} /></>}
      {npmc && <Card title={<>NPMC: units under outage <Badge color="amber">{npmc.rows.length}</Badge></>}><SpreadsheetGrid exportName="npmc" rows={npmc.rows} columns={fmtCols(npmc.columns)} compact /></Card>}
    </div>
  )
}

export function BiViewsPage() {
  useRecentPages('BI views')
  const [views, setViews] = useState<any[]>([])
  const [sel, setSel] = useState('bi_outage_codes')
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.get('/mis/bi-views').then((r) => setViews(r.data)) }, [])
  useEffect(() => { api.get(`/mis/bi-views/${sel}`).then((r) => setData(r.data)) }, [sel])
  return (
    <div className="space-y-3">
      <PageHeader title="Power BI / Tableau data views" subtitle="Read-only SQL views on the OMS database for Grid-India's existing BI licences (5 dashboards each)." actions={<><Button variant="secondary" onClick={() => download(`/mis/bi-views/${sel}`, `${sel}.csv`, { fmt: 'csv' })}>CSV</Button><a className="text-sm text-grid-700 underline" href="/graphql" target="_blank" rel="noreferrer">GraphQL explorer</a></>} />
      <Tabs active={sel} onChange={setSel} tabs={views.map((v) => ({ key: v.name, label: v.name }))} />
      <pre className="overflow-x-auto rounded bg-slate-900 p-2 text-[11px] text-emerald-200">{views.find((v) => v.name === sel)?.sql}</pre>
      {data && <SpreadsheetGrid exportName={sel} rows={data.rows} columns={data.columns.map((c: string) => ({ key: c, label: c }))} compact />}
    </div>
  )
}
