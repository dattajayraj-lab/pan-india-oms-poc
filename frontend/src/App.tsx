import { Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import { useAuth, type ModuleKey } from './store/auth'
import LoginPage from './pages/public/LoginPage'
import HomePage from './pages/portal/HomePage'
import ProfilePage from './pages/portal/ProfilePage'
import { AuditPage, SessionsPage, SettingsPage, UsersPage } from './pages/admin/AdminPages'
import { MODULE_ROUTES, PUBLIC_ROUTES, ADMIN_ROUTES } from './routes'

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading, flags } = useAuth()
  const loc = useLocation()
  if (loading) return <div className="p-10 text-center text-slate-500">Loading…</div>
  if (!user) return <Navigate to={loc.pathname === '/' ? '/welcome' : '/login'} state={{ from: loc.pathname }} replace />
  if (flags.must_change_password && loc.pathname !== '/profile') return <Navigate to="/profile?force=1" replace />
  return <>{children}</>
}

function RequireModule({ module, children }: { module: ModuleKey; children: ReactNode }) {
  const { can } = useAuth()
  if (!can(module)) {
    return (
      <div className="mx-auto mt-16 max-w-md rounded-lg border border-red-200 bg-red-50 p-6 text-center">
        <div className="text-3xl">🔒</div>
        <h1 className="mt-2 font-semibold text-red-800">Authorisation revoked / not granted</h1>
        <p className="text-sm text-red-700">Your login is not authorised for this module. Contact the module Admin.</p>
      </div>
    )
  }
  return <>{children}</>
}

function NotFound() {
  return <div className="mt-16 text-center text-slate-500"><div className="text-4xl">404</div>Page not found</div>
}

export default function App() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-slate-500">Loading…</div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        {PUBLIC_ROUTES.map((r) => <Route key={r.path} path={r.path} element={r.element} />)}
        <Route element={<RequireAuth><AppShell /></RequireAuth>}>
          <Route path="/" element={<HomePage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/admin/users" element={<UsersPage />} />
          <Route path="/admin/sessions" element={<SessionsPage />} />
          <Route path="/admin/settings" element={<SettingsPage />} />
          <Route path="/admin/audit" element={<AuditPage />} />
          {ADMIN_ROUTES.map((r) => <Route key={r.path} path={r.path} element={r.element} />)}
          {MODULE_ROUTES.map((r) => <Route key={r.path} path={r.path} element={<RequireModule module={r.module}>{r.element}</RequireModule>} />)}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

