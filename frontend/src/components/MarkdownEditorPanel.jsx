import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  FileText, Eye, Pencil, Save, Loader2, AlertCircle, X,
} from 'lucide-react'
import { vaultAPI } from '../services/api'

/**
 * MarkdownEditorPanel — Obsidian-style Markdown viewer/editor.
 *
 * Modes:
 *  - "view": Rendered markdown (react-markdown + remark-gfm)
 *  - "edit": Monospace textarea for raw markdown editing
 *
 * Loads vault .md content when `selected` node changes.
 */
export default function MarkdownEditorPanel({ selected, onClose }) {
  const { t } = useTranslation()
  const [mode, setMode] = useState('view')
  const [content, setContent] = useState('')
  const [savedContent, setSavedContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const textareaRef = useRef(null)

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
  }, [selected])

  // Focus textarea when switching to edit mode.
  useEffect(() => {
    if (mode === 'edit' && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [mode])

  const handleSave = useCallback(async () => {
    if (!selected || !hasChanges || saving) return
    setSaving(true)
    try {
      await vaultAPI.save(selected.id, content)
      setSavedContent(content)
    } catch (err) {
      const detail = err.response?.data?.detail || err.message
      setError(detail)
    } finally {
      setSaving(false)
    }
  }, [selected, content, hasChanges, saving])

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
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            ) : (
              <p className="md-editor-no-content">
                {t('graph.editorNoContent', 'No content available.')}
              </p>
            )}
          </div>
        )}

        {!loading && !error && mode === 'edit' && (
          <textarea
            ref={textareaRef}
            className="md-editor-textarea"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            spellCheck={false}
          />
        )}
      </div>
    </div>
  )
}
