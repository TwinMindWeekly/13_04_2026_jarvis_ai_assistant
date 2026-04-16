import { useState, useRef, useEffect, useCallback } from 'react'
import { useDraggable, useDroppable } from '@dnd-kit/core'
import {
  FileText, Folder, FolderOpen, ChevronRight, ChevronDown, Trash2,
} from 'lucide-react'

/** Merge two refs (from useDraggable + useDroppable) into one callback ref. */
function useMergedRef(ref1, ref2) {
  return useCallback((node) => {
    ref1(node)
    ref2(node)
  }, [ref1, ref2])
}

/**
 * SidebarDocNode — recursive tree node renderer.
 *
 * Handles:
 *  - Folder: expand/collapse, click to expand, drop target, optional rename
 *  - File: click to select, drag source, hover delete, double-click rename
 */
export default function SidebarDocNode({
  node,
  depth = 0,
  expanded,
  onToggleExpand,
  selectedDocId,
  onSelectFile,
  onDeleteFile,
  onDeleteFolder,
  onRenameFile,
  onRenameFolder,
  renamingId,
  setRenamingId,
}) {
  if (node.type === 'folder' && node.path === '') {
    // Root — just render children.
    return (
      <div className="sidebar-doc-tree-root">
        {node.children.map((child) => (
          <SidebarDocNode
            key={keyFor(child)}
            node={child}
            depth={0}
            expanded={expanded}
            onToggleExpand={onToggleExpand}
            selectedDocId={selectedDocId}
            onSelectFile={onSelectFile}
            onDeleteFile={onDeleteFile}
            onDeleteFolder={onDeleteFolder}
            onRenameFile={onRenameFile}
            onRenameFolder={onRenameFolder}
            renamingId={renamingId}
            setRenamingId={setRenamingId}
          />
        ))}
      </div>
    )
  }

  if (node.type === 'folder') {
    return (
      <FolderNode
        node={node}
        depth={depth}
        expanded={expanded}
        onToggleExpand={onToggleExpand}
        selectedDocId={selectedDocId}
        onSelectFile={onSelectFile}
        onDeleteFile={onDeleteFile}
        onDeleteFolder={onDeleteFolder}
        onRenameFile={onRenameFile}
        onRenameFolder={onRenameFolder}
        renamingId={renamingId}
        setRenamingId={setRenamingId}
      />
    )
  }

  // File
  return (
    <FileNode
      node={node}
      depth={depth}
      selectedDocId={selectedDocId}
      onSelectFile={onSelectFile}
      onDeleteFile={onDeleteFile}
      onRenameFile={onRenameFile}
      renamingId={renamingId}
      setRenamingId={setRenamingId}
    />
  )
}

function keyFor(node) {
  return node.type === 'folder' ? `f:${node.path}` : `d:${node.id}`
}

// ---------------------------------------------------------------------------
// FolderNode
// ---------------------------------------------------------------------------

function FolderNode({
  node,
  depth,
  expanded,
  onToggleExpand,
  selectedDocId,
  onSelectFile,
  onDeleteFile,
  onDeleteFolder,
  onRenameFile,
  onRenameFolder,
  renamingId,
  setRenamingId,
}) {
  const isOpen = expanded[node.path] !== false // default true
  const renamingKey = `folder:${node.path}`
  const isRenaming = renamingId === renamingKey

  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: `folder-${node.path}`,
    data: { type: 'folder', path: node.path },
  })

  const { attributes, listeners, setNodeRef: setDragRef, isDragging } = useDraggable({
    id: `drag-folder-${node.path}`,
    data: { type: 'folder', path: node.path },
  })

  const fileCount = node.children.filter((c) => c.type === 'file').length

  return (
    <div>
      <div
        ref={setDropRef}
        className={`sidebar-tree-row folder ${isOver ? 'drop-active' : ''} ${isDragging ? 'dragging' : ''}`}
        style={{ paddingLeft: depth * 12 + 8 }}
        onClick={() => onToggleExpand(node.path)}
        onDoubleClick={(e) => {
          e.stopPropagation()
          if (!node.path) return
          setRenamingId(renamingKey)
        }}
      >
        <span className="sidebar-tree-chevron">
          {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
        <span ref={setDragRef} {...attributes} {...listeners} style={{ display: 'flex', cursor: 'grab' }}>
          {isOpen ? <FolderOpen size={14} /> : <Folder size={14} />}
        </span>
        {isRenaming ? (
          <InlineRename
            initial={node.name}
            onSubmit={(newName) => {
              onRenameFolder(node.path, newName)
              setRenamingId(null)
            }}
            onCancel={() => setRenamingId(null)}
          />
        ) : (
          <>
            <span className="sidebar-tree-name" title={node.name}>
              {node.name}
            </span>
            {onDeleteFolder && (
              <button
                className="sidebar-tree-delete"
                onClick={(e) => {
                  e.stopPropagation()
                  if (fileCount > 0) {
                    if (!window.confirm(`Delete folder "${node.name}" and ${fileCount} file(s) inside?`)) return
                  }
                  onDeleteFolder(node.path)
                }}
                title="Delete folder"
              >
                <Trash2 size={11} />
              </button>
            )}
          </>
        )}
      </div>

      {isOpen && node.children.length > 0 && (
        <div>
          {node.children.map((child) => (
            <SidebarDocNode
              key={keyFor(child)}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggleExpand={onToggleExpand}
              selectedDocId={selectedDocId}
              onSelectFile={onSelectFile}
              onDeleteFile={onDeleteFile}
              onDeleteFolder={onDeleteFolder}
              onRenameFile={onRenameFile}
              onRenameFolder={onRenameFolder}
              renamingId={renamingId}
              setRenamingId={setRenamingId}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// FileNode
// ---------------------------------------------------------------------------

function FileNode({
  node,
  depth,
  selectedDocId,
  onSelectFile,
  onDeleteFile,
  onRenameFile,
  renamingId,
  setRenamingId,
}) {
  const renamingKey = `file:${node.id}`
  const isRenaming = renamingId === renamingKey

  const { attributes, listeners, setNodeRef: setDragRef, isDragging } = useDraggable({
    id: `doc-${node.id}`,
    data: { type: 'file', docId: node.id, filename: node.filename, folderPath: node.folder_path || '' },
  })

  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: `file-drop-${node.id}`,
    data: { type: 'file', docId: node.id, folderPath: node.folder_path || '' },
  })

  const isActive = selectedDocId === node.id

  return (
    <div
      ref={setDropRef}
      className={`sidebar-tree-row file ${isActive ? 'active' : ''} ${isDragging ? 'dragging' : ''} ${isOver ? 'drop-active' : ''}`}
      style={{ paddingLeft: depth * 12 + 28 }}
      onClick={() => onSelectFile(node)}
      onDoubleClick={(e) => {
        e.stopPropagation()
        setRenamingId(renamingKey)
      }}
    >
      <span ref={setDragRef} {...attributes} {...listeners} style={{ display: 'flex', cursor: 'grab', flexShrink: 0 }}>
        <FileText size={13} style={{ color: '#888' }} />
      </span>
      {isRenaming ? (
        <InlineRename
          initial={node.filename}
          onSubmit={(newName) => {
            onRenameFile(node.id, newName)
            setRenamingId(null)
          }}
          onCancel={() => setRenamingId(null)}
        />
      ) : (
        <>
          <span className="sidebar-tree-name" title={node.filename}>
            {node.filename}
          </span>
          <button
            className="sidebar-tree-delete"
            onClick={(e) => {
              e.stopPropagation()
              onDeleteFile(node.id)
            }}
            title="Delete"
          >
            <Trash2 size={11} />
          </button>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// InlineRename
// ---------------------------------------------------------------------------

function InlineRename({ initial, onSubmit, onCancel }) {
  const [value, setValue] = useState(initial)
  const ref = useRef(null)

  useEffect(() => {
    if (ref.current) {
      ref.current.focus()
      ref.current.select()
    }
  }, [])

  const handleKey = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      const trimmed = value.trim()
      if (trimmed && trimmed !== initial) onSubmit(trimmed)
      else onCancel()
    } else if (e.key === 'Escape') {
      onCancel()
    }
  }

  return (
    <input
      ref={ref}
      className="sidebar-tree-rename-input"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKey}
      onBlur={() => {
        const trimmed = value.trim()
        if (trimmed && trimmed !== initial) onSubmit(trimmed)
        else onCancel()
      }}
      onClick={(e) => e.stopPropagation()}
    />
  )
}
