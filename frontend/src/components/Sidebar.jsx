import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  SquarePen, Settings, PanelLeft, Zap, FileText, Network,
  Upload, Loader2, FilePlus, FolderPlus, User, Briefcase,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { documentsAPI } from '../services/api'
import SidebarDocTree from './SidebarDocTree'

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
  onOpenProfile,
  onOpenJobs,
  onOpenCVs,
  onSelectDocument,
  selectedDocId,
  currentProvider,
  currentModel,
}) {
  const { t } = useTranslation()
  const [documents, setDocuments] = useState([])
  const [extraFolders, setExtraFolders] = useState(() => {
    try {
      const stored = localStorage.getItem('jarvis-extra-folders')
      return stored ? JSON.parse(stored) : []
    } catch { return [] }
  })
  const [uploading, setUploading] = useState(false)
  const [busy, setBusy] = useState(false)
  const fileInputRef = useRef(null)

  const loadDocuments = useCallback(async () => {
    try {
      const { data } = await documentsAPI.list()
      setDocuments(data?.documents || [])
    } catch (err) {
      console.error('[Sidebar] Failed to load documents:', err)
    }
  }, [])

  // Persist extraFolders to localStorage
  useEffect(() => {
    localStorage.setItem('jarvis-extra-folders', JSON.stringify(extraFolders))
  }, [extraFolders])

  useEffect(() => {
    if (isOpen) loadDocuments()
  }, [isOpen, loadDocuments])

  // ── Upload ──
  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await documentsAPI.upload(file)
      await loadDocuments()
      window.dispatchEvent(new CustomEvent('graph:invalidate'))
    } catch (err) {
      console.error('[Sidebar] Upload failed:', err)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // ── Create file ──
  const handleCreateFile = async () => {
    setBusy(true)
    try {
      const baseName = t('sidebar2.untitled', 'Untitled')
      const existing = new Set(
        documents
          .filter((d) => (d.folder_path || '') === '')
          .map((d) => d.filename)
      )
      let name = `${baseName}.md`
      let i = 1
      while (existing.has(name)) {
        i += 1
        name = `${baseName} ${i}.md`
      }
      const { data } = await documentsAPI.create(name, '', `# ${name.replace(/\.md$/, '')}\n`)
      await loadDocuments()
      window.dispatchEvent(new CustomEvent('graph:invalidate'))
      // auto-open the new doc
      if (data?.id) {
        onSelectDocument({ id: data.id, filename: name, folder_path: '' })
      }
    } catch (err) {
      console.error('[Sidebar] Failed to create file:', err)
    } finally {
      setBusy(false)
    }
  }

  // ── Create folder (client-only until it has a child) ──
  const handleCreateFolder = () => {
    const baseName = t('sidebar2.untitledFolder', 'Untitled folder')
    const existing = new Set(
      extraFolders.concat(
        documents
          .map((d) => d.folder_path || '')
          .filter(Boolean)
          .map((p) => p.split('/')[0])
      )
    )
    let name = baseName
    let i = 1
    while (existing.has(name)) {
      i += 1
      name = `${baseName} ${i}`
    }
    setExtraFolders((prev) => [...prev, name])
  }

  // ── Delete file ──
  const handleDeleteFile = async (docId) => {
    try {
      await documentsAPI.delete(docId)
      setDocuments((prev) => prev.filter((d) => d.id !== docId))
      if (selectedDocId === docId) onSelectDocument(null)
      window.dispatchEvent(new CustomEvent('graph:invalidate'))
    } catch (err) {
      console.error('[Sidebar] Failed to delete file:', err)
    }
  }

  // ── Delete folder (all files inside + remove from extraFolders) ──
  const handleDeleteFolder = async (folderPath) => {
    const filesInFolder = documents.filter(
      (d) => d.folder_path === folderPath || d.folder_path.startsWith(folderPath + '/')
    )
    setBusy(true)
    try {
      await Promise.all(filesInFolder.map((d) => documentsAPI.delete(d.id)))
      setDocuments((prev) => prev.filter(
        (d) => d.folder_path !== folderPath && !d.folder_path.startsWith(folderPath + '/')
      ))
      setExtraFolders((prev) => prev.filter((f) => f !== folderPath && !f.startsWith(folderPath + '/')))
      if (filesInFolder.some((d) => d.id === selectedDocId)) onSelectDocument(null)
      window.dispatchEvent(new CustomEvent('graph:invalidate'))
    } catch (err) {
      console.error('[Sidebar] Failed to delete folder:', err)
    } finally {
      setBusy(false)
    }
  }

  // ── Rename file ──
  const handleRenameFile = async (docId, newName) => {
    let finalName = newName.trim()
    if (!finalName) return
    if (!finalName.toLowerCase().endsWith('.md')) finalName += '.md'
    try {
      await documentsAPI.update(docId, { filename: finalName })
      setDocuments((prev) =>
        prev.map((d) => (d.id === docId ? { ...d, filename: finalName } : d))
      )
    } catch (err) {
      console.error('[Sidebar] Rename failed:', err)
    }
  }

  // ── Move file to folder ──
  const handleMoveFile = async (docId, folderPath) => {
    try {
      // Check if old folder will become empty after this move
      const doc = documents.find((d) => d.id === docId)
      const oldFolder = doc?.folder_path || ''

      await documentsAPI.update(docId, { folder_path: folderPath })
      setDocuments((prev) => {
        const updated = prev.map((d) => (d.id === docId ? { ...d, folder_path: folderPath } : d))
        // If old folder is now empty, preserve it as extraFolder
        if (oldFolder) {
          const stillHasFiles = updated.some((d) => d.id !== docId && (d.folder_path || '') === oldFolder)
          if (!stillHasFiles) {
            setExtraFolders((ef) => ef.includes(oldFolder) ? ef : [...ef, oldFolder])
          }
        }
        // New folder becomes "real" — remove from extraFolders
        if (folderPath) {
          const topLevel = folderPath.split('/')[0]
          setExtraFolders((ef) => ef.filter((f) => f !== topLevel))
        }
        return updated
      })
    } catch (err) {
      console.error('[Sidebar] Move failed:', err)
    }
  }

  // ── Rename folder (bulk update every descendant) ──
  const handleRenameFolder = async (oldPath, newName) => {
    const trimmed = newName.trim()
    if (!trimmed) return
    const parentParts = oldPath.split('/').slice(0, -1)
    const newPath = [...parentParts, trimmed].join('/')
    if (newPath === oldPath) return

    // Update all docs whose folder_path starts with oldPath
    const affected = documents.filter(
      (d) => d.folder_path === oldPath || d.folder_path.startsWith(oldPath + '/')
    )
    setBusy(true)
    try {
      await Promise.all(
        affected.map((d) => {
          const updated = newPath + d.folder_path.slice(oldPath.length)
          return documentsAPI.update(d.id, { folder_path: updated })
        })
      )
      await loadDocuments()
      // update extraFolders too if this was a client-only folder
      setExtraFolders((prev) =>
        prev.map((f) => (f === oldPath ? newPath : f))
      )
    } finally {
      setBusy(false)
    }
  }

  // ── Move folder (change folder_path of every descendant) ──
  const handleMoveFolder = async (path, newParent) => {
    const name = path.split('/').pop()
    const newPath = [newParent, name].filter(Boolean).join('/')
    if (newPath === path) return

    const affected = documents.filter(
      (d) => d.folder_path === path || d.folder_path.startsWith(path + '/')
    )
    setBusy(true)
    try {
      await Promise.all(
        affected.map((d) => {
          const updated = newPath + d.folder_path.slice(path.length)
          return documentsAPI.update(d.id, { folder_path: updated })
        })
      )
      await loadDocuments()
      setExtraFolders((prev) =>
        prev.map((f) => (f === path ? newPath : f)).filter((f, i, arr) => arr.indexOf(f) === i)
      )
    } finally {
      setBusy(false)
    }
  }

  // ── Reorder: drag file onto another file → swap position ──
  const handleReorderFiles = async (draggedId, targetId) => {
    const dragged = documents.find((d) => d.id === draggedId)
    const target = documents.find((d) => d.id === targetId)
    if (!dragged || !target) return

    const targetFolder = target.folder_path || ''
    const siblings = documents
      .filter((d) => (d.folder_path || '') === targetFolder && d.id !== draggedId)
      .sort((a, b) => (a.sort_order ?? 999999) - (b.sort_order ?? 999999))

    const targetIdx = siblings.findIndex((d) => d.id === targetId)
    // Dragging down → insert AFTER target; dragging up → insert BEFORE target
    const draggedOrder = dragged.sort_order ?? 999999
    const targetOrder = target.sort_order ?? 999999
    const insertIdx = draggedOrder < targetOrder ? targetIdx + 1 : targetIdx
    siblings.splice(insertIdx, 0, { ...dragged, folder_path: targetFolder })

    const updates = siblings.map((d, i) => ({
      id: d.id,
      sort_order: i,
      folder_path: targetFolder,
    }))

    try {
      await documentsAPI.reorder(updates)
      const lookup = Object.fromEntries(updates.map((u) => [u.id, u]))
      setDocuments((prev) =>
        prev.map((d) => {
          const upd = lookup[d.id]
          return upd ? { ...d, sort_order: upd.sort_order, folder_path: upd.folder_path } : d
        })
      )
    } catch (err) {
      console.error('[Sidebar] Reorder failed:', err)
    }
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

          {/* Navigation: Profile / Jobs / Graph */}
          <div className="px-2 py-1 d-flex flex-column gap-1">
            <SidebarNavItem
              icon={User}
              label={t('sidebar.profile', 'Profile')}
              onClick={onOpenProfile}
            />
            <SidebarNavItem
              icon={Briefcase}
              label={t('sidebar.jobs', 'Jobs')}
              onClick={onOpenJobs}
            />
            <SidebarNavItem
              icon={FileText}
              label={t('sidebar.cvs', 'CVs & Portfolios')}
              onClick={onOpenCVs}
            />
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
              <div className="sidebar-docs-actions">
                <button
                  className="sidebar-docs-upload-btn"
                  onClick={handleCreateFile}
                  disabled={busy}
                  title={t('sidebar2.newFile', 'New file')}
                >
                  <FilePlus size={14} />
                </button>
                <button
                  className="sidebar-docs-upload-btn"
                  onClick={handleCreateFolder}
                  title={t('sidebar2.newFolder', 'New folder')}
                >
                  <FolderPlus size={14} />
                </button>
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
            </div>

            <div className="sidebar-docs-list">
              {documents.length === 0 && extraFolders.length === 0 ? (
                <div className="sidebar-docs-empty">
                  {t('sidebar.noDocuments', 'No documents yet')}
                </div>
              ) : (
                <SidebarDocTree
                  documents={documents}
                  extraFolders={extraFolders}
                  selectedDocId={selectedDocId}
                  onSelectFile={onSelectDocument}
                  onDeleteFile={handleDeleteFile}
                  onDeleteFolder={handleDeleteFolder}
                  onRenameFile={handleRenameFile}
                  onMoveFile={handleMoveFile}
                  onReorderFiles={handleReorderFiles}
                  onRenameFolder={handleRenameFolder}
                  onMoveFolder={handleMoveFolder}
                />
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
