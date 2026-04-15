import { useState, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Network, MessageSquare } from 'lucide-react'
import { Badge } from 'react-bootstrap'
import { useGraph } from '../hooks/useGraph'
import GraphCanvas from './GraphCanvas'
import GraphChatPanel from './GraphChatPanel'
import MarkdownEditorPanel from './MarkdownEditorPanel'
import ResizeHandle from './ResizeHandle'

const CHAT_MIN = 280
const CHAT_MAX = 520
const CHAT_DEFAULT = 380
const SPLIT_MIN_PX = 200

/**
 * GraphPage — Obsidian-style split layout for the knowledge graph.
 *
 * Layout:
 *   [Markdown Editor (left)] ↔ [Graph Canvas (right)]
 *   Click a node → editor opens on the left, graph stays on the right.
 *   Chat panel is a floating overlay toggled via header button.
 */
export default function GraphPage({ onBack, settings }) {
  const { t } = useTranslation()
  const { data, loading, error } = useGraph({ enabled: true })
  const [selected, setSelected] = useState(null)
  const [highlighted, setHighlighted] = useState([])
  const [chatOpen, setChatOpen] = useState(false)

  const [chatWidth, setChatWidth] = useState(CHAT_DEFAULT)
  const [splitRatio, setSplitRatio] = useState(0.5)
  const splitContainerRef = useRef(null)

  const handleSelectNode = useCallback((node) => {
    setSelected(node)
  }, [])

  const handleCloseEditor = useCallback(() => {
    setSelected(null)
  }, [])

  // ── Split resize (editor ↔ graph) ──
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

      {/* ── Body: [editor | graph] + chat overlay ── */}
      <div className="graph-page-body">
        <div className="graph-split-container" ref={splitContainerRef}>
          {/* Editor on the LEFT */}
          {selected && (
            <>
              <div
                className="graph-split-left"
                style={{ flex: `0 0 ${splitRatio * 100}%` }}
              >
                <MarkdownEditorPanel
                  selected={selected}
                  onClose={handleCloseEditor}
                />
              </div>
              <ResizeHandle onResize={handleSplitResize} />
            </>
          )}

          {/* Graph on the RIGHT (or full width when no selection) */}
          <div className="graph-split-right" style={selected ? { flex: `0 0 ${(1 - splitRatio) * 100}%` } : { flex: 1, borderLeft: 'none' }}>
            <GraphCanvas
              data={data}
              loading={loading}
              error={error}
              selected={selected}
              highlighted={highlighted}
              onSelectNode={handleSelectNode}
            />
          </div>
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
