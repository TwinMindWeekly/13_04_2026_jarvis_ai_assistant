import { FileText, X, Loader2 } from 'lucide-react'

export default function AttachmentPreview({ attachments, uploading, error, onRemove }) {
  if (attachments.length === 0 && !uploading && !error) return null

  return (
    <div className="d-flex flex-wrap gap-1 mb-2" style={{ maxWidth: 768, margin: '0 auto', padding: '0 16px' }}>
      {attachments.map((att, i) => (
        <div
          key={i}
          className="d-flex align-items-center gap-1"
          style={{
            background: 'rgba(99,102,241,0.12)',
            borderRadius: 6,
            padding: '3px 8px 3px 6px',
            fontSize: '0.75rem',
            color: 'var(--text-secondary)',
          }}
        >
          <FileText size={12} style={{ flexShrink: 0 }} />
          <span style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {att.filename}
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}>
            {att.charCount > 1000 ? `${(att.charCount / 1000).toFixed(0)}K` : att.charCount} chars
          </span>
          <button
            onClick={() => onRemove(i)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, lineHeight: 1, color: 'var(--text-muted)' }}
            aria-label="Remove"
          >
            <X size={12} />
          </button>
        </div>
      ))}

      {uploading && (
        <div
          className="d-flex align-items-center gap-1"
          style={{
            background: 'rgba(99,102,241,0.08)',
            borderRadius: 6,
            padding: '3px 8px',
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
          }}
        >
          <Loader2 size={12} className="animate-spin" />
          <span>Uploading...</span>
        </div>
      )}

      {error && (
        <div style={{ fontSize: '0.72rem', color: 'var(--error, #ef4444)', padding: '2px 4px' }}>
          {error}
        </div>
      )}
    </div>
  )
}
