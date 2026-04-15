import { Form, InputGroup, Button, Badge } from 'react-bootstrap'
import { useTranslation } from 'react-i18next'
import { Search, Maximize2, RefreshCw } from 'lucide-react'

/**
 * GraphToolbar — search input, similarity threshold slider, zoom-to-fit,
 * force-rebuild buttons, plus a small badge showing node/link counts.
 */
export default function GraphToolbar({
  threshold,
  onThresholdChange,
  search,
  onSearchChange,
  onZoomToFit,
  onRebuild,
  stats,
}) {
  const { t } = useTranslation()

  return (
    <div
      className="d-flex align-items-center gap-3 px-3 py-2"
      style={{
        background: '#1a1b22',
        borderBottom: '1px solid #2a2b33',
        flexWrap: 'wrap',
      }}
    >
      <InputGroup size="sm" style={{ maxWidth: 280 }}>
        <InputGroup.Text style={{ background: '#0f1014', borderColor: '#2a2b33' }}>
          <Search size={14} />
        </InputGroup.Text>
        <Form.Control
          placeholder={t('graph.searchPlaceholder', 'Filter nodes...')}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          style={{ background: '#0f1014', color: '#eee', borderColor: '#2a2b33' }}
        />
      </InputGroup>

      <div
        className="d-flex align-items-center gap-2"
        style={{ minWidth: 220 }}
      >
        <Form.Label className="mb-0" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
          {t('graph.threshold', 'Link threshold')}: {threshold.toFixed(2)}
        </Form.Label>
        <Form.Range
          min={0.3}
          max={0.9}
          step={0.05}
          value={threshold}
          onChange={(e) => onThresholdChange(parseFloat(e.target.value))}
          style={{ flex: 1 }}
        />
      </div>

      <Button size="sm" variant="outline-light" onClick={onZoomToFit}>
        <Maximize2 size={14} className="me-1" />
        {t('graph.zoomToFit', 'Fit')}
      </Button>

      <Button size="sm" variant="outline-light" onClick={onRebuild} title="Recompute graph">
        <RefreshCw size={14} className="me-1" />
        {t('graph.rebuild', 'Rebuild')}
      </Button>

      {stats && (
        <div className="ms-auto d-flex align-items-center gap-2" style={{ fontSize: 12 }}>
          <Badge bg="secondary">
            {stats.total_docs || 0} {t('graph.nodes', 'docs')}
          </Badge>
          <Badge bg="secondary">
            {stats.total_links || 0} {t('graph.links', 'links')}
          </Badge>
          {stats.cached && (
            <Badge bg="info" title="Served from cache">
              {t('graph.cached', 'cached')}
            </Badge>
          )}
        </div>
      )}
    </div>
  )
}
