// Module launcher: authorised modules enabled and highlighted, others greyed out (TS Cl. 2.5; FRD UI-08, UI-09).
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { NAV } from '../../nav'
import { useAuth } from '../../store/auth'
import { fmtDT, readRecent, useAutoRefresh, useRecentPages } from '../../store/hooks'
import { LastUpdated, Stat, cls } from '../../components/common/ui'

const DESC: Record<string, string> = {
  cas: 'Lodge, track and escalate complaints with SLA monitoring',
  registration: 'NSWS connectivity, CONN-4 and Fees & Charges registration',
  ftc: 'Five-stage first time charging with departmental consents',
  comm_cert: 'OPGW / FOTE certification through CA and CB annexures',
  realtime: '24×7 control room: shifts, consents and operating codes',
  outage_coord: 'OCC, D-3, D-2 and D-1 shutdown planning',
  availability: 'Monthly outage review, objections and bifurcation',
  protection: 'Tripping events, FIR/DR/EL/TR and PSC tracking',
  alerts: 'Violation SMS / e-mail and flash reports',
  sps: 'Healthiness of System Protection Schemes',
  mis: 'Reports, 300 graphs, NPMC and BI data views',
}
const TINT = ['bg-sky-50 text-sky-700', 'bg-violet-50 text-violet-700', 'bg-amber-50 text-amber-700', 'bg-teal-50 text-teal-700', 'bg-rose-50 text-rose-700',
  'bg-indigo-50 text-indigo-700', 'bg-emerald-50 text-emerald-700', 'bg-orange-50 text-orange-700', 'bg-fuchsia-50 text-fuchsia-700', 'bg-cyan-50 text-cyan-700', 'bg-lime-50 text-lime-700']
const TILE_ICON: Record<string, string> = { freq: '〰', demand: '⚡', tickets: '🎫', cases: '📂', outage: '⛔', codes: '🔑', dsm: '₹', rev: '🔁' }

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

export default function HomePage() {
  const { user, launcher } = useAuth()
  const { t, i18n } = useTranslation()
  useRecentPages(t('common.home'))
  const { data, updatedAt } = useAutoRefresh<any>('/portal/home-stats')
  const hi = i18n.language === 'hi'
  const recent = user ? readRecent(user.username).filter((r) => r.path !== '/').slice(0, 4) : []
  const tone = (k: string, t0: string) => (k === 'outage' ? 'red' : k === 'tickets' ? 'amber' : k === 'codes' ? 'green' : t0) as any
  const enabledCount = launcher.filter((m) => m.enabled).length

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-grid-800 via-grid-900 to-grid-950 px-6 py-7 text-white shadow-lift sm:px-8">
        <svg className="absolute -right-10 -top-10 h-64 w-64 opacity-[0.07]" viewBox="0 0 200 200" aria-hidden>
          <g fill="none" stroke="white" strokeWidth="2">{[0, 1, 2, 3, 4].map((i) => <circle key={i} cx="100" cy="100" r={20 + i * 18} />)}<path d="M10 100h180M100 10v180M30 30l140 140M170 30L30 170" /></g>
        </svg>
        <div className="relative flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-widest text-saffron-400">{user?.centre?.name_en ?? 'Grid-India'}</div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">{hi ? 'नमस्कार' : greeting()}, {user?.full_name}</h1>
            <p className="mt-1.5 max-w-xl text-sm text-grid-200">{t('launcher.subtitle')} You have access to <b className="text-white">{enabledCount}</b> of {launcher.length} modules.</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <LastUpdated at={updatedAt} />
            {recent.length > 0 && (
              <div className="flex flex-wrap justify-end gap-1.5">
                {recent.map((r) => <Link key={r.path} to={r.path} className="rounded-full bg-white/10 px-3 py-1 text-[11px] font-medium text-white ring-1 ring-white/15 hover:bg-white/20">{r.title}</Link>)}
              </div>
            )}
          </div>
        </div>
      </section>

      {data && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          {data.tiles.map((tile: any) => <Stat key={tile.key} label={hi ? tile.label_hi : tile.label_en} value={tile.value} tone={tone(tile.key, tile.tone)} sub={tile.sub} icon={TILE_ICON[tile.key]} />)}
        </div>
      )}

      <section>
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-slate-900">{t('launcher.title')}</h2>
            <p className="text-xs text-slate-500">{fmtDT(new Date()).slice(0, 10)} · NLDC, NRLDC, ERLDC, WRLDC, SRLDC, NERLDC</p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {launcher.map((m, idx) => {
            const nav = NAV.find((n) => n.key === m.key)!
            const inner = (
              <>
                <div className="flex items-start justify-between">
                  <span className={cls('flex h-11 w-11 items-center justify-center rounded-xl text-xl', m.enabled ? TINT[idx % TINT.length] : 'bg-slate-100 grayscale')} aria-hidden>{nav.icon}</span>
                  {m.enabled ? <span className="text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-grid-500">→</span> : <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-400">🔒 {t('launcher.notAuthorised')}</span>}
                </div>
                <div className="mt-4 font-semibold tracking-tight">{hi ? m.name_hi : m.name_en}</div>
                <div className="text-[11px] text-slate-400">{hi ? m.name_en : m.name_hi}</div>
                <p className="mt-2 text-xs leading-relaxed text-slate-500">{DESC[m.key]}</p>
              </>
            )
            return m.enabled ? (
              <Link key={m.key} to={nav.items[0].path} data-testid={`module-${m.key}`} data-enabled="true"
                className="group rounded-xl border border-slate-200/80 bg-white p-5 text-slate-900 shadow-card transition hover:-translate-y-0.5 hover:border-grid-300 hover:shadow-lift">
                {inner}
              </Link>
            ) : (
              <div key={m.key} data-testid={`module-${m.key}`} data-enabled="false" aria-disabled="true"
                className="cursor-not-allowed rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-slate-400 opacity-80">
                {inner}
              </div>
            )
          })}
        </div>
      </section>
    </div>
  )
}
