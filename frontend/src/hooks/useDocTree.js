import { useMemo } from 'react'

/**
 * Build a tree structure from a flat documents array + client-only folder list.
 *
 * Node shapes:
 *   Folder: { type: 'folder', name, path, children: [...] }
 *   File:   { type: 'file', id, filename, folder_path, ...doc }
 *
 * Folders are inferred from each document's folder_path. Additional `extraFolders`
 * (created client-side before any doc moves into them) appear as empty folders.
 */
export function useDocTree(documents, extraFolders = []) {
  return useMemo(() => buildTree(documents, extraFolders), [documents, extraFolders])
}

function buildTree(docs, extraFolders) {
  const root = { type: 'folder', name: '', path: '', children: [] }

  // Ensure a folder node exists at path, creating intermediates as needed.
  const ensureFolder = (path) => {
    const parts = (path || '').split('/').filter(Boolean)
    let node = root
    let accumulated = ''
    for (const p of parts) {
      accumulated = accumulated ? `${accumulated}/${p}` : p
      let folder = node.children.find(
        (c) => c.type === 'folder' && c.name === p
      )
      if (!folder) {
        folder = { type: 'folder', name: p, path: accumulated, children: [] }
        node.children.push(folder)
      }
      node = folder
    }
    return node
  }

  // Pre-create any client-side folders (so they appear even if empty).
  for (const path of extraFolders) {
    ensureFolder(path)
  }

  // Insert docs.
  for (const doc of docs) {
    const folderNode = ensureFolder(doc.folder_path || '')
    folderNode.children.push({
      type: 'file',
      id: doc.id,
      filename: doc.filename,
      folder_path: doc.folder_path || '',
      ...doc,
    })
  }

  // Sort: folders first (alpha), then files (alpha).
  sortTree(root)
  return root
}

function sortTree(node) {
  if (node.type !== 'folder') return
  node.children.sort((a, b) => {
    // Folders first
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1
    // Then by sort_order (manual drag order), fallback to alphabetical
    const aOrder = a.sort_order ?? 999999
    const bOrder = b.sort_order ?? 999999
    if (aOrder !== bOrder) return aOrder - bOrder
    const aName = a.type === 'folder' ? a.name : a.filename
    const bName = b.type === 'folder' ? b.name : b.filename
    return (aName || '').localeCompare(bName || '', undefined, { sensitivity: 'base' })
  })
  for (const c of node.children) sortTree(c)
}

/**
 * Given a folder path and optional parent, join them into a canonical path.
 */
export function joinPath(parent, name) {
  return [parent, name].filter(Boolean).join('/')
}
