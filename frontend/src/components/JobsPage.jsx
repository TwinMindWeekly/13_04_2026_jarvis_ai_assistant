import { useCallback, useEffect, useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import Badge from 'react-bootstrap/Badge'
import {
  ArrowLeft, Loader2, RefreshCw, Star, StarOff, ExternalLink, Filter, Plus, Trash2, Sparkles,
} from 'lucide-react'
import Modal from 'react-bootstrap/Modal'
import { jobsAPI, cvsAPI } from '../services/api'

const SOURCE_LABELS = {
  duckduckgo: 'DuckDuckGo',
  topcv: 'TopCV',
  itviec: 'ITviec',
  vietnamworks: 'VietnamWorks',
  remoteok: 'RemoteOK',
  weworkremotely: 'WeWorkRemotely',
}

function matchPct(score) {
  const pct = Math.round((Number(score) || 0) * 100)
  return `${pct}%`
}

function matchClass(score) {
  const s = Number(score) || 0
  if (s > 0.2) return 'success'
  if (s > 0.1) return 'warning'
  return 'secondary'
}

export default function JobsPage({ onBack, onOpenCVs }) {
  const [jobs, setJobs] = useState([])
  const [savedSearches, setSavedSearches] = useState([])
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [minScore, setMinScore] = useState('')
  const [savedOnly, setSavedOnly] = useState(false)
  const [newSearch, setNewSearch] = useState({ query: '', location: '' })
  // Tailor modal
  const [tailorJob, setTailorJob] = useState(null)
  const [tailorCVs, setTailorCVs] = useState([])
  const [tailorLoading, setTailorLoading] = useState(false)
  const [tailorBaseId, setTailorBaseId] = useState('')
  const [tailoring, setTailoring] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = {}
      if (sourceFilter) params.source = sourceFilter
      if (minScore) params.min_score = Number(minScore)
      if (savedOnly) params.saved_only = true
      const [{ data: jobsResp }, { data: searchesResp }] = await Promise.all([
        jobsAPI.list(params),
        jobsAPI.savedSearches(),
      ])
      setJobs(jobsResp?.jobs || [])
      setSavedSearches(searchesResp?.searches || [])
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [sourceFilter, minScore, savedOnly])

  useEffect(() => { load() }, [load])

  const refresh = async () => {
    setRefreshing(true)
    setError('')
    setMessage('')
    try {
      const { data } = await jobsAPI.refresh()
      setMessage(`Refreshed: ${data.inserted || 0} new, ${data.updated || 0} updated.`)
      load()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setRefreshing(false)
    }
  }

  const openTailor = async (job) => {
    setTailorJob(job)
    setTailorBaseId('')
    setTailorLoading(true)
    try {
      const { data } = await cvsAPI.list('cv')
      const list = data?.cvs || []
      setTailorCVs(list)
      const def = list.find((c) => c.is_default) || list[0]
      if (def) setTailorBaseId(def.id)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setTailorLoading(false)
    }
  }

  const submitTailor = async () => {
    if (!tailorJob || !tailorBaseId) return
    setTailoring(true)
    try {
      await cvsAPI.tailor(tailorBaseId, tailorJob.id)
      setMessage(`CV tailored for ${tailorJob.company || tailorJob.title}. Open CVs to review.`)
      setTailorJob(null)
      if (onOpenCVs) onOpenCVs()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setTailoring(false)
    }
  }

  const toggleSave = async (job) => {
    try {
      if (job.saved) {
        await jobsAPI.unsave(job.id)
      } else {
        await jobsAPI.save(job.id)
      }
      load()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    }
  }

  const addSavedSearch = async () => {
    if (!newSearch.query.trim()) return
    try {
      await jobsAPI.createSavedSearch({
        query: newSearch.query,
        location: newSearch.location,
      })
      setNewSearch({ query: '', location: '' })
      load()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    }
  }

  const removeSavedSearch = async (id) => {
    try {
      await jobsAPI.deleteSavedSearch(id)
      load()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    }
  }

  return (
    <main className="flex-grow-1 d-flex flex-column" style={{ height: '100vh', overflow: 'hidden' }}>
      <header className="chat-header">
        <button onClick={onBack} className="sidebar-icon-btn" aria-label="Back">
          <ArrowLeft size={20} />
        </button>
        <h3 className="m-0 ms-2 flex-grow-1" style={{ fontSize: '1rem', fontWeight: 600 }}>
          Jobs
        </h3>
        <Button variant="primary" onClick={refresh} disabled={refreshing}>
          {refreshing ? <Loader2 size={14} className="animate-spin me-2" /> : <RefreshCw size={14} className="me-2" />}
          {refreshing ? 'Refreshing…' : 'Refresh all'}
        </Button>
      </header>

      <div className="flex-grow-1 overflow-auto p-4" style={{ maxWidth: 1100, width: '100%', margin: '0 auto' }}>
        {/* Saved searches */}
        <section
          className="mb-4 p-3"
          style={{
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 10,
            background: 'rgba(255,255,255,0.02)',
          }}
        >
          <div className="d-flex align-items-center justify-content-between mb-2">
            <strong style={{ fontSize: '0.9rem' }}>Saved searches</strong>
            <small className="text-muted">Run automatically every day.</small>
          </div>

          <div className="d-flex flex-column gap-1 mb-2">
            {savedSearches.length === 0 && (
              <small className="text-muted">No saved searches yet. Add one below.</small>
            )}
            {savedSearches.map((s) => (
              <div
                key={s.id}
                className="d-flex align-items-center justify-content-between"
                style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(255,255,255,0.03)' }}
              >
                <div style={{ fontSize: '0.85rem' }}>
                  <strong>{s.query}</strong>
                  {s.location && <span className="text-muted"> · {s.location}</span>}
                </div>
                <Button
                  size="sm"
                  variant="outline-danger"
                  onClick={() => removeSavedSearch(s.id)}
                  title="Delete"
                >
                  <Trash2 size={12} />
                </Button>
              </div>
            ))}
          </div>

          <div className="d-flex gap-2">
            <Form.Control
              placeholder="Job title or keywords"
              value={newSearch.query}
              onChange={(e) => setNewSearch({ ...newSearch, query: e.target.value })}
            />
            <Form.Control
              placeholder="Location (optional)"
              value={newSearch.location}
              onChange={(e) => setNewSearch({ ...newSearch, location: e.target.value })}
              style={{ maxWidth: 220 }}
            />
            <Button variant="outline-primary" onClick={addSavedSearch}>
              <Plus size={14} className="me-1" /> Add
            </Button>
          </div>
        </section>

        {/* Filters */}
        <section className="mb-3 d-flex flex-wrap gap-2 align-items-center">
          <Filter size={14} style={{ color: '#888' }} />
          <Form.Select
            size="sm"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            style={{ maxWidth: 180 }}
          >
            <option value="">All sources</option>
            {Object.entries(SOURCE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </Form.Select>
          <Form.Control
            size="sm"
            type="number"
            step="0.05"
            min="0"
            max="1"
            placeholder="Min score (0–1)"
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
            style={{ maxWidth: 140 }}
          />
          <Form.Check
            type="switch"
            id="saved-only"
            label="Saved only"
            checked={savedOnly}
            onChange={(e) => setSavedOnly(e.target.checked)}
          />
        </section>

        {message && <div className="text-success small mb-2">{message}</div>}
        {error && <div className="text-danger small mb-2">{error}</div>}

        {loading ? (
          <div className="d-flex justify-content-center py-4">
            <Loader2 size={20} className="animate-spin" style={{ color: '#888' }} />
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-5 text-muted">
            No jobs tracked yet. Hit “Refresh all” after adding a saved search or filling in your profile.
          </div>
        ) : (
          <div className="d-flex flex-column gap-2">
            {jobs.map((job) => (
              <article
                key={job.id}
                className="p-3"
                style={{
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 10,
                  background: 'rgba(255,255,255,0.02)',
                }}
              >
                <div className="d-flex align-items-start justify-content-between gap-2">
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div className="d-flex align-items-center gap-2 flex-wrap">
                      <strong style={{ fontSize: '0.95rem' }}>{job.title || 'Untitled'}</strong>
                      <Badge bg={matchClass(job.match_score)} style={{ fontSize: '0.7rem' }}>
                        match {matchPct(job.match_score)}
                      </Badge>
                      <Badge bg="secondary" style={{ fontSize: '0.65rem' }}>
                        {SOURCE_LABELS[job.source] || job.source}
                      </Badge>
                      {job.remote && <Badge bg="info" style={{ fontSize: '0.65rem' }}>remote</Badge>}
                    </div>
                    <div className="d-flex gap-2 flex-wrap" style={{ fontSize: '0.82rem', color: '#aaa', marginTop: 4 }}>
                      {job.company && <span>{job.company}</span>}
                      {job.location && <span>· {job.location}</span>}
                      {job.salary && <span>· {job.salary}</span>}
                    </div>
                    {job.description && (
                      <p style={{ fontSize: '0.82rem', color: '#bbb', margin: '8px 0 0' }}>
                        {job.description}
                      </p>
                    )}
                  </div>
                  <div className="d-flex flex-column gap-1">
                    <Button
                      size="sm"
                      variant={job.saved ? 'warning' : 'outline-secondary'}
                      onClick={() => toggleSave(job)}
                      title={job.saved ? 'Unsave' : 'Save'}
                    >
                      {job.saved ? <Star size={12} /> : <StarOff size={12} />}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline-info"
                      onClick={() => openTailor(job)}
                      title="Tailor a CV for this job"
                    >
                      <Sparkles size={12} />
                    </Button>
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="btn btn-sm btn-outline-primary"
                    >
                      <ExternalLink size={12} />
                    </a>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      <Modal show={!!tailorJob} onHide={() => setTailorJob(null)} centered data-bs-theme="dark">
        <Modal.Header closeButton>
          <Modal.Title as="h5" style={{ fontSize: '0.95rem' }}>
            Tailor CV for {tailorJob?.company || tailorJob?.title}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {tailorLoading ? (
            <div className="d-flex justify-content-center py-3">
              <Loader2 size={18} className="animate-spin" />
            </div>
          ) : tailorCVs.length === 0 ? (
            <div className="text-muted small">
              You have no CVs yet. Go to <strong>CVs</strong> to create or upload one first.
            </div>
          ) : (
            <>
              <p className="small text-muted mb-2">
                Pick the CV to start from. The AI will clone it and rewrite the summary + bullets using
                this job's description. The original CV is never modified.
              </p>
              <Form.Select
                value={tailorBaseId}
                onChange={(e) => setTailorBaseId(e.target.value)}
              >
                {tailorCVs.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}{c.is_default ? ' (default)' : ''}
                  </option>
                ))}
              </Form.Select>
            </>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="outline-secondary" onClick={() => setTailorJob(null)}>Cancel</Button>
          <Button
            variant="primary"
            onClick={submitTailor}
            disabled={tailoring || !tailorBaseId || tailorCVs.length === 0}
          >
            {tailoring ? <Loader2 size={14} className="animate-spin me-2" /> : <Sparkles size={14} className="me-2" />}
            Tailor CV
          </Button>
        </Modal.Footer>
      </Modal>
    </main>
  )
}
