import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Network, MessageSquare, X } from 'lucide-react'
import { Badge } from 'react-bootstrap'
import { useGraph } from '../hooks/useGraph'
import { useAgent } from '../hooks/useAgent'
import { useVoice } from '../hooks/useVoice'
import { resolveWikilinkTargets } from '../utils/wikilinkDetector'
import GraphCanvas from './GraphCanvas'
import ChatArea from './ChatArea'
import MarkdownEditorPanel from './MarkdownEditorPanel'
import ResizeHandle from './ResizeHandle'

const CHAT_MIN = 320
const CHAT_MAX = 640
const CHAT_DEFAULT = 420
const SPLIT_MIN_PX = 200

/**
 * GraphPage — Obsidian-style split layout for the knowledge graph.
 *
 * Layout:
 *   [Markdown Editor (left)] ↔ [Graph Canvas (right)]
 *   Click a node → editor opens on the left, graph stays on the right.
 *   Chat panel is a floating overlay on the right edge.
 */
export default function GraphPage({ onBack, settings, externalSelectedDoc, onExternalDocConsumed }) {
  const { t } = useTranslation()
  const { data, loading, error, refetch, patchData } = useGraph({ enabled: true })
  const [selected, setSelected] = useState(null)
  const [highlighted, setHighlighted] = useState([])
  const [chatOpen, setChatOpen] = useState(false)

  const [chatWidth, setChatWidth] = useState(CHAT_DEFAULT)
  const [splitRatio, setSplitRatio] = useState(0.5)
  const splitContainerRef = useRef(null)

  // Dedicated agent instance for the graph chat (independent conversation).
  const graphAgent = useAgent(settings.provider, settings.model, settings.language)

  const [graphVoiceEnabled, setGraphVoiceEnabled] = useState(settings.voiceEnabled !== false)
  const voiceLang = settings.language === 'vi' ? 'vi-VN' : 'en-US'
  const voice = useVoice({ language: voiceLang, enabled: graphVoiceEnabled })

  const handleToggleGraphVoice = useCallback(() => {
    setGraphVoiceEnabled((prev) => {
      if (prev) voice.stopSpeaking()
      return !prev
    })
  }, [voice])

  const speakingCharIndex = graphVoiceEnabled && voice.isSpeaking ? voice.speakingCharIndex : -1

  // TTS: auto-speak new assistant messages
  const lastSpokenCount = useRef(0)
  useEffect(() => {
    if (!graphVoiceEnabled) return
    const msgs = graphAgent.messages
    if (msgs.length === 0 || msgs.length <= lastSpokenCount.current) return
    const last = msgs[msgs.length - 1]
    if (last.role === 'assistant' && last.content) {
      voice.speak(last.content, '')
    }
    lastSpokenCount.current = msgs.length
  }, [graphAgent.messages.length]) // eslint-disable-line react-hooks/exhaustive-deps

  // Handle external document selection (from Sidebar file create/click while in graph view)
  useEffect(() => {
    if (!externalSelectedDoc) return
    const graphNode = data.nodes.find((n) => n.id === externalSelectedDoc.id)
    if (graphNode) {
      setSelected(graphNode)
    } else {
      // Doc just created — graph doesn't have it yet, create minimal node representation
      setSelected({
        id: externalSelectedDoc.id,
        label: (externalSelectedDoc.filename || '').replace(/\.md$/, ''),
        folder: externalSelectedDoc.folder_path || '',
      })
      // Trigger graph refresh to pick up the new doc
      refetch()
    }
    onExternalDocConsumed?.()
  }, [externalSelectedDoc]) // eslint-disable-line react-hooks/exhaustive-deps

  // Real-time wikilink detection — optimistically update graph edges
  const handleWikilinksChange = useCallback((docId, targets) => {
    if (!docId || !data.nodes.length) return
    const resolvedIds = resolveWikilinkTargets(targets, data.nodes)
    patchData((prev) => {
      const otherLinks = prev.links.filter((link) => {
        const srcId = typeof link.source === 'object' ? link.source.id : link.source
        return srcId !== docId
      })
      const newLinks = resolvedIds
        .filter((tid) => tid !== docId)
        .map((tid) => ({ source: docId, target: tid, weight: 1.0, context: '' }))
      return { ...prev, links: [...otherLinks, ...newLinks] }
    })
  }, [data.nodes, patchData])

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

  // ── Highlight graph nodes mentioned by the AI ──
  const findMentionedNodes = useCallback(
    (text) => {
      if (!text || !data.nodes?.length) return []
      const lower = text.toLowerCase()
      return data.nodes.filter((n) => {
        const name = (n.label || '').toLowerCase()
        // Also strip .md extension so "[[foo]]" matches filename "foo.md"
        const stem = name.replace(/\.[a-z0-9]+$/, '')
        return (
          (name.length > 2 && lower.includes(name)) ||
          (stem.length > 2 && lower.includes(stem))
        )
      })
    },
    [data.nodes]
  )

  // Watch the latest assistant message and highlight matching nodes.
  useEffect(() => {
    if (graphAgent.messages.length === 0) {
      setHighlighted([])
      return
    }
    const last = graphAgent.messages[graphAgent.messages.length - 1]
    if (last.role === 'assistant' && last.content) {
      const matched = findMentionedNodes(last.content)
      setHighlighted(matched.map((n) => n.id))
    }
  }, [graphAgent.messages, findMentionedNodes])

  // Suggestion chips (Vietnamese-friendly; i18n keys available).
  const suggestionChips = useMemo(
    () => [
      {
        label: t('graph.suggestFind', 'Find notes related to...'),
        prompt: t('graph.suggestFindPrompt', 'Find notes related to ',),
      },
      {
        label: t('graph.suggestSummarize', 'Summarize my notes about...'),
        prompt: t('graph.suggestSummarizePrompt', 'Summarize my notes about '),
      },
      {
        label: t('graph.suggestListAll', 'List all my documents'),
        prompt: t('graph.suggestListAllPrompt', 'List all my documents with a short description of each.'),
      },
      {
        label: t('graph.suggestCompare', 'Compare notes on...'),
        prompt: t('graph.suggestComparePrompt', 'Compare notes on '),
      },
    ],
    [t]
  )

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
                  onWikilinksChange={handleWikilinksChange}
                />
              </div>
              <ResizeHandle onResize={handleSplitResize} />
            </>
          )}

          {/* Graph on the RIGHT (or full width when no selection) */}
          <div
            className="graph-split-right"
            style={selected ? { flex: `0 0 ${(1 - splitRatio) * 100}%` } : { flex: 1, borderLeft: 'none' }}
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
        </div>

        {/* Chat overlay — unified ChatArea */}
        {chatOpen && (
          <div className="graph-chat-overlay" style={{ width: chatWidth }}>
            <ResizeHandle onResize={handleChatResize} />
            <div className="graph-chat-overlay-inner">
              <div className="graph-chat-overlay-header">
                <MessageSquare size={16} />
                <span>{t('graph.aiChatTitle', 'Document AI')}</span>
                <button
                  className="graph-chat-close-btn"
                  onClick={() => setChatOpen(false)}
                  title="Close"
                >
                  <X size={16} />
                </button>
              </div>
              <ChatArea
                messages={graphAgent.messages}
                actions={graphAgent.actions}
                isLoading={graphAgent.isLoading}
                streamingText={graphAgent.streamingText}
                error={graphAgent.error}
                onSendMessage={graphAgent.sendMessage}
                onClear={graphAgent.clearMessages}
                voice={voice}
                voiceEnabled={graphVoiceEnabled}
                onToggleVoice={handleToggleGraphVoice}
                speakingCharIndex={speakingCharIndex}
                suggestionChips={suggestionChips}
                emptyTitle={t('graph.chatEmptyTitle', 'Explore your knowledge')}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
