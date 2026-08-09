import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from './api'

interface Query<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
}

/** Fetch on mount and whenever a dependency in `path` changes. */
export function useQuery<T>(path: string | null, deps: unknown[] = []): Query<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [nonce, setNonce] = useState(0)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  useEffect(() => {
    if (!path) {
      setData(null)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    api
      .get<T>(path)
      .then((result) => {
        if (alive.current) setData(result)
      })
      .catch((err: unknown) => {
        if (alive.current) setError(err instanceof ApiError ? err.message : String(err))
      })
      .finally(() => {
        if (alive.current) setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, nonce, ...deps])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, error, loading, reload }
}

/** Imperative mutation with pending and error state. */
export function useMutation<TInput, TOutput>(
  fn: (input: TInput) => Promise<TOutput>,
): {
  run: (input: TInput) => Promise<TOutput | null>
  pending: boolean
  error: string | null
  reset: () => void
} {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(
    async (input: TInput) => {
      setPending(true)
      setError(null)
      try {
        return await fn(input)
      } catch (err: unknown) {
        setError(err instanceof ApiError ? err.message : String(err))
        return null
      } finally {
        setPending(false)
      }
    },
    [fn],
  )

  return { run, pending, error, reset: () => setError(null) }
}
