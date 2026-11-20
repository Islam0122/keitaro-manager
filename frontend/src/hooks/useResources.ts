import { useCallback, useEffect, useState } from 'react'

import { resourcesApi } from '@/api'
import { ApiError, errorMessage } from '@/api/client'
import type { Domain, Group, Offer, TrafficSource } from '@/types/api'

export interface Resources {
  domains: Domain[]
  groups: Group[]
  sources: TrafficSource[]
  offers: Offer[]
}

let cache: Resources | null = null

/** Loads Keitaro dictionaries once per session (shared between pages); `refresh` forces a reload. */
export function useResources() {
  const [data, setData] = useState<Resources | null>(cache)
  const [error, setError] = useState<string | null>(null)
  const [errorCode, setErrorCode] = useState<string | null>(null)
  const [loading, setLoading] = useState(!cache)

  const load = useCallback(async (force = false) => {
    if (cache && !force) {
      setData(cache)
      return
    }
    setLoading(true)
    setError(null)
    setErrorCode(null)
    try {
      const [domains, groups, sources, offers] = await Promise.all([
        resourcesApi.domains(),
        resourcesApi.groups(),
        resourcesApi.sources(),
        resourcesApi.offers(),
      ])
      cache = { domains, groups, sources, offers }
      setData(cache)
    } catch (e) {
      setError(errorMessage(e))
      setErrorCode(e instanceof ApiError ? e.code : null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return { data, error, errorCode, loading, refresh: () => load(true) }
}

export function invalidateResources() {
  cache = null
}
