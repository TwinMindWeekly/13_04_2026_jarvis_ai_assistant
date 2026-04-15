import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Network } from 'lucide-react'
import { Badge } from 'react-bootstrap'
import { useGraph } from '../hooks/useGraph'
import GraphLeftPanel from './GraphLeftPanel'
import GraphCanvas from './GraphCanvas'
import GraphChatPanel from './GraphChatPanel'

/**
 * GraphPage — full-page Obsidian-style 3-panel layout for the knowledge graph.
 *
 * Layout:
 *   [Left 280px]  [Center flex-1]  [Right 360px]
 *   Search/Docs    Graph Canvas     AI Chat
 *
 * Replaces the old GraphPanel modal. Rendered by App.jsx when viewMode='graph'.
 */
export default function GraphPage({ onBack, settings }) {
  const { t } = useTranslation()
  const { data, loading, error } = useGraph({ enabled: true })
  const [selected, setSelected] = useState(null)
  const [highlighted, setHighlighted] = useState([])

  return (
    <div className="graph-page">
      {/* ── Header bar ── */}
      <div className="graph-page-header">
        <button className="graph-page-back-btn" onClick={onBack}>
          <ArrowLeft size={18} />
          <span className="d-none d-md-inline">{t('graph.back', 'Back to Chat')}</span>
        </button>

        <div className="graph-page-title">
          <Network size={18} />
          <span>{t('graph.pageTitle', 'Graph View')}</span>
        </div>

        <div className="graph-page-stats">
          {data.meta && (
            <>
              <Badge bg="secondary">
                {data.meta.total_docs || 0} {t('graph.nodes', 'docs')}
              </Badge>
              <Badge bg="secondary">
                {data.meta.total_links || 0} {t('graph.links', 'links')}
              </Badge>
            </>
          )}
        </div>
      </div>

      {/* ── 3-panel body ── */}
      <div className="graph-page-body">
        <GraphLeftPanel
          nodes={data.nodes}
          links={data.links}
          selected={selected}
          onSelectNode={setSelected}
        />

        <GraphCanvas
          data={data}
          loading={loading}
          error={error}
          selected={selected}
          highlighted={highlighted}
          onSelectNode={setSelected}
        />

        <GraphChatPanel
          settings={settings}
          graphNodes={data.nodes}
          onHighlightNodes={setHighlighted}
          onSelectNode={setSelected}
        />
      </div>
    </div>
  )
}
