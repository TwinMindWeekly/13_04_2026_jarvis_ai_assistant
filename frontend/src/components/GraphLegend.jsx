import { useTranslation } from 'react-i18next'

/**
 * GraphLegend — small floating legend in the graph's bottom-left corner,
 * listing the folder → color mapping.
 */
export default function GraphLegend({ folderColors }) {
  const { t } = useTranslation()
  // Filter out root (empty string) entries — no need to show in legend
  const entries = Object.entries(folderColors).filter(([folder]) => folder !== '')
  if (entries.length === 0) return null

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 16,
        left: 16,
        background: 'rgba(26, 27, 34, 0.92)',
        border: '1px solid #2a2b33',
        borderRadius: 6,
        padding: '8px 12px',
        maxWidth: 220,
        maxHeight: 180,
        overflowY: 'auto',
        color: '#eee',
        fontSize: 12,
        zIndex: 5,
      }}
    >
      <div style={{ color: '#aaa', marginBottom: 6, fontWeight: 600 }}>
        {t('graph.legend', 'Folders')}
      </div>
      {entries.map(([folder, color]) => (
        <div
          key={folder}
          className="d-flex align-items-center gap-2"
          style={{ marginBottom: 3 }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: color,
              display: 'inline-block',
              flexShrink: 0,
            }}
          />
          <span
            style={{
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
            title={folder}
          >
            {folder}
          </span>
        </div>
      ))}
    </div>
  )
}
