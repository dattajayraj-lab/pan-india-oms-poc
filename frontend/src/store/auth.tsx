import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, getToken, onUnauthorized, setToken } from '../api/client'

export type ModuleKey =
  | 'cas' | 'registration' | 'ftc' | 'comm_cert' | 'realtime' | 'outage_coord'
  | 'availability' | 'protection' | 'alerts' | 'sps' | 'mis'

export interface User {
  id: number
  username: string
  full_name: string
  email: string
  mobile: string
  user_category: string
  department: string
  centre: { id: number; code: string; name_en: string; name_hi: string } | null
  entity_id: number | null
  roles: string[]
  is_admin: boolean
  is_external: boolean
  sees_all_centres: boolean
  modules: Record<ModuleKey, number>
  has_signature: boolean
}
export interface LauncherItem { key: ModuleKey; name_en: string; name_hi: string; icon: string; enabled: boolean }
export interface Flags { must_change_password: boolean; contact_verification_due: boolean; password_expired: boolean }

interface AuthState {
  user: User | null
  launcher: LauncherItem[]
  flags: Flags
  refreshMs: number
  activeCentre: string
  setActiveCentre: (c: string) => void
  loading: boolean
  completeLogin: (token: string) => Promise<void>
  reload: () => Promise<void>
  logout: () => Promise<void>
  can: (m: ModuleKey, level?: 1 | 2 | 3 | 4) => boolean
  hasRole: (...codes: string[]) => boolean
}

const Ctx = createContext<AuthState | null>(null)
const noFlags: Flags = { must_change_password: false, contact_verification_due: false, password_expired: false }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [launcher, setLauncher] = useState<LauncherItem[]>([])
  const [flags, setFlags] = useState<Flags>(noFlags)
  const [refreshMs, setRefreshMs] = useState(2000)
  const [activeCentre, setActiveCentre] = useState('ALL')
  const [loading, setLoading] = useState(!!getToken())

  const reload = useCallback(async () => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    try {
      const { data } = await api.get('/auth/me')
      setUser(data.user)
      setLauncher(data.launcher)
      setFlags({ must_change_password: data.must_change_password, contact_verification_due: data.contact_verification_due, password_expired: data.password_expired })
      setRefreshMs(data.settings?.refresh_interval_ms ?? 2000)
      setActiveCentre((prev) => (prev !== 'ALL' ? prev : data.user.sees_all_centres ? 'ALL' : data.user.centre?.code ?? 'ALL'))
    } catch {
      setToken(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    reload()
    return onUnauthorized(() => {
      setToken(null)
      setUser(null)
    })
  }, [reload])

  const completeLogin = useCallback(async (t: string) => {
    setToken(t)
    setLoading(true)
    await reload()
  }, [reload])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      /* already ended */
    }
    setToken(null)
    setUser(null)
  }, [])

  const can = useCallback((m: ModuleKey, level: 1 | 2 | 3 | 4 = 1) => (user?.modules?.[m] ?? 0) >= level, [user])
  const hasRole = useCallback((...codes: string[]) => !!user && (user.is_admin || codes.some((c) => user.roles.includes(c))), [user])

  const value = useMemo(
    () => ({ user, launcher, flags, refreshMs, activeCentre, setActiveCentre, loading, completeLogin, reload, logout, can, hasRole }),
    [user, launcher, flags, refreshMs, activeCentre, loading, completeLogin, reload, logout, can, hasRole],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth outside AuthProvider')
  return v
}
