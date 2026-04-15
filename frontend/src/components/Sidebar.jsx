import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { SquarePen, Settings, PanelLeft, Zap, FileText, Network, Upload, Trash2, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { documentsAPI } from '../services/api'

const SIDEBAR_WIDTH = 260

function SidebarNavItem({ icon: Icon, label, onClick, active }) {
  return (
    <button className={`sidebar-nav-item ${active ? 'active' : ''}`} onClick={onClick}>
      <Icon size={18} />
      <span>{label}</span>
    </button>
  )
}

export default function Sidebar({
  isOpen,
  onToggle,
  onNewChat,
  onOpenSettings,
  onOpenGraph,
  onSelectDocument,
  selectedDocId,
  currentProvider,
  currentModel,
}) {
  const { t } = useTranslation()
  const [documents, setDocuments] = useState([])
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)

  const loadDocuments = useCallback(async () => {
    try {
      const { data } = await documentsAPI.list()
      setDocuments(data?.documents || [])
    } catch {
      // silent
    }
  }, [])

  useEffect(() => {
    if (isOpen) loadDocuments()
  }, [isOpen, loadDocuments])

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await documentsAPI.upload(file)
      await loadDocuments()
    } catch {
      // silent
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async (e, docId) => {
    e.stopPropagation()
    try {
      await documentsAPI.delete(docId)
      setDocuments((prev) => prev.filter((d) => d.id !== docId))
      if (selectedDocId === docId) onSelectDocument(null)
    } catch {
      // silent
    }
  }

  const formatBytes = (bytes) => {
    if (!bytes) return '-'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            key="overlay"
            className="sidebar-overlay d-lg-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onToggle}
          />
        )}
      </AnimatePresence>

      {/* Sidebar panel */}
      <motion.aside
        className="sidebar-panel"
        initial={false}
        animate={{ width: isOpen ? SIDEBAR_WIDTH : 0 }}
        transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
        aria-hidden={!isOpen}
      >
        <div className="sidebar-inner">
          {/* Top: toggle + new chat */}
          <div className="d-flex align-items-center justify-content-between px-2 pt-3 pb-1">
            <button
              onClick={onToggle}
              className="sidebar-icon-btn"
              aria-label="Toggle sidebar"
            >
              <PanelLeft size={20} />
            </button>

            <button
              onClick={onNewChat}
              className="sidebar-icon-btn"
              aria-label={t('sidebar.newChat')}
              title={t('sidebar.newChat')}
            >
              <SquarePen size={20} />
            </button>
          </div>

          {/* Navigation: Graph only */}
          <div className="px-2 py-1">
            <SidebarNavItem
              icon={Network}
              label={t('sidebar.graph', 'Knowledge Graph')}
              onClick={onOpenGraph}
            />
          </div>

          {/* Documents section */}
          <div className="sidebar-docs-section">
            <div className="sidebar-docs-header">
              <div className="sidebar-docs-title">
                <FileText size={14} />
                <span>{t('sidebar.documents', 'Documents')} ({documents.length})</span>
              </div>
              <button
                className="sidebar-docs-upload-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                title="Upload"
              >
                {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
              </button>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleUpload}
                accept=".pdf,.docx,.txt,.md,.pptx,.xlsx"
                style={{ display: 'none' }}
              />
            </div>

            <div className="sidebar-docs-list">
              {documents.length === 0 ? (
                <div className="sidebar-docs-empty">
                  {t('sidebar.noDocuments', 'No documents yet')}
                </div>
              ) : (
                documents.map((doc) => (
                  <button
                    key={doc.id}
                    className={`sidebar-doc-item ${selectedDocId === doc.id ? 'active' : ''}`}
                    onClick={() => onSelectDocument(doc)}
                  >
                    <FileText size={14} className="flex-shrink-0" style={{ color: '#888' }} />
                    <div className="sidebar-doc-info">
                      <div className="sidebar-doc-name" title={doc.filename}>
                        {doc.filename}
                      </div>
                      <div className="sidebar-doc-meta">
                        {formatBytes(doc.size_bytes)}
                      </div>
                    </div>
                    <button
                      className="sidebar-doc-delete"
                      onClick={(e) => handleDelete(e, doc.id)}
                      title="Delete"
                    >
                      <Trash2 size={12} />
                    </button>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Bottom: provider info + settings */}
          <div
            className="px-2 pb-3 pt-2"
            style={{ borderTop: '1px solid var(--border-light)' }}
          >
            {currentProvider && currentModel && (
              <div
                className="d-flex align-items-center gap-2 px-3 py-2 mb-1 rounded-3"
                style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}
              >
                <div
                  className="d-flex align-items-center justify-content-center rounded-circle flex-shrink-0"
                  style={{ width: 20, height: 20, background: 'var(--accent)' }}
                >
                  <Zap size={10} color="#fff" />
                </div>
                <span className="text-truncate">
                  {currentProvider} · {currentModel}
                </span>
              </div>
            )}

            <SidebarNavItem
              icon={Settings}
              label={t('sidebar.settings')}
              onClick={onOpenSettings}
            />
          </div>
        </div>
      </motion.aside>
    </>
  )
}
