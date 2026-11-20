import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api, wsUrl } from '../api/client'
import { useAuth } from './auth'

/**
 * Fetch + auto-refresh at the Admin-configured interval (TS Cl. 2.4: refresh <= 2 s, configurable).
 * Pauses while the tab is hidden to avoid wasted load at 1000 concurrent users.
 */
export function useAutoRefresh<T>(path: string | null, params?: Record<string, any>, opts?: { live?: boolean; intervalMs?: number }) {
  const { refreshMs, activeCentre } = useAuth()
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const key = JSON.stringify(params ?? {})
  const live = opts?.live ?? true
  const interval = opts?.intervalMs ?? refreshMs

  const load = useCallback(async () => {
    if (!path) return
    try {
      const p = { ...(params ?? {}) }
      if (activeCentre && activeCentre !== 'ALL' && p.centre === undefined) p.centre = activeCentre
      const res = await api.get(path, { params: p })
      setData(res.data)
      setError(null)
      setUpdatedAt(new Date())
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e.message)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, key, activeCentre])

  useEffect(() => {
    load()
    if (!live) return
    const id = setInterval(() => {
      if (!document.hidden) load()
    }, Math.max(interval, 500))
    return () => clearInterval(id)
  }, [load, live, interval])

  return { data, error, updatedAt, reload: load, setData }
}

/** Subscribe to WebSocket push events for a channel (centre code or user:{id}). */
export function useLiveChannel(channel: string | null, onEvent: (ev: any) => void) {
  const cb = useRef(onEvent)
  cb.current = onEvent
  useEffect(() => {
    if (!channel || typeof WebSocket === 'undefined') return
    let ws: WebSocket | null = null
    let stop = false
    let retry: ReturnType<typeof setTimeout>
    const open = () => {
      ws = new WebSocket(wsUrl(channel))
      ws.onmessage = (m) => {
        try {
          cb.current(JSON.parse(m.data))
        } catch {
          /* ignore */
        }
      }
      ws.onclose = () => {
        if (!stop) retry = setTimeout(open, 3000)
      }
    }
    open()
    return () => {
      stop = true
      clearTimeout(retry)
      ws?.close()
    }
  }, [channel])
}

/** Track the last 5 visited pages per login (TS Cl. 11.4.4 p.134; FRD UI-12). */
export function useRecentPages(title: string) {
  const { user } = useAuth()
  const loc = useLocation()
  useEffect(() => {
    if (!user || !title) return
    const k = `oms.recent.${user.username}`
    try {
      const list: { path: string; title: string }[] = JSON.parse(localStorage.getItem(k) || '[]')
      const next = [{ path: loc.pathname + loc.search, title }, ...list.filter((x) => x.path !== loc.pathname + loc.search)].slice(0, 5)
      localStorage.setItem(k, JSON.stringify(next))
      window.dispatchEvent(new Event('oms-recent'))
    } catch {
      /* storage unavailable */
    }
  }, [user, title, loc.pathname, loc.search])
}

export function readRecent(username: string): { path: string; title: string }[] {
  try {
    return JSON.parse(localStorage.getItem(`oms.recent.${username}`) || '[]')
  } catch {
    return []
  }
}

export function fmtDT(v?: string | Date | null) {
  if (!v) return ''
  const d = typeof v === 'string' ? new Date(v.endsWith('Z') || v.includes('+') ? v : v + 'Z') : v
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getDate())}-${p(d.getMonth() + 1)}-${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
