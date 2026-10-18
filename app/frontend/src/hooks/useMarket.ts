'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/market-api'
const cache = new Map<string, { value: unknown; timestamp: number }>()
export function useMarket<T>(path: string | null, interval = 0) {
  const activePath = useRef(path)
  activePath.current = path
  const requestSequence = useRef(0)
  const [data, setData] = useState<T | undefined>(() =>
    path ? (cache.get(path)?.value as T | undefined) : undefined
  )
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(Boolean(path && !cache.has(path)))
  const [updated, setUpdated] = useState<number | undefined>(() =>
    path ? cache.get(path)?.timestamp : undefined
  )
  const reload = useCallback(async () => {
    if (!path) return
    const sequence = ++requestSequence.current
    setError('')
    try {
      const result = await api<T>(path)
      const timestamp = Date.now()
      cache.set(path, { value: result, timestamp })
      if (activePath.current === path && sequence === requestSequence.current) {
        setData(result)
        setUpdated(timestamp)
      }
    } catch (e) {
      if (activePath.current === path && sequence === requestSequence.current)
        setError(
          e instanceof Error
            ? e.message
            : 'Could not connect to the market service.'
        )
    } finally {
      if (activePath.current === path && sequence === requestSequence.current)
        setLoading(false)
    }
  }, [path])
  useEffect(() => {
    if (!path) {
      setData(undefined)
      return
    }
    setData(cache.get(path)?.value as T | undefined)
    setUpdated(cache.get(path)?.timestamp)
    setLoading(!cache.has(path))
    void reload()
    // Background reads stop after ten minutes; Reload starts a fresh window.
    const started = Date.now()
    const timer = interval
      ? setInterval(() => {
          if (Date.now() - started < 600000 && !document.hidden) void reload()
        }, interval)
      : undefined
    // A review decision changes counts on other panels; let them re-read.
    const refresh = () => void reload()
    window.addEventListener('market:refresh', refresh)
    return () => {
      clearInterval(timer)
      window.removeEventListener('market:refresh', refresh)
    }
  }, [path, interval, reload])
  return { data, error, loading, updated, reload }
}
