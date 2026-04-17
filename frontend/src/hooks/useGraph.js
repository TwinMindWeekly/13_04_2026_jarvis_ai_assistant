import { useCallback, useEffect, useRef, useState } from 'react'
import { graphAPI } from '../services/api'

/**
 * useGraph — fetch + manage the knowledge-graph data.
 *
 * Listens for 'graph:invalidate' events (dispatched after doc create/delete/upload)
 * and auto-refetches with debounce. Supports optimistic updates via patchData().
 * Preserves node positions (x/y/vx/vy) across refetches to avoid layout jumps.
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
      setData((prev) => {
        // Preserve node positions from previous render to avoid layout reset
        if (prev.nodes.length > 0) {
          const prevMap = new Map(prev.nodes.map((n) => [n.id, n]))
          const mergedNodes = payload.nodes.map((n) => {
            const existing = prevMap.get(n.id)
            return existing
              ? { ...n, x: existing.x, y: existing.y, vx: existing.vx, vy: existing.vy }
              : n
          })
          return { ...payload, nodes: mergedNodes }
        }
        return payload
      })
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

  // Listen for 'graph:invalidate' events — debounced auto-refresh
  useEffect(() => {
    if (!enabled) return
    let timer
    const handler = () => {
      clearTimeout(timer)
      timer = setTimeout(() => fetchGraph(), 300)
    }
    window.addEventListener('graph:invalidate', handler)
    return () => {
      window.removeEventListener('graph:invalidate', handler)
      clearTimeout(timer)
    }
  }, [enabled, fetchGraph])

  // Optimistic update — patch data without re-fetching from server
  const patchData = useCallback((patcher) => {
    setData((prev) => (typeof patcher === 'function' ? patcher(prev) : { ...prev, ...patcher }))
  }, [])

  return {
    data,
    loading,
    error,
    refetch: fetchGraph,
    patchData,
  }
}
