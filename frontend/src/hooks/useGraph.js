import { useCallback, useEffect, useRef, useState } from 'react'
import { graphAPI } from '../services/api'

/**
 * useGraph — fetch + manage the knowledge-graph data.
 *
 * Threshold changes debounce for 300ms before refetching so the slider feels
 * responsive without hammering the backend.
 */
export function useGraph({ enabled = true, initialThreshold = 0.5 } = {}) {
  const [data, setData] = useState({ nodes: [], links: [], meta: null })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [threshold, setThreshold] = useState(initialThreshold)
  const debounceRef = useRef(null)

  const fetchGraph = useCallback(
    async (t = threshold, force = false) => {
      setLoading(true)
      setError(null)
      try {
        const { data: payload } = await graphAPI.getData(t, force)
        setData(payload)
      } catch (err) {
        setError(
          err.response?.data?.detail ||
            err.message ||
            'Failed to load knowledge graph'
        )
      } finally {
        setLoading(false)
      }
    },
    [threshold]
  )

  // Initial load + refetch when panel re-enabled.
  useEffect(() => {
    if (enabled) fetchGraph(threshold)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled])

  // Debounced refetch when threshold changes.
  useEffect(() => {
    if (!enabled) return
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => fetchGraph(threshold), 300)
    return () => clearTimeout(debounceRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threshold, enabled])

  const rebuild = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data: payload } = await graphAPI.rebuild(threshold)
      setData(payload)
    } catch (err) {
      setError(err.message || 'Rebuild failed')
    } finally {
      setLoading(false)
    }
  }, [threshold])

  return {
    data,
    loading,
    error,
    threshold,
    setThreshold,
    refetch: fetchGraph,
    rebuild,
  }
}
