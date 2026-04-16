import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  FileText, Eye, Pencil, Save, Loader2, AlertCircle, X,
} from 'lucide-react'
import { vaultAPI } from '../services/api'
import { extractWikilinkTargets } from '../utils/wikilinkDetector'

/**
 * Convert [[WikiLink]] and [[Target|Display]] to placeholder HTML spans.
 * Uses a zero-width-joiner trick so ReactMarkdown passes them through as text,
 * then we render them as styled pills in a custom text component.
 */
const WIKILINK_SPLIT_RE = /(?<!!)\[\[([^|\]]+?)(?:\|([^\]]+?))?\]\]/g

function renderContentWithWikilinks(md) {
  if (!md) return null
  // Split markdown at wikilinks, render parts as markdown + wikilinks as pills
  const parts = []
  let lastIndex = 0
  WIKILINK_SPLIT_RE.lastIndex = 0
  let match
  while ((match = WIKILINK_SPLIT_RE.exec(md)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'md', text: md.slice(lastIndex, match.index) })
    }
    parts.push({ type: 'wikilink', target: match[1].trim(), display: (match[2] || match[1]).trim() })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < md.length) {
    parts.push({ type: 'md', text: md.slice(lastIndex) })
  }
  return parts
}

/**
 * Highlight [[wikilinks]] in edit mode by escaping HTML, then wrapping
 * matches in <span class="md-wikilink-edit">. Used as innerHTML for the
 * transparent overlay behind the textarea.
 */
function highlightWikilinks(text) {
  if (!text) return ''
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped.replace(
    /(?:!?)(\[\[[^\]]+?\]\])/g,
    '<span class="md-wikilink-edit">$1</span>'
  ) + '\n' // trailing newline keeps overlay height in sync
}

/**
 * MarkdownEditorPanel — Obsidian-style Markdown viewer/editor.
 *
 * Modes:
 *  - "view": Rendered markdown (react-markdown + remark-gfm)
 *  - "edit": Monospace textarea for raw markdown editing
 *
 * Loads vault .md content when `selected` node changes.
 */
export default function MarkdownEditorPanel({ selected, onClose, refreshKey, onWikilinksChange }) {
  const { t } = useTranslation()
  const [mode, setMode] = useState('view')
  const [content, setContent] = useState('')
  const [savedContent, setSavedContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const textareaRef = useRef(null)
  const overlayRef = useRef(null)

  const handleEditorScroll = useCallback((e) => {
    if (overlayRef.current) {
      overlayRef.current.scrollTop = e.target.scrollTop
      overlayRef.current.scrollLeft = e.target.scrollLeft
    }
  }, [])

  const hasChanges = content !== savedContent

  // Load vault content when selected node changes.
  useEffect(() => {
    if (!selected) {
      setContent('')
      setSavedContent('')
      setError(null)
      setMode('view')
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    setMode('view')

    vaultAPI
      .get(selected.id)
      .then(({ data }) => {
        if (cancelled) return
        setContent(data.content || '')
        setSavedContent(data.content || '')
      })
      .catch((err) => {
        if (cancelled) return
        const detail = err.response?.data?.detail || err.message
        setError(detail)
        setContent('')
        setSavedContent('')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [selected, refreshKey])

  // Focus textarea when switching to edit mode.
  useEffect(() => {
    if (mode === 'edit' && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [mode])

  const prevWikilinksRef = useRef([])

  const handleSave = useCallback(async () => {
    if (!selected || !hasChanges || saving) return
    setSaving(true)
    try {
      await vaultAPI.save(selected.id, content)
      setSavedContent(content)
      // Only update graph if wikilinks actually changed
      const newTargets = extractWikilinkTargets(content)
      const prevTargets = prevWikilinksRef.current
      const changed = newTargets.length !== prevTargets.length ||
        newTargets.some((t, i) => t !== prevTargets[i])
      prevWikilinksRef.current = newTargets
      if (changed) {
        if (onWikilinksChange) onWikilinksChange(selected.id, newTargets)
        window.dispatchEvent(new CustomEvent('graph:invalidate'))
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message
      setError(detail)
    } finally {
      setSaving(false)
    }
  }, [selected, content, hasChanges, saving, onWikilinksChange])

  // Ctrl+S / Cmd+S to save.
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handleSave])

  // Wikilink detection on save only — avoids graph re-layout while typing

  // ── Empty state ──
  if (!selected) {
    return (
      <div className="md-editor-panel">
        <div className="md-editor-empty">
          <FileText size={40} style={{ color: '#444' }} />
          <p>{t('graph.editorEmpty', 'Select a node to view its document')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="md-editor-panel">
      {/* ── Toolbar ── */}
      <div className="md-editor-toolbar">
        <div className="md-editor-toolbar-left">
          <FileText size={16} style={{ color: '#888', flexShrink: 0 }} />
          <span className="md-editor-filename" title={selected.label}>
            {selected.label}
          </span>
          {hasChanges && (
            <span className="md-editor-unsaved" title="Unsaved changes">●</span>
          )}
        </div>

        <div className="md-editor-toolbar-right">
          <button
            className={`md-editor-mode-btn ${mode === 'view' ? 'active' : ''}`}
            onClick={() => setMode('view')}
            title={t('graph.editorView', 'Preview')}
          >
            <Eye size={14} />
          </button>
          <button
            className={`md-editor-mode-btn ${mode === 'edit' ? 'active' : ''}`}
            onClick={() => setMode('edit')}
            title={t('graph.editorEdit', 'Edit')}
          >
            <Pencil size={14} />
          </button>

          {hasChanges && (
            <button
              className="md-editor-save-btn"
              onClick={handleSave}
              disabled={saving}
              title="Ctrl+S"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              <span>{t('graph.editorSave', 'Save')}</span>
            </button>
          )}

          <button className="md-editor-close-btn" onClick={onClose} title="Close">
            <X size={16} />
          </button>
        </div>
      </div>

      {/* ── Content area ── */}
      <div className="md-editor-content">
        {loading && (
          <div className="md-editor-loading">
            <Loader2 size={24} className="animate-spin" />
            <span>{t('graph.editorLoading', 'Loading document...')}</span>
          </div>
        )}

        {error && !loading && (
          <div className="md-editor-error">
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && mode === 'view' && (
          <div className="md-editor-preview" onDoubleClick={() => setMode('edit')}>
            {content ? (
              renderContentWithWikilinks(content).map((part, i) =>
                part.type === 'wikilink' ? (
                  <span key={i} className="md-wikilink" title={part.target}>
                    {part.display}
                  </span>
                ) : (
                  <ReactMarkdown key={i} remarkPlugins={[remarkGfm]}>
                    {part.text}
                  </ReactMarkdown>
                )
              )
            ) : (
              <p className="md-editor-no-content">
                {t('graph.editorNoContent', 'No content available.')}
              </p>
            )}
          </div>
        )}

        {!loading && !error && mode === 'edit' && (
          <div className="md-editor-edit-container">
            {/* Highlight overlay — shows colored text, syncs scroll with textarea */}
            <div
              ref={overlayRef}
              className="md-editor-highlight-overlay"
              aria-hidden="true"
              dangerouslySetInnerHTML={{ __html: highlightWikilinks(content) }}
            />
            <textarea
              ref={textareaRef}
              className="md-editor-textarea"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onScroll={handleEditorScroll}
              spellCheck={false}
            />
          </div>
        )}
      </div>
    </div>
  )
}
