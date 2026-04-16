import { useState, useCallback } from 'react'
import { DndContext, DragOverlay, PointerSensor, useSensor, useSensors, useDroppable } from '@dnd-kit/core'
import { FileText, Folder } from 'lucide-react'
import { useDocTree } from '../hooks/useDocTree'
import SidebarDocNode from './SidebarDocNode'

/**
 * SidebarDocTree — Obsidian-style tree view for documents.
 *
 * Supports:
 * - Drag file onto folder → move into folder
 * - Drag file onto another file → reorder (insert before target)
 * - Drag folder onto folder → nest folder
 * - Drag onto root zone → move to root
 */
export default function SidebarDocTree({
  documents,
  extraFolders,
  selectedDocId,
  onSelectFile,
  onDeleteFile,
  onDeleteFolder,
  onRenameFile,
  onMoveFile,
  onReorderFiles,
  onRenameFolder,
  onMoveFolder,
}) {
  const tree = useDocTree(documents, extraFolders)
  const [expanded, setExpanded] = useState({})
  const [renamingId, setRenamingId] = useState(null)
  const [activeDrag, setActiveDrag] = useState(null)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  const handleToggleExpand = useCallback((path) => {
    setExpanded((prev) => ({ ...prev, [path]: prev[path] === false ? true : false }))
  }, [])

  const handleDragStart = useCallback((event) => {
    setActiveDrag(event.active.data.current)
  }, [])

  const handleDragEnd = useCallback((event) => {
    setActiveDrag(null)
    const { active, over } = event
    if (!over) return
    const activeData = active.data.current
    const overData = over.data.current
    if (!activeData || !overData) return

    // Drop file onto another file → reorder within same folder
    if (activeData.type === 'file' && overData.type === 'file') {
      if (activeData.docId === overData.docId) return
      onReorderFiles?.(activeData.docId, overData.docId)
      return
    }

    // Drop onto a folder or root
    if (overData.type === 'folder' || overData.type === 'root') {
      const destPath = overData.type === 'root' ? '' : overData.path
      if (activeData.type === 'file') {
        onMoveFile(activeData.docId, destPath)
      } else if (activeData.type === 'folder') {
        if (destPath === activeData.path) return
        if (destPath.startsWith(activeData.path + '/')) return
        onMoveFolder(activeData.path, destPath)
      }
      if (destPath) {
        setExpanded((prev) => ({ ...prev, [destPath]: true }))
      }
    }
  }, [onMoveFile, onMoveFolder, onReorderFiles])

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <RootDropZone />
      <SidebarDocNode
        node={tree}
        expanded={expanded}
        onToggleExpand={handleToggleExpand}
        selectedDocId={selectedDocId}
        onSelectFile={onSelectFile}
        onDeleteFile={onDeleteFile}
        onDeleteFolder={onDeleteFolder}
        onRenameFile={onRenameFile}
        onRenameFolder={onRenameFolder}
        renamingId={renamingId}
        setRenamingId={setRenamingId}
      />
      <DragOverlay dropAnimation={null}>
        {activeDrag && (
          <div className="sidebar-tree-row drag-overlay">
            {activeDrag.type === 'folder' ? <Folder size={14} /> : <FileText size={13} />}
            <span className="sidebar-tree-name">
              {activeDrag.type === 'folder' ? activeDrag.path?.split('/').pop() : activeDrag.filename}
            </span>
          </div>
        )}
      </DragOverlay>
    </DndContext>
  )
}

function RootDropZone() {
  const { setNodeRef, isOver } = useDroppable({
    id: 'root-zone',
    data: { type: 'root' },
  })
  return (
    <div
      ref={setNodeRef}
      className={`sidebar-tree-root-zone ${isOver ? 'drop-active' : ''}`}
      aria-hidden="true"
    />
  )
}
