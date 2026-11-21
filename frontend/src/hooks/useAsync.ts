import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, errorMessage } from '@/api/client'

/** Loads data on mount / when deps change; exposes reload and local setter for optimistic updates. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [errorCode, setErrorCode] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const requestId = useRef(0)

  // `deps` is the caller's dependency list (like useEffect); the loader closure is re-created on each render.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(loader, deps)

  const reload = useCallback(async () => {
    const id = ++requestId.current
    setLoading(true)
    setError(null)
    setErrorCode(null)
    try {
      const result = await run()
      if (id === requestId.current) setData(result)
    } catch (e) {
      if (id === requestId.current) {
        setError(errorMessage(e))
        setErrorCode(e instanceof ApiError ? e.code : null)
      }
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }, [run])

  useEffect(() => {
    void reload()
  }, [reload])

  return { data, setData, error, errorCode, loading, reload }
}
