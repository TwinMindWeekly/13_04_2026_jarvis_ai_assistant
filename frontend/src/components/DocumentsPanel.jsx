import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Upload, Trash2, X, Loader2 } from 'lucide-react'
import { documentsAPI } from '../services/api'

/**
 * DocumentsPanel — Modal for uploading and managing documents for RAG.
 */
export default function DocumentsPanel({ isOpen, onClose }) {
  const [documents, setDocuments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  const loadDocuments = useCallback(async () => {
    try {
      const { data } = await documentsAPI.list()
      setDocuments(data?.documents || [])
    } catch (err) {
      setError(err.message || 'Failed to load documents')
    }
  }, [])

  useEffect(() => {
    if (isOpen) loadDocuments()
  }, [isOpen, loadDocuments])

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)
    try {
      await documentsAPI.upload(file)
      await loadDocuments()
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err.message || 'Upload failed')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async (docId) => {
    try {
      await documentsAPI.delete(docId)
      setDocuments((prev) => prev.filter((d) => d.id !== docId))
    } catch (err) {
      setError(err.message || 'Delete failed')
    }
  }

  const formatBytes = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="documents-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="documents-modal"
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.18 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="documents-header">
              <div className="d-flex align-items-center gap-2">
                <FileText size={18} style={{ color: 'var(--accent)' }} />
                <h2 className="m-0" style={{ fontSize: '1rem', fontWeight: 600 }}>
                  Documents ({documents.length})
                </h2>
              </div>
              <button onClick={onClose} className="sidebar-icon-btn" aria-label="Close">
                <X size={18} />
              </button>
            </div>

            <div className="documents-body">
              {/* Upload area */}
              <button
                className="upload-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    <span>Uploading and indexing...</span>
                  </>
                ) : (
                  <>
                    <Upload size={18} />
                    <span>Upload document (PDF, DOCX, TXT, MD, PPTX, XLSX)</span>
                  </>
                )}
              </button>

              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept=".pdf,.docx,.txt,.md,.pptx,.xlsx"
                style={{ display: 'none' }}
              />

              {error && (
                <div className="documents-error">
                  {error}
                </div>
              )}

              {/* Document list */}
              <div className="documents-list">
                {documents.length === 0 ? (
                  <div className="documents-empty">
                    <FileText size={32} style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
                    <p className="m-0 mt-2" style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                      No documents uploaded yet
                    </p>
                  </div>
                ) : (
                  documents.map((doc) => (
                    <div key={doc.id} className="document-item">
                      <FileText size={18} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
                      <div className="document-info">
                        <div className="document-name">{doc.filename}</div>
                        <div className="document-meta">
                          {doc.chunks_count} chunks · {formatBytes(doc.size_bytes)}
                        </div>
                      </div>
                      <button
                        className="document-delete"
                        onClick={() => handleDelete(doc.id)}
                        aria-label="Delete"
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
