import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Spinner, Alert } from 'react-bootstrap'
import { useTranslation } from 'react-i18next'
import ForceGraph2D from 'react-force-graph-2d'
import { Maximize2 } from 'lucide-react'
import GraphLegend from './GraphLegend'

/**
 * Neural-network color gradient based on connection count (degree).
 * 0 connections = cool dim blue, many connections = bright warm white/pink.
 * Creates a "brain" aesthetic where hub nodes glow brighter.
 */
const _DEGREE_COLORS = [
  [60, 100, 180],    // 0: dim blue (orphan)
  [70, 140, 220],    // 1: blue
  [90, 180, 240],    // 2: light blue
  [120, 210, 230],   // 3: cyan
  [160, 230, 200],   // 4: teal
  [200, 240, 160],   // 5: yellow-green
  [240, 220, 120],   // 6: warm yellow
  [255, 190, 100],   // 7: orange
  [255, 150, 120],   // 8+: warm pink
]

function _degreeColor(degree) {
  const idx = Math.min(degree, _DEGREE_COLORS.length - 1)
  const [r, g, b] = _DEGREE_COLORS[idx]
  return `rgb(${r}, ${g}, ${b})`
}

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
  const prevNodeIdsRef = useRef(new Set())
  const newNodeTimestamps = useRef({})

  // Track newly added nodes for fade-in animation
  useEffect(() => {
    const currentIds = new Set(data.nodes.map((n) => n.id))
    const now = Date.now()
    for (const id of currentIds) {
      if (!prevNodeIdsRef.current.has(id)) {
        newNodeTimestamps.current[id] = now
      }
    }
    // Clean up old entries
    for (const id of Object.keys(newNodeTimestamps.current)) {
      if (!currentIds.has(id)) delete newNodeTimestamps.current[id]
    }
    prevNodeIdsRef.current = currentIds
  }, [data.nodes])

  // Configure force simulation — spread nodes out more (Obsidian-like)
  useEffect(() => {
    const fg = fgRef.current
    if (!fg) return
    fg.d3Force('link')?.distance(70)
    fg.d3Force('charge')?.strength(-150).distanceMax(300)
  }, [data])

  // Resize canvas to container using ResizeObserver (detects panel resizes too).
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const update = () => {
      const rect = el.getBoundingClientRect()
      setDimensions({ width: rect.width, height: rect.height })
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
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
      const key = node.folder || ''
      if (!(key in map)) {
        map[key] = palette[i % palette.length]
        i += 1
      }
    }
    return map
  }, [data.nodes])

  // Build adjacency map + degree count for hover highlighting and node sizing.
  const { neighborsMap, degreeMap } = useMemo(() => {
    const nMap = {}
    const dMap = {}
    for (const link of data.links) {
      const s = typeof link.source === 'object' ? link.source.id : link.source
      const tgt = typeof link.target === 'object' ? link.target.id : link.target
      nMap[s] = nMap[s] || new Set()
      nMap[tgt] = nMap[tgt] || new Set()
      nMap[s].add(tgt)
      nMap[tgt].add(s)
      dMap[s] = (dMap[s] || 0) + 1
      dMap[tgt] = (dMap[tgt] || 0) + 1
    }
    return { neighborsMap: nMap, degreeMap: dMap }
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

      // Size + color scale with connection count — neural network aesthetic
      const degree = degreeMap[node.id] || 0
      let radius = Math.max(3, 3 + degree * 2)
      const color = _degreeColor(degree)

      // New node fade-in + scale animation (1 second)
      const addedAt = newNodeTimestamps.current[node.id]
      let animAlpha = 1
      if (addedAt) {
        const elapsed = Date.now() - addedAt
        if (elapsed < 1000) {
          const t = elapsed / 1000
          animAlpha = t
          radius *= 0.3 + 0.7 * t
        } else {
          // Animation done — clean up
          delete newNodeTimestamps.current[node.id]
        }
      }

      ctx.globalAlpha = (dimmed ? 0.15 : 1.0) * animAlpha

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

      // Glow effect for hub nodes (degree >= 2) — brain-like aesthetic
      if (degree >= 2) {
        ctx.save()
        ctx.shadowColor = color
        ctx.shadowBlur = 4 + degree * 2
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
        ctx.fillStyle = color
        ctx.fill()
        ctx.restore()
      } else {
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
        ctx.fillStyle = color
        ctx.fill()
      }

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
    [hovered, selected, folderColors, neighborsMap, degreeMap, highlightedSet, searchLower, matchesSearch]
  )

  const nodePointerAreaPaint = useCallback((node, color, ctx) => {
    const degree = degreeMap[node.id] || 0
    const radius = Math.max(6, 3 + degree * 2 + 4)
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
    ctx.fill()
  }, [degreeMap])

  const linkColor = useCallback(
    (link) => {
      const sId = typeof link.source === 'object' ? link.source.id : link.source
      const tId = typeof link.target === 'object' ? link.target.id : link.target
      const isActive =
        (hovered && (sId === hovered.id || tId === hovered.id)) ||
        (selected && (sId === selected.id || tId === selected.id))
      if (isActive) return 'rgba(120, 200, 255, 0.9)'
      return 'rgba(80, 140, 200, 0.2)'
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
