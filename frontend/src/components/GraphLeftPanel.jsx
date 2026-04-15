import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Search, FileText, FolderClosed, Calendar, Hash, Layers, ArrowLeft,
} from 'lucide-react'

/**
 * GraphLeftPanel — left sidebar showing document list + detail view.
 *
 * Two modes:
 *  1. List mode (default): search box + scrollable document list.
 *  2. Detail mode (when `selected` is set): document metadata + neighbors.
 */
export default function GraphLeftPanel({
  nodes,
  links,
  selected,
  onSelectNode,
  style,
}) {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const searchLower = search.trim().toLowerCase()

  const filteredNodes = useMemo(
    () =>
      searchLower
        ? nodes.filter((n) => (n.label || '').toLowerCase().includes(searchLower))
        : nodes,
    [nodes, searchLower]
  )

  // Build neighbor list for selected node.
  const neighbors = useMemo(() => {
    if (!selected) return []
    const adj = {}
    for (const link of links) {
      const s = typeof link.source === 'object' ? link.source.id : link.source
      const tgt = typeof link.target === 'object' ? link.target.id : link.target
      if (s === selected.id) adj[tgt] = link.weight
      if (tgt === selected.id) adj[s] = link.weight
    }
    const nodesById = Object.fromEntries(nodes.map((n) => [n.id, n]))
    return Object.entries(adj)
      .map(([id, weight]) => ({ node: nodesById[id], weight }))
      .filter((x) => x.node)
      .sort((a, b) => b.weight - a.weight)
  }, [selected, links, nodes])

  const formatSize = (bytes) => {
    if (!bytes) return '-'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  const formatDate = (iso) => {
    if (!iso) return '-'
    try { return new Date(iso).toLocaleDateString() } catch { return iso }
  }

  // ── Detail mode ──
  if (selected) {
    return (
      <div className="graph-left-panel" style={style}>
        <div className="graph-left-header">
          <button
            className="graph-left-back"
            onClick={() => onSelectNode(null)}
          >
            <ArrowLeft size={16} />
            <span>{t('graph.allDocuments', 'All documents')}</span>
          </button>
        </div>

        <div className="graph-left-detail">
          <div className="graph-left-detail-title">
            <FileText size={18} />
            <strong title={selected.label}>{selected.label}</strong>
          </div>

          <div className="graph-left-meta">
            <div className="graph-left-meta-row">
              <FolderClosed size={14} />
              <span className="graph-left-meta-label">{t('graph.folder', 'Folder')}:</span>
              <span>{selected.folder || t('graph.rootFolder', '(root)')}</span>
            </div>
            <div className="graph-left-meta-row">
              <Calendar size={14} />
              <span className="graph-left-meta-label">{t('graph.uploadedAt', 'Uploaded')}:</span>
              <span>{formatDate(selected.uploaded_at)}</span>
            </div>
            <div className="graph-left-meta-row">
              <Hash size={14} />
              <span className="graph-left-meta-label">{t('graph.chunks', 'Chunks')}:</span>
              <span>{selected.chunks_count}</span>
            </div>
            <div className="graph-left-meta-row">
              <Layers size={14} />
              <span className="graph-left-meta-label">{t('graph.fileSize', 'Size')}:</span>
              <span>{formatSize(selected.size_bytes)}</span>
            </div>
          </div>

          <div className="graph-left-neighbors-header">
            {t('graph.neighbors', 'Related documents')} ({neighbors.length})
          </div>
          {neighbors.length === 0 ? (
            <div className="graph-left-empty-msg">
              {t('graph.noNeighbors', 'No related documents above the current threshold.')}
            </div>
          ) : (
            <div className="graph-left-neighbors-list">
              {neighbors.map(({ node: nb, weight }) => (
                <button
                  key={nb.id}
                  className="graph-left-neighbor-item"
                  onClick={() => onSelectNode(nb)}
                >
                  <span className="graph-left-neighbor-name" title={nb.label}>
                    {nb.label}
                  </span>
                  <span className="graph-left-neighbor-score">
                    {(weight * 100).toFixed(0)}%
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── List mode ──
  return (
    <div className="graph-left-panel" style={style}>
      <div className="graph-left-header">
        <div className="graph-left-search">
          <Search size={14} />
          <input
            type="text"
            placeholder={t('graph.searchDocs', 'Search documents...')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="graph-left-list">
        {filteredNodes.length === 0 ? (
          <div className="graph-left-empty-msg">
            {searchLower
              ? t('graph.noResults', 'No documents match your search.')
              : t('graph.noDocsYet', 'Upload documents to see the knowledge graph.')}
          </div>
        ) : (
          filteredNodes.map((node) => (
            <button
              key={node.id}
              className={`graph-left-doc-item ${selected?.id === node.id ? 'active' : ''}`}
              onClick={() => onSelectNode(node)}
            >
              <FileText size={16} className="flex-shrink-0" style={{ color: '#888' }} />
              <div className="graph-left-doc-info">
                <div className="graph-left-doc-name" title={node.label}>
                  {node.label}
                </div>
                <div className="graph-left-doc-meta">
                  {node.chunks_count} chunks · {formatSize(node.size_bytes)}
                </div>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
