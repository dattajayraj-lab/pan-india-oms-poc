import { useEffect, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { fmtDT } from '../../store/hooks'

export function cls(...xs: (string | false | null | undefined)[]) {
  return xs.filter(Boolean).join(' ')
}

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'success' | 'warning'
const variants: Record<Variant, string> = {
  primary: 'bg-grid-700 text-white shadow-sm hover:bg-grid-800 focus-visible:ring-grid-400 disabled:bg-slate-300 disabled:shadow-none',
  secondary: 'bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 hover:text-slate-900 disabled:text-slate-400',
  danger: 'bg-red-600 text-white shadow-sm hover:bg-red-700 disabled:bg-slate-300',
  ghost: 'text-grid-700 hover:bg-grid-50',
  success: 'bg-emerald-600 text-white shadow-sm hover:bg-emerald-700 disabled:bg-slate-300',
  warning: 'bg-amber-500 text-white shadow-sm hover:bg-amber-600 disabled:bg-slate-300',
}

export function Button({ variant = 'primary', size = 'md', className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' }) {
  return (
    <button
      {...p}
      className={cls('inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:cursor-not-allowed',
        size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3.5 py-2 text-sm', variants[variant], className)}
    />
  )
}

export function Card({ title, actions, children, className, flush }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; flush?: boolean }) {
  return (
    <section className={cls('rounded-xl border border-slate-200/80 bg-white shadow-card', className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-3">
          <h2 className="text-[13px] font-semibold tracking-tight text-slate-800">{title}</h2>
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        </header>
      )}
      <div className={flush ? '' : 'p-5'}>{children}</div>
    </section>
  )
}

const badgeColors: Record<string, string> = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20', red: 'bg-red-50 text-red-700 ring-red-600/20',
  amber: 'bg-amber-50 text-amber-800 ring-amber-600/25', blue: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  slate: 'bg-slate-100 text-slate-600 ring-slate-500/15', purple: 'bg-violet-50 text-violet-700 ring-violet-600/20',
}
const dotColors: Record<string, string> = { green: 'bg-emerald-500', red: 'bg-red-500', amber: 'bg-amber-500', blue: 'bg-sky-500', slate: 'bg-slate-400', purple: 'bg-violet-500' }
/** Status colour coding used in every module (FRD UI-13). */
export function statusColor(s?: string | null): string {
  const v = (s || '').toUpperCase()
  if (/(APPROVED|ACCEPTED|CLOSED|RESOLVED|PUBLISHED|COMPLIED|IN_SERVICE|^ON$|VERIFIED|CLEAN|DONE|FINAL|ISSUED|COMPLETED|GRANTED|CONSENTED)/.test(v)) return 'green'
  if (/(REJECT|RETURN|TRIPPED|OBJECTED|NOT_COMPLIED|^OFF$|EXPIRED|REVOKED|LOCKED|OVERDUE|INFECTED|DISAPPROVED|BREACH)/.test(v)) return 'red'
  if (/(PENDING|DRAFT|REVIEW|PROCESSING|ESCALATED|PARTIAL|DEGRADED|OUTAGE|SUBMITTED|WAITING|REOPENED|AWAITING|OPEN|REQUESTED)/.test(v)) return 'amber'
  if (/(FORWARD|SHIFTED|ASSIGNED|IN_PROGRESS)/.test(v)) return 'blue'
  return 'slate'
}
export function Badge({ children, color }: { children: ReactNode; color?: string }) {
  const c = color ?? statusColor(String(children))
  return (
    <span className={cls('inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset', badgeColors[c] ?? badgeColors.slate)}>
      <span className={cls('h-1.5 w-1.5 rounded-full', dotColors[c] ?? dotColors.slate)} />
      {typeof children === 'string' ? children.replace(/_/g, ' ') : children}
    </span>
  )
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    if (open) window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
      <div className={cls('mt-12 w-full overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-black/5', wide ? 'max-w-5xl' : 'max-w-lg')}>
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
          <h3 className="font-semibold tracking-tight text-slate-900">{title}</h3>
          <button aria-label="Close" onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600">✕</button>
        </header>
        <div className="max-h-[75vh] overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  )
}

export function Field({ label, children, hint, required }: { label: ReactNode; children: ReactNode; hint?: ReactNode; required?: boolean }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
        {label} {required && <span className="text-red-600">*</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

export const inputCls = 'w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-grid-500 disabled:bg-slate-50 disabled:text-slate-500'

export function Alert({ kind = 'info', children }: { kind?: 'info' | 'error' | 'success' | 'warning'; children: ReactNode }) {
  const c = { info: 'border-sky-500 bg-sky-50 text-sky-900', error: 'border-red-500 bg-red-50 text-red-900', success: 'border-emerald-500 bg-emerald-50 text-emerald-900', warning: 'border-amber-500 bg-amber-50 text-amber-900' }[kind]
  const icon = { info: 'ℹ', error: '⚠', success: '✓', warning: '!' }[kind]
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={cls('flex items-start gap-2.5 rounded-lg border-l-4 px-4 py-3 text-sm shadow-card', c)}>
      <span className="mt-px font-bold" aria-hidden>{icon}</span><div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}

/** Live "Last Updated: DD-MM-YYYY HH:mm:ss" pill (TS Cl. 2.4). */
export function LastUpdated({ at }: { at: Date | null }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">
      <span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" /><span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" /></span>
      {t('common.lastUpdated')}: {at ? fmtDT(at) : '—'}
    </span>
  )
}

const tones = {
  grid: { text: 'text-grid-800', bar: 'bg-grid-500', chip: 'bg-grid-50 text-grid-700' },
  red: { text: 'text-red-700', bar: 'bg-red-500', chip: 'bg-red-50 text-red-600' },
  amber: { text: 'text-amber-700', bar: 'bg-amber-500', chip: 'bg-amber-50 text-amber-700' },
  green: { text: 'text-emerald-700', bar: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-700' },
}
export function Stat({ label, value, tone = 'grid', sub, icon }: { label: ReactNode; value: ReactNode; tone?: 'grid' | 'red' | 'amber' | 'green'; sub?: ReactNode; icon?: ReactNode }) {
  const t = tones[tone] ?? tones.grid
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200/80 bg-white p-4 shadow-card">
      <span className={cls('absolute inset-y-0 left-0 w-1', t.bar)} aria-hidden />
      <div className="flex items-start justify-between gap-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
        {icon && <span className={cls('flex h-7 w-7 items-center justify-center rounded-lg text-sm', t.chip)} aria-hidden>{icon}</span>}
      </div>
      <div className={cls('mt-1.5 text-2xl font-bold tabular-nums tracking-tight', t.text)}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </div>
  )
}

export function PageHeader({ title, subtitle, actions, eyebrow }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-saffron-600">{eyebrow}</div>}
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-500">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{actions}</div>
    </div>
  )
}

export function Tabs({ tabs, active, onChange }: { tabs: { key: string; label: ReactNode; count?: number }[]; active: string; onChange: (k: string) => void }) {
  return (
    <div className="mb-4 flex flex-wrap gap-1 rounded-xl bg-slate-200/60 p-1" role="tablist">
      {tabs.map((t) => (
        <button key={t.key} role="tab" aria-selected={active === t.key} onClick={() => onChange(t.key)}
          className={cls('inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition',
            active === t.key ? 'bg-white text-grid-800 shadow-card' : 'text-slate-600 hover:bg-white/60 hover:text-slate-800')}>
          {t.label}
          {t.count !== undefined && <span className={cls('rounded-full px-1.5 text-[10px] font-semibold', active === t.key ? 'bg-grid-100 text-grid-700' : 'bg-slate-300/60 text-slate-600')}>{t.count}</span>}
        </button>
      ))}
    </div>
  )
}
