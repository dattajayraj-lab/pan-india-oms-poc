import { useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../../api/client'
import { setLanguage } from '../../i18n'
import { ADMIN_NAV, NAV } from '../../nav'
import { useAuth } from '../../store/auth'
import { fmtDT, readRecent, useLiveChannel } from '../../store/hooks'
import { Button, Modal, cls } from '../common/ui'
import ContactReviewModal from './ContactReviewModal'

const CENTRES = ['ALL', 'NLDC', 'NRLDC', 'ERLDC', 'WRLDC', 'SRLDC', 'NERLDC']

function Logo({ compact }: { compact?: boolean }) {
  const { t } = useTranslation()
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-saffron-400 to-saffron-600 shadow-lg shadow-saffron-500/20">
        <svg viewBox="0 0 24 24" className="h-5 w-5 fill-white" aria-hidden><path d="M13.5 2 5 13.5h6L9.5 22 19 9.5h-6z" /></svg>
      </span>
      {!compact && (
        <span className="leading-tight">
          <span className="block text-[15px] font-bold tracking-tight text-white">{t('app.short')}</span>
          <span className="block text-[10px] font-medium uppercase tracking-wider text-grid-300">Operations Management</span>
        </span>
      )}
    </Link>
  )
}

export default function AppShell() {
  const { user, launcher, activeCentre, flags } = useAuth()
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const loc = useLocation()
  useEffect(() => setOpen(false), [loc.pathname])
  if (!user) return null
  const hi = i18n.language === 'hi'
  const enabled = new Set(launcher.filter((m) => m.enabled).map((m) => m.key))

  return (
    <div className="flex min-h-screen bg-slate-100">
      {open && <div className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden" onClick={() => setOpen(false)} />}
      <aside aria-label="Sidebar" className={cls('fixed inset-y-0 left-0 z-40 flex flex-col bg-grid-950 transition-all lg:sticky lg:top-0 lg:h-screen lg:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full', collapsed ? 'w-[72px]' : 'w-72')}>
        <div className={cls('flex h-16 items-center border-b border-white/5', collapsed ? 'justify-center px-2' : 'justify-between px-4')}>
          <Logo compact={collapsed} />
          {!collapsed && <button className="hidden rounded-md p-1 text-grid-300 hover:bg-white/5 hover:text-white lg:block" aria-label="Collapse sidebar" onClick={() => setCollapsed(true)}>«</button>}
        </div>
        {collapsed && <button className="mx-auto mt-2 hidden rounded-md p-1 text-grid-300 hover:bg-white/5 hover:text-white lg:block" aria-label="Expand sidebar" onClick={() => setCollapsed(false)}>»</button>}
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4 text-sm [scrollbar-width:thin]">
          <SideLink to="/" icon="🏠" label={t('common.home')} collapsed={collapsed} end />
          {!collapsed && <div className="px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-widest text-grid-400">{t('nav.launcher')}</div>}
          {NAV.map((m) => {
            const active = loc.pathname.startsWith(m.base)
            const ok = enabled.has(m.key)
            return (
              <div key={m.key}>
                {ok ? (
                  <SideLink to={m.items[0].path} icon={m.icon} label={t(`modules.${m.key}`)} collapsed={collapsed} forceActive={active} />
                ) : (
                  <div className={cls('flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-grid-400/50', collapsed && 'justify-center')} title={t('launcher.notAuthorised')}>
                    <span aria-hidden className="grayscale">{m.icon}</span>{!collapsed && <span className="truncate">{t(`modules.${m.key}`)}</span>}
                    {!collapsed && <span className="ml-auto text-[10px]">🔒</span>}
                  </div>
                )}
                {ok && active && !collapsed && (
                  <div className="mb-1 ml-5 mt-0.5 space-y-0.5 border-l border-white/10 pl-3">
                    {m.items.filter((i) => !(i.internalOnly && user.is_external)).map((i) => (
                      <NavLink key={i.path} to={i.path} end className={({ isActive }) => cls('block rounded-md px-2.5 py-1.5 text-[13px] transition',
                        isActive ? 'bg-white/10 font-medium text-white' : 'text-grid-300 hover:bg-white/5 hover:text-white')}>
                        {hi ? i.hi : i.en}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
          {user.is_admin && (
            <>
              {!collapsed && <div className="px-3 pb-1 pt-5 text-[10px] font-semibold uppercase tracking-widest text-grid-400">{t('nav.admin')}</div>}
              {ADMIN_NAV.map((i) => <SideLink key={i.path} to={i.path} icon="⚙️" label={hi ? i.hi : i.en} collapsed={collapsed} />)}
            </>
          )}
        </nav>
        {!collapsed && (
          <div className="border-t border-white/5 p-4 text-[11px] leading-relaxed text-grid-400">
            <div className="font-medium text-grid-200">Grid Controller of India Ltd</div>
            POC · GEM/2026/B/8083674
          </div>
        )}
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setOpen((o) => !o)} />
        <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-5 lg:px-8 lg:py-6">
          <Breadcrumbs />
          <Outlet />
        </main>
        <footer className="border-t border-slate-200 bg-white/60 px-6 py-3 text-center text-[11px] text-slate-500">
          © Grid Controller of India Ltd · Pan-Grid-India OMS proof of concept · {activeCentre === 'ALL' ? t('common.allCentres') : activeCentre}
        </footer>
      </div>
      {flags.contact_verification_due && <ContactReviewModal />}
    </div>
  )
}

function SideLink({ to, icon, label, collapsed, end, forceActive }: { to: string; icon: string; label: string; collapsed: boolean; end?: boolean; forceActive?: boolean }) {
  return (
    <NavLink to={to} end={end} title={label} className={({ isActive }) => cls('group relative flex items-center gap-3 rounded-lg px-3 py-2 transition',
      collapsed && 'justify-center',
      isActive || forceActive ? 'bg-grid-700 text-white shadow-inner' : 'text-grid-200 hover:bg-white/5 hover:text-white')}>
      {({ isActive }) => (
        <>
          {(isActive || forceActive) && <span className="absolute left-0 top-1.5 h-6 w-1 rounded-r bg-saffron-500" aria-hidden />}
          <span aria-hidden className="text-base">{icon}</span>
          {!collapsed && <span className="truncate text-[13px] font-medium">{label}</span>}
        </>
      )}
    </NavLink>
  )
}

function Topbar({ onMenu }: { onMenu: () => void }) {
  const { user, activeCentre, setActiveCentre, logout } = useAuth()
  const { t, i18n } = useTranslation()
  const nav = useNavigate()
  const [notif, setNotif] = useState<{ unread: number; items: any[] }>({ unread: 0, items: [] })
  const [panel, setPanel] = useState<'' | 'notif' | 'recent' | 'profile'>('')
  const [sessionsOpen, setSessionsOpen] = useState(false)
  const [recent, setRecent] = useState(() => readRecent(user!.username))

  const loadNotif = () => api.get('/auth/notifications').then((r) => setNotif(r.data)).catch(() => undefined)
  useEffect(() => {
    loadNotif()
    const id = setInterval(loadNotif, 15000)
    const h = () => setRecent(readRecent(user!.username))
    window.addEventListener('oms-recent', h)
    return () => { clearInterval(id); window.removeEventListener('oms-recent', h) }
  }, [user])
  useLiveChannel(user ? `user:${user.id}` : null, () => loadNotif())
  const iconBtn = 'relative flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700'

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:px-8">
      <button className={cls(iconBtn, 'lg:hidden')} onClick={onMenu} aria-label="Toggle menu">☰</button>
      <div className="hidden min-w-0 md:block">
        <div className="truncate text-sm font-semibold text-slate-800">{t('app.title')}</div>
        <div className="truncate text-[11px] text-slate-500">{user!.centre?.name_en ?? 'Grid-India'} · {user!.roles.slice(0, 2).map((r) => r.replace(/_/g, ' ').toLowerCase()).join(', ')}</div>
      </div>
      <div className="ml-auto flex items-center gap-1.5">
        <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-1">
          <label className="sr-only" htmlFor="centre-switch">{t('common.centre')}</label>
          <span className="pl-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">{t('common.centre')}</span>
          <select id="centre-switch" value={activeCentre} onChange={(e) => setActiveCentre(e.target.value)} disabled={!user!.sees_all_centres}
            className="rounded-md border-0 bg-white py-1 pl-2 pr-7 text-xs font-semibold text-grid-800 shadow-sm ring-1 ring-slate-200 disabled:opacity-80">
            {CENTRES.filter((c) => user!.sees_all_centres || c === user!.centre?.code).map((c) => <option key={c} value={c}>{c === 'ALL' ? t('common.allCentres') : c}</option>)}
          </select>
        </div>
        <button className="rounded-lg px-2.5 py-1.5 text-xs font-semibold text-grid-700 ring-1 ring-slate-200 hover:bg-grid-50" onClick={() => setLanguage(i18n.language === 'hi' ? 'en' : 'hi')} aria-label={t('common.language')}>
          {i18n.language === 'hi' ? 'EN' : 'हिं'}
        </button>
        <div className="relative">
          <button className={iconBtn} aria-label={t('common.recent')} onClick={() => setPanel(panel === 'recent' ? '' : 'recent')}>🕘</button>
          {panel === 'recent' && (
            <Dropdown onClose={() => setPanel('')} title={t('common.recent')}>
              {recent.length === 0 && <div className="p-2 text-xs text-slate-500">—</div>}
              {recent.map((r) => <button key={r.path} onClick={() => { setPanel(''); nav(r.path) }} className="block w-full truncate rounded-md px-2.5 py-2 text-left text-xs text-slate-700 hover:bg-slate-100">{r.title}</button>)}
            </Dropdown>
          )}
        </div>
        <div className="relative">
          <button className={iconBtn} aria-label={t('common.notifications')} onClick={() => setPanel(panel === 'notif' ? '' : 'notif')}>
            🔔{notif.unread > 0 && <span className="absolute right-0.5 top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-saffron-500 px-1 text-[9px] font-bold text-white ring-2 ring-white">{notif.unread > 99 ? '99+' : notif.unread}</span>}
          </button>
          {panel === 'notif' && (
            <Dropdown onClose={() => setPanel('')} title={t('common.notifications')} wide
              action={<button className="text-[11px] font-medium text-grid-600 hover:underline" onClick={() => api.post('/auth/notifications/read-all').then(loadNotif)}>Mark all read</button>}>
              {notif.items.length === 0 && <div className="p-3 text-center text-xs text-slate-500">You're all caught up</div>}
              {notif.items.map((n) => (
                <button key={n.id} onClick={() => { setPanel(''); if (n.link) nav(n.link) }} className={cls('flex w-full gap-2 rounded-md px-2.5 py-2 text-left hover:bg-slate-50', !n.is_read && 'bg-grid-50/70')}>
                  <span className={cls('mt-1.5 h-2 w-2 shrink-0 rounded-full', n.is_read ? 'bg-slate-300' : 'bg-saffron-500')} />
                  <span className="min-w-0"><span className="block text-xs font-medium text-slate-800">{n.subject}</span><span className="block text-[10px] text-slate-500">{n.module} · {fmtDT(n.created_at)}</span></span>
                </button>
              ))}
            </Dropdown>
          )}
        </div>
        <div className="relative ml-1">
          <button className="flex items-center gap-2 rounded-lg py-1 pl-1 pr-2 hover:bg-slate-100" onClick={() => setPanel(panel === 'profile' ? '' : 'profile')} aria-label={t('common.profile')}>
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-grid-600 to-grid-800 text-xs font-bold text-white">{user!.full_name.split(' ').map((w) => w[0]).slice(0, 2).join('')}</span>
            <span className="hidden max-w-[11rem] truncate text-left text-xs font-semibold text-slate-700 xl:block">{user!.full_name}</span>
            <span className="hidden text-slate-400 xl:block">▾</span>
          </button>
          {panel === 'profile' && (
            <Dropdown onClose={() => setPanel('')} title={user!.username}>
              <div className="px-2.5 pb-2 text-[11px] text-slate-500">{user!.roles.join(', ')}<br />{user!.centre?.code}</div>
              <button className="block w-full rounded-md px-2.5 py-2 text-left text-xs text-slate-700 hover:bg-slate-100" onClick={() => { setPanel(''); nav('/profile') }}>{t('common.profile')} / {t('auth.changePassword')}</button>
              <button className="block w-full rounded-md px-2.5 py-2 text-left text-xs text-slate-700 hover:bg-slate-100" onClick={() => { setPanel(''); setSessionsOpen(true) }}>{t('common.sessions')}</button>
              <button className="block w-full rounded-md px-2.5 py-2 text-left text-xs font-medium text-red-600 hover:bg-red-50" onClick={() => logout().then(() => nav('/login'))}>{t('common.logout')}</button>
            </Dropdown>
          )}
        </div>
      </div>
      <SessionsModal open={sessionsOpen} onClose={() => setSessionsOpen(false)} />
    </header>
  )
}

function Dropdown({ children, onClose, title, wide, action }: { children: ReactNode; onClose: () => void; title: string; wide?: boolean; action?: ReactNode }) {
  useEffect(() => {
    const h = (e: MouseEvent) => !(e.target as HTMLElement).closest('[data-dropdown]') && onClose()
    setTimeout(() => window.addEventListener('click', h))
    return () => window.removeEventListener('click', h)
  }, [onClose])
  return (
    <div data-dropdown className={cls('absolute right-0 mt-2 max-h-[28rem] overflow-y-auto rounded-xl bg-white p-1.5 text-slate-800 shadow-lift ring-1 ring-slate-200', wide ? 'w-80' : 'w-60')}>
      <div className="flex items-center justify-between px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-400">{title}{action}</div>
      {children}
    </div>
  )
}

/** All present login sessions are visible to the user; others can be logged out (Table 1 note). */
function SessionsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const [rows, setRows] = useState<any[]>([])
  const load = () => api.get('/auth/sessions').then((r) => setRows(r.data))
  useEffect(() => { if (open) load() }, [open])
  return (
    <Modal open={open} onClose={onClose} title={t('common.sessions')}>
      <ul className="space-y-2 text-sm">
        {rows.map((s) => (
          <li key={s.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-3">
            <div>
              <div className="font-medium">{s.ip_address || 'local'} {s.current && <span className="text-xs text-emerald-600">(this session)</span>}</div>
              <div className="text-xs text-slate-500">{s.user_agent?.slice(0, 60)}</div>
              <div className="text-xs text-slate-500">Since {fmtDT(s.created_at)} · last seen {fmtDT(s.last_seen_at)}</div>
            </div>
            {!s.current && <Button size="sm" variant="danger" onClick={() => api.delete(`/auth/sessions/${s.id}`).then(load)}>{t('common.logout')}</Button>}
          </li>
        ))}
      </ul>
    </Modal>
  )
}

function Breadcrumbs() {
  const loc = useLocation()
  const { t } = useTranslation()
  const parts = loc.pathname.split('/').filter(Boolean)
  if (!parts.length) return null
  const label = (p: string) => decodeURIComponent(p).replace(/-/g, ' ')
  return (
    <nav aria-label="Breadcrumb" className="mb-3 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
      <Link to="/" className="hover:text-grid-600">{t('common.home')}</Link>
      {parts.map((p, i) => (
        <span key={i} className="flex items-center gap-1.5">
          <span className="text-slate-300">/</span>
          {i === parts.length - 1 ? <span className="font-medium capitalize text-slate-700">{label(p)}</span> : <Link className="capitalize hover:text-grid-600" to={'/' + parts.slice(0, i + 1).join('/')}>{label(p)}</Link>}
        </span>
      ))}
    </nav>
  )
}
