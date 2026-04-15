import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Modal, Spinner, Alert } from 'react-bootstrap'
import { useTranslation } from 'react-i18next'
import ForceGraph2D from 'react-force-graph-2d'
import { useGraph } from '../hooks/useGraph'
import GraphToolbar from './GraphToolbar'
import GraphDetailPanel from './GraphDetailPanel'
import GraphLegend from './GraphLegend'

/**
 * GraphPanel — Obsidian-style knowledge graph view for uploaded documents.
 *
 * Performance notes:
 *  - Canvas 2D renderer via react-force-graph-2d (D3-force simulation)
 *  - cooldownTicks=120 freezes physics after ~2s so the view stops jittering
 *  - Click/hover handlers are refs to avoid re-rendering the graph component
 */
export default function GraphPanel({ isOpen, onClose }) {
  const { t } = useTranslation()
  const fgRef = useRef(null)
  const containerRef = useRef(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })
  const [selected, setSelected] = useState(null)
  const [hovered, setHovered] = useState(null)
  const [search, setSearch] = useState('')

  const { data, loading, error, threshold, setThreshold, rebuild } = useGraph({
    enabled: isOpen,
  })

  // Resize canvas to container.
  useEffect(() => {
    if (!isOpen) return
    const update = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        setDimensions({ width: rect.width, height: rect.height })
      }
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [isOpen])

  // Distinct folders → stable color palette.
  const folderColors = useMemo(() => {
    const palette = [
      '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
      '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
    ]
    const map = {}
    let i = 0
    for (const node of data.nodes) {
      const key = node.folder || '(root)'
      if (!(key in map)) {
        map[key] = palette[i % palette.length]
        i += 1
      }
    }
    return map
  }, [data.nodes])

  // Build adjacency map for hover highlighting + neighbor list.
  const neighborsMap = useMemo(() => {
    const map = {}
    for (const link of data.links) {
      const s = typeof link.source === 'object' ? link.source.id : link.source
      const t = typeof link.target === 'object' ? link.target.id : link.target
      map[s] = map[s] || new Set()
      map[t] = map[t] || new Set()
      map[s].add(t)
      map[t].add(s)
    }
    return map
  }, [data.links])

  const searchLower = search.trim().toLowerCase()
  const matchesSearch = useCallback(
    (node) => !searchLower || (node.label || '').toLowerCase().includes(searchLower),
    [searchLower]
  )

  // Node painter — circle + label (only when zoomed in or hovered).
  const nodeCanvasObject = useCallback(
    (node, ctx, globalScale) => {
      const isHovered = hovered && hovered.id === node.id
      const isNeighborOfHovered =
        hovered && neighborsMap[hovered.id]?.has(node.id)
      const isSelected = selected && selected.id === node.id
      const dimmed = searchLower && !matchesSearch(node)

      const radius = Math.max(3, Math.sqrt(node.chunks_count || 1) * 2)
      const color = folderColors[node.folder || '(root)'] || '#888'

      ctx.globalAlpha = dimmed ? 0.15 : 1.0

      // Ring for selected.
      if (isSelected) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + 4, 0, 2 * Math.PI)
        ctx.strokeStyle = '#ffd700'
        ctx.lineWidth = 2 / globalScale
        ctx.stroke()
      }

      // Ring for hovered or neighbor-of-hovered.
      if (isHovered || isNeighborOfHovered) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + 2, 0, 2 * Math.PI)
        ctx.strokeStyle = '#ffaa00'
        ctx.lineWidth = 1.5 / globalScale
        ctx.stroke()
      }

      ctx.beginPath()
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()

      // Label — only when zoomed in or currently hovered/selected.
      if (globalScale > 1.3 || isHovered || isSelected) {
        const label = node.label || node.id
        const fontSize = Math.max(10, 12 / globalScale)
        ctx.font = `${fontSize}px Inter, system-ui, sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillStyle = '#ffffff'
        ctx.fillText(label, node.x, node.y + radius + 2)
      }

      ctx.globalAlpha = 1.0
    },
    [hovered, selected, folderColors, neighborsMap, searchLower, matchesSearch]
  )

  // Larger hit area than the visible node so dense clusters stay clickable.
  const nodePointerAreaPaint = useCallback((node, color, ctx) => {
    const radius = Math.max(6, Math.sqrt(node.chunks_count || 1) * 2 + 4)
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
    ctx.fill()
  }, [])

  const linkColor = useCallback(
    (link) => {
      const sId = typeof link.source === 'object' ? link.source.id : link.source
      const tId = typeof link.target === 'object' ? link.target.id : link.target
      const highlighted =
        (hovered && (sId === hovered.id || tId === hovered.id)) ||
        (selected && (sId === selected.id || tId === selected.id))
      if (highlighted) return 'rgba(255, 170, 0, 0.85)'
      // Weight-based opacity.
      const opacity = 0.1 + (link.weight || 0.5) * 0.25
      return `rgba(180, 180, 200, ${opacity})`
    },
    [hovered, selected]
  )

  const handleNodeClick = useCallback((node) => {
    setSelected(node)
    if (fgRef.current) {
      // Center on clicked node without zooming in aggressively.
      fgRef.current.centerAt(node.x, node.y, 500)
    }
  }, [])

  const handleBackgroundClick = useCallback(() => setSelected(null), [])

  const handleZoomToFit = useCallback(() => {
    if (fgRef.current) {
      fgRef.current.zoomToFit(400, 60)
    }
  }, [])

  const neighborsOfSelected = useMemo(() => {
    if (!selected) return []
    const ids = neighborsMap[selected.id]
    if (!ids) return []
    const nodesById = Object.fromEntries(data.nodes.map((n) => [n.id, n]))
    const linksByPair = {}
    for (const link of data.links) {
      const s = typeof link.source === 'object' ? link.source.id : link.source
      const t = typeof link.target === 'object' ? link.target.id : link.target
      linksByPair[`${s}|${t}`] = link.weight
      linksByPair[`${t}|${s}`] = link.weight
    }
    return [...ids]
      .map((nid) => ({
        node: nodesById[nid],
        weight: linksByPair[`${selected.id}|${nid}`] || 0,
      }))
      .filter((x) => x.node)
      .sort((a, b) => b.weight - a.weight)
  }, [selected, neighborsMap, data.nodes, data.links])

  return (
    <Modal show={isOpen} onHide={onClose} fullscreen>
      <Modal.Header closeButton>
        <Modal.Title>{t('graph.title', 'Knowledge Graph')}</Modal.Title>
      </Modal.Header>
      <Modal.Body className="p-0" style={{ overflow: 'hidden' }}>
        <div
          style={{ display: 'flex', flexDirection: 'column', height: '100%' }}
        >
          <GraphToolbar
            threshold={threshold}
            onThresholdChange={setThreshold}
            search={search}
            onSearchChange={setSearch}
            onZoomToFit={handleZoomToFit}
            onRebuild={rebuild}
            stats={data.meta}
          />
          <div style={{ position: 'relative', flex: 1, display: 'flex' }}>
            <div
              ref={containerRef}
              style={{
                flex: 1,
                position: 'relative',
                background: '#0f1014',
                overflow: 'hidden',
              }}
            >
              {loading && (
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 10,
                  }}
                >
                  <Spinner animation="border" variant="light" />
                </div>
              )}
              {error && (
                <Alert
                  variant="danger"
                  className="position-absolute m-3"
                  style={{ top: 0, left: 0, zIndex: 10 }}
                >
                  {error}
                </Alert>
              )}
              {!loading && data.nodes.length === 0 && (
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#888',
                    fontSize: 16,
                    padding: 24,
                    textAlign: 'center',
                  }}
                >
                  {t(
                    'graph.empty',
                    'Upload at least 2 documents to see the knowledge graph.'
                  )}
                </div>
              )}
              <ForceGraph2D
                ref={fgRef}
                graphData={data}
                width={dimensions.width}
                height={dimensions.height}
                backgroundColor="#0f1014"
                nodeCanvasObject={nodeCanvasObject}
                nodePointerAreaPaint={nodePointerAreaPaint}
                linkColor={linkColor}
                linkWidth={(link) => 0.5 + (link.weight || 0.5) * 2}
                onNodeClick={handleNodeClick}
                onNodeHover={setHovered}
                onBackgroundClick={handleBackgroundClick}
                cooldownTicks={120}
                d3VelocityDecay={0.3}
                warmupTicks={40}
                enableNodeDrag
                enableZoomInteraction
                enablePanInteraction
              />
              <GraphLegend folderColors={folderColors} />
            </div>
            {selected && (
              <GraphDetailPanel
                node={selected}
                neighbors={neighborsOfSelected}
                onClose={() => setSelected(null)}
                onSelectNeighbor={handleNodeClick}
              />
            )}
          </div>
        </div>
      </Modal.Body>
    </Modal>
  )
}
