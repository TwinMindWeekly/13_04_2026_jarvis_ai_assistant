import { useState, useCallback } from 'react'
import { DndContext, DragOverlay, PointerSensor, useSensor, useSensors, useDroppable } from '@dnd-kit/core'
import { FileText, Folder } from 'lucide-react'
import { useDocTree } from '../hooks/useDocTree'
import SidebarDocNode from './SidebarDocNode'

/**
 * SidebarDocTree — Obsidian-style tree view for documents.
 *
 * Props:
 *   documents          flat list from API
 *   extraFolders       client-side folders (empty ones that haven't received any file yet)
 *   selectedDocId      currently selected doc id
 *   onSelectFile(doc)  open document in editor
 *   onDeleteFile(id)   delete via API + remove from list
 *   onRenameFile(id,name)    rename via PATCH
 *   onMoveFile(id,folder)    move via PATCH
 *   onRenameFolder(oldPath, newName)   rename folder (bulk move children)
 *   onMoveFolder(path, newParent)      move folder (bulk move children)
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
  onRenameFolder,
  onMoveFolder,
}) {
  const tree = useDocTree(documents, extraFolders)
  const [expanded, setExpanded] = useState({})
  const [renamingId, setRenamingId] = useState(null)
  const [activeDrag, setActiveDrag] = useState(null)

  // pointer drag requires 5px movement before activating so clicks still work
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

    // Drop onto a folder → move file (or folder) into it.
    if (overData.type === 'folder' || overData.type === 'root') {
      const destPath = overData.type === 'root' ? '' : overData.path
      if (activeData.type === 'file') {
        onMoveFile(activeData.docId, destPath)
      } else if (activeData.type === 'folder') {
        // Don't drop folder into itself or a descendant.
        if (destPath === activeData.path) return
        if (destPath.startsWith(activeData.path + '/')) return
        onMoveFolder(activeData.path, destPath)
      }
    }
  }, [onMoveFile, onMoveFolder])

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
