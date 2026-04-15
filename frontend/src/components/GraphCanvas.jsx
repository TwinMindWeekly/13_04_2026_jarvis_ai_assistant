import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Spinner, Alert } from 'react-bootstrap'
import { useTranslation } from 'react-i18next'
import ForceGraph2D from 'react-force-graph-2d'
import { Maximize2 } from 'lucide-react'
import GraphLegend from './GraphLegend'

/**
 * GraphCanvas — the central force-directed graph visualization.
 *
 * Receives graph data + selection/highlight state from parent GraphPage.
 * Renders ForceGraph2D with custom node painting, hover highlight, and
 * click-to-select behavior.
 */
export default function GraphCanvas({
  data,
  loading,
  error,
  selected,
  highlighted,
  onSelectNode,
  search,
}) {
  const { t } = useTranslation()
  const fgRef = useRef(null)
  const containerRef = useRef(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })
  const [hovered, setHovered] = useState(null)

  // Resize canvas to container.
  useEffect(() => {
    const update = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        setDimensions({ width: rect.width, height: rect.height })
      }
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  // Center on selected node when it changes.
  useEffect(() => {
    if (selected && fgRef.current) {
      fgRef.current.centerAt(selected.x, selected.y, 500)
    }
  }, [selected])

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

  // Build adjacency map for hover highlighting.
  const neighborsMap = useMemo(() => {
    const map = {}
    for (const link of data.links) {
      const s = typeof link.source === 'object' ? link.source.id : link.source
      const tgt = typeof link.target === 'object' ? link.target.id : link.target
      map[s] = map[s] || new Set()
      map[tgt] = map[tgt] || new Set()
      map[s].add(tgt)
      map[tgt].add(s)
    }
    return map
  }, [data.links])

  const highlightedSet = useMemo(
    () => new Set(highlighted || []),
    [highlighted]
  )

  const searchLower = (search || '').trim().toLowerCase()
  const matchesSearch = useCallback(
    (node) => !searchLower || (node.label || '').toLowerCase().includes(searchLower),
    [searchLower]
  )

  // Node painter.
  const nodeCanvasObject = useCallback(
    (node, ctx, globalScale) => {
      const isHovered = hovered && hovered.id === node.id
      const isNeighborOfHovered = hovered && neighborsMap[hovered.id]?.has(node.id)
      const isSelected = selected && selected.id === node.id
      const isHighlighted = highlightedSet.has(node.id)
      const dimmed = searchLower && !matchesSearch(node)

      const radius = Math.max(3, Math.sqrt(node.chunks_count || 1) * 2)
      const color = folderColors[node.folder || '(root)'] || '#888'

      ctx.globalAlpha = dimmed ? 0.15 : 1.0

      // Ring for AI-highlighted nodes (blue glow).
      if (isHighlighted) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + 5, 0, 2 * Math.PI)
        ctx.strokeStyle = '#38bdf8'
        ctx.lineWidth = 2.5 / globalScale
        ctx.stroke()
      }

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

      // Label — only when zoomed in or currently hovered/selected/highlighted.
      if (globalScale > 1.3 || isHovered || isSelected || isHighlighted) {
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
    [hovered, selected, folderColors, neighborsMap, highlightedSet, searchLower, matchesSearch]
  )

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
      const isActive =
        (hovered && (sId === hovered.id || tId === hovered.id)) ||
        (selected && (sId === selected.id || tId === selected.id))
      if (isActive) return 'rgba(255, 170, 0, 0.85)'
      const opacity = 0.1 + (link.weight || 0.5) * 0.25
      return `rgba(180, 180, 200, ${opacity})`
    },
    [hovered, selected]
  )

  const handleNodeClick = useCallback(
    (node) => onSelectNode(node),
    [onSelectNode]
  )

  const handleBackgroundClick = useCallback(
    () => onSelectNode(null),
    [onSelectNode]
  )

  const handleZoomToFit = useCallback(() => {
    if (fgRef.current) fgRef.current.zoomToFit(400, 60)
  }, [])

  return (
    <div ref={containerRef} className="graph-canvas">
      {loading && (
        <div className="graph-canvas-overlay">
          <Spinner animation="border" variant="light" />
        </div>
      )}
      {error && (
        <Alert variant="danger" className="position-absolute m-3" style={{ top: 0, left: 0, zIndex: 10 }}>
          {error}
        </Alert>
      )}
      {!loading && data.nodes.length === 0 && (
        <div className="graph-canvas-overlay" style={{ color: '#888', fontSize: 16, padding: 24, textAlign: 'center' }}>
          {t('graph.empty', 'Upload at least 2 documents to see the knowledge graph.')}
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
      <button className="graph-fit-btn" onClick={handleZoomToFit} title={t('graph.zoomToFit', 'Fit')}>
        <Maximize2 size={16} />
      </button>
    </div>
  )
}
