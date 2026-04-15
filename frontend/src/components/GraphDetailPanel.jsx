import { Button, ListGroup } from 'react-bootstrap'
import { useTranslation } from 'react-i18next'
import { X, File, FolderClosed, Calendar, Hash, Layers } from 'lucide-react'

/**
 * GraphDetailPanel — side panel showing the selected node's metadata and
 * neighbors. Slides in from the right of the graph.
 */
export default function GraphDetailPanel({
  node,
  neighbors,
  onClose,
  onSelectNeighbor,
}) {
  const { t } = useTranslation()

  const formatSize = (bytes) => {
    if (!bytes) return '-'
    const units = ['B', 'KB', 'MB', 'GB']
    let i = 0
    let n = bytes
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024
      i++
    }
    return `${n.toFixed(1)} ${units[i]}`
  }

  const formatDate = (iso) => {
    if (!iso) return '-'
    try {
      return new Date(iso).toLocaleString()
    } catch {
      return iso
    }
  }

  return (
    <div
      style={{
        width: 340,
        minWidth: 340,
        background: '#1a1b22',
        borderLeft: '1px solid #2a2b33',
        overflowY: 'auto',
        color: '#eee',
      }}
    >
      <div
        className="d-flex align-items-center justify-content-between p-3"
        style={{ borderBottom: '1px solid #2a2b33' }}
      >
        <div className="d-flex align-items-center gap-2" style={{ minWidth: 0 }}>
          <File size={18} />
          <strong
            style={{
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
            title={node.label}
          >
            {node.label}
          </strong>
        </div>
        <Button
          size="sm"
          variant="link"
          className="text-light p-0"
          onClick={onClose}
          aria-label="Close detail panel"
        >
          <X size={18} />
        </Button>
      </div>

      <div className="p-3" style={{ fontSize: 13 }}>
        <div className="d-flex align-items-center gap-2 mb-2">
          <FolderClosed size={14} />
          <span style={{ color: '#aaa' }}>{t('graph.folder', 'Folder')}:</span>
          <span>{node.folder || t('graph.rootFolder', '(root)')}</span>
        </div>
        <div className="d-flex align-items-center gap-2 mb-2">
          <Calendar size={14} />
          <span style={{ color: '#aaa' }}>{t('graph.uploadedAt', 'Uploaded')}:</span>
          <span>{formatDate(node.uploaded_at)}</span>
        </div>
        <div className="d-flex align-items-center gap-2 mb-2">
          <Hash size={14} />
          <span style={{ color: '#aaa' }}>{t('graph.chunks', 'Chunks')}:</span>
          <span>{node.chunks_count}</span>
        </div>
        <div className="d-flex align-items-center gap-2 mb-2">
          <Layers size={14} />
          <span style={{ color: '#aaa' }}>{t('graph.fileSize', 'Size')}:</span>
          <span>{formatSize(node.size_bytes)}</span>
        </div>
      </div>

      <div
        className="px-3 py-2"
        style={{ borderTop: '1px solid #2a2b33', fontSize: 12, color: '#aaa' }}
      >
        {t('graph.neighbors', 'Related documents')} ({neighbors.length})
      </div>
      {neighbors.length === 0 ? (
        <div className="p-3" style={{ color: '#888', fontSize: 13 }}>
          {t('graph.noNeighbors', 'No related documents above the current threshold.')}
        </div>
      ) : (
        <ListGroup variant="flush">
          {neighbors.map(({ node: nb, weight }) => (
            <ListGroup.Item
              key={nb.id}
              action
              onClick={() => onSelectNeighbor(nb)}
              style={{
                background: 'transparent',
                color: '#eee',
                borderColor: '#2a2b33',
                cursor: 'pointer',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <span
                  style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    flex: 1,
                  }}
                  title={nb.label}
                >
                  {nb.label}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    color: '#888',
                    fontFamily: 'monospace',
                  }}
                >
                  {(weight * 100).toFixed(0)}%
                </span>
              </div>
            </ListGroup.Item>
          ))}
        </ListGroup>
      )}
    </div>
  )
}
