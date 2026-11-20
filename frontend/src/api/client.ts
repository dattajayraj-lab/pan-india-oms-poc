import axios, { AxiosError } from 'axios'

export const api = axios.create({ baseURL: '/api/v1' })

let token: string | null = null
try {
  token = sessionStorage.getItem('oms.token')
} catch {
  token = null
}

export function setToken(t: string | null) {
  token = t
  try {
    if (t) sessionStorage.setItem('oms.token', t)
    else sessionStorage.removeItem('oms.token')
  } catch {
    /* ignore */
  }
}
export const getToken = () => token

api.interceptors.request.use((cfg) => {
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

type Listener = () => void
const unauthorizedListeners = new Set<Listener>()
export const onUnauthorized = (fn: Listener) => {
  unauthorizedListeners.add(fn)
  return () => {
    unauthorizedListeners.delete(fn)
  }
}

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401 && token) unauthorizedListeners.forEach((fn) => fn())
    return Promise.reject(err)
  },
)

/** Human-readable message from an API error (structured errors per TS Cl. 2.6(e)). */
export function errMsg(e: unknown): string {
  const ax = e as AxiosError<any>
  const d = ax?.response?.data
  if (d?.errors?.length) return d.errors.map((x: any) => `${x.field}: ${x.message}`).join('; ')
  if (typeof d?.detail === 'string') return d.detail
  if (Array.isArray(d?.detail)) return d.detail.map((x: any) => x.msg).join('; ')
  return ax?.message || 'Request failed'
}

export async function download(path: string, filename: string, params?: Record<string, any>) {
  const res = await api.get(path, { params, responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function wsUrl(channel: string) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws/${encodeURIComponent(channel)}`
}
