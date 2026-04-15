import { useState, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Network, PanelLeftClose, PanelLeft, MessageSquare } from 'lucide-react'
import { Badge } from 'react-bootstrap'
import { useGraph } from '../hooks/useGraph'
import GraphLeftPanel from './GraphLeftPanel'
import GraphCanvas from './GraphCanvas'
import GraphChatPanel from './GraphChatPanel'
import MarkdownEditorPanel from './MarkdownEditorPanel'
import ResizeHandle from './ResizeHandle'

const SIDEBAR_MIN = 160
const SIDEBAR_MAX = 400
const SIDEBAR_DEFAULT = 240
const CHAT_MIN = 280
const CHAT_MAX = 520
const CHAT_DEFAULT = 380
const SPLIT_MIN_PX = 200 // minimum width for either split pane

/**
 * GraphPage — Obsidian-style split layout for the knowledge graph.
 *
 * All vertical dividers are draggable:
 *   [Sidebar ↔]  [Graph Canvas ↔ Markdown Editor]  [↔ Chat overlay]
 */
export default function GraphPage({ onBack, settings }) {
  const { t } = useTranslation()
  const { data, loading, error } = useGraph({ enabled: true })
  const [selected, setSelected] = useState(null)
  const [highlighted, setHighlighted] = useState([])
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [chatOpen, setChatOpen] = useState(false)

  // Resizable widths
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT)
  const [chatWidth, setChatWidth] = useState(CHAT_DEFAULT)
  // splitRatio: fraction of the split-container width allocated to graph (left)
  const [splitRatio, setSplitRatio] = useState(0.5)
  const splitContainerRef = useRef(null)

  const handleSelectNode = useCallback((node) => {
    setSelected(node)
  }, [])

  const handleCloseEditor = useCallback(() => {
    setSelected(null)
  }, [])

  // ── Sidebar resize ──
  const handleSidebarResize = useCallback((delta) => {
    setSidebarWidth((w) => Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, w + delta)))
  }, [])

  // ── Split resize (graph ↔ editor) ──
  const handleSplitResize = useCallback((delta) => {
    const container = splitContainerRef.current
    if (!container) return
    const totalW = container.offsetWidth
    if (totalW <= 0) return
    setSplitRatio((prev) => {
      const leftPx = prev * totalW + delta
      const clamped = Math.max(SPLIT_MIN_PX, Math.min(totalW - SPLIT_MIN_PX, leftPx))
      return clamped / totalW
    })
  }, [])

  // ── Chat resize (drag left edge) ──
  const handleChatResize = useCallback((delta) => {
    // dragging left edge to the left = wider chat, so negate delta
    setChatWidth((w) => Math.min(CHAT_MAX, Math.max(CHAT_MIN, w - delta)))
  }, [])

  return (
    <div className="graph-page">
      {/* ── Header bar ── */}
      <div className="graph-page-header">
        <div className="graph-page-header-left">
          <button className="graph-page-back-btn" onClick={onBack}>
            <ArrowLeft size={18} />
            <span className="d-none d-md-inline">{t('graph.back', 'Back to Chat')}</span>
          </button>

          <button
            className="graph-page-toggle-btn"
            onClick={() => setSidebarOpen((v) => !v)}
            title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
          >
            {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
          </button>
        </div>

        <div className="graph-page-title">
          <Network size={18} />
          <span>{t('graph.pageTitle', 'Graph View')}</span>
        </div>

        <div className="graph-page-header-right">
          <div className="graph-page-stats">
            {data.meta && (
              <>
                <Badge bg="secondary">
                  {data.meta.total_docs || 0} {t('graph.nodes', 'docs')}
                </Badge>
                <Badge bg="secondary">
                  {data.meta.total_links || 0} {t('graph.links', 'links')}
                </Badge>
              </>
            )}
          </div>

          <button
            className={`graph-page-chat-btn ${chatOpen ? 'active' : ''}`}
            onClick={() => setChatOpen((v) => !v)}
            title={t('graph.aiChatTitle', 'Document AI')}
          >
            <MessageSquare size={18} />
          </button>
        </div>
      </div>

      {/* ── Body: sidebar + split view + chat ── */}
      <div className="graph-page-body">
        {/* File list sidebar */}
        {sidebarOpen && (
          <>
            <GraphLeftPanel
              nodes={data.nodes}
              links={data.links}
              selected={selected}
              onSelectNode={handleSelectNode}
              style={{ width: sidebarWidth, minWidth: sidebarWidth }}
            />
            <ResizeHandle onResize={handleSidebarResize} />
          </>
        )}

        {/* Split: Graph + Editor */}
        <div className="graph-split-container" ref={splitContainerRef}>
          <div
            className="graph-split-left"
            style={selected ? { flex: `0 0 ${splitRatio * 100}%` } : undefined}
          >
            <GraphCanvas
              data={data}
              loading={loading}
              error={error}
              selected={selected}
              highlighted={highlighted}
              onSelectNode={handleSelectNode}
            />
          </div>

          {selected && (
            <>
              <ResizeHandle onResize={handleSplitResize} />
              <div
                className="graph-split-right"
                style={{ flex: `0 0 ${(1 - splitRatio) * 100}%` }}
              >
                <MarkdownEditorPanel
                  selected={selected}
                  onClose={handleCloseEditor}
                />
              </div>
            </>
          )}
        </div>

        {/* Chat overlay */}
        {chatOpen && (
          <div className="graph-chat-overlay" style={{ width: chatWidth }}>
            <ResizeHandle onResize={handleChatResize} />
            <GraphChatPanel
              settings={settings}
              graphNodes={data.nodes}
              onHighlightNodes={setHighlighted}
              onSelectNode={handleSelectNode}
            />
          </div>
        )}
      </div>
    </div>
  )
}
