import { useCallback, useEffect, useState } from 'react'
import { graphAPI } from '../services/api'

/**
 * useGraph — fetch + manage the knowledge-graph data.
 *
 * Simplified for Phase 9: threshold is fixed at 0.5 (no slider),
 * rebuild is removed (cache invalidation happens automatically on
 * document upload/delete).
 */
export function useGraph({ enabled = true } = {}) {
  const [data, setData] = useState({ nodes: [], links: [], meta: null })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchGraph = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data: payload } = await graphAPI.getData(0.5, false)
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
  }, [])

  // Initial load + refetch when panel re-enabled.
  useEffect(() => {
    if (enabled) fetchGraph()
  }, [enabled, fetchGraph])

  return {
    data,
    loading,
    error,
    refetch: fetchGraph,
  }
}
