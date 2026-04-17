import { useCallback, useEffect, useRef, useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import Badge from 'react-bootstrap/Badge'
import Tabs from 'react-bootstrap/Tabs'
import Tab from 'react-bootstrap/Tab'
import {
  ArrowLeft, Loader2, Upload, Plus, Trash2, Download, FileText,
  Star, StarOff, X, Eye,
} from 'lucide-react'
import { cvsAPI } from '../services/api'

const TEMPLATE_OPTIONS = {
  cv: [
    { value: 'minimal', label: 'Minimal' },
    { value: 'modern', label: 'Modern (two-column)' },
  ],
  portfolio: [
    { value: 'portfolio_minimal', label: 'Portfolio — Minimal' },
    { value: 'minimal', label: 'Minimal' },
  ],
}

const EMPTY_SECTIONS = {
  contact: { full_name: '', email: '', phone: '', location: '', website: '', linkedin: '', github: '' },
  summary: '',
  experience: [],
  education: [],
  skills: [],
  projects: [],
  certifications: [],
  languages: [],
  custom: [],
}

// -----------------------------------------------------------------------
// Chip editor for flat string arrays
// -----------------------------------------------------------------------

function ChipList({ values, onChange, placeholder = 'Add item' }) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const v = draft.trim()
    if (!v) return
    if (values.includes(v)) { setDraft(''); return }
    onChange([...values, v])
    setDraft('')
  }
  return (
    <div>
      <div className="d-flex flex-wrap gap-1 mb-2">
        {values.map((v) => (
          <Badge key={v} bg="secondary" style={{ fontSize: '0.8rem', padding: '4px 8px' }} className="d-flex align-items-center gap-1">
            {v}
            <X size={12} style={{ cursor: 'pointer' }} onClick={() => onChange(values.filter((x) => x !== v))} />
          </Badge>
        ))}
      </div>
      <div className="d-flex gap-2">
        <Form.Control
          placeholder={placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
        />
        <Button variant="outline-secondary" onClick={add}>Add</Button>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------
// Generic repeater for object arrays
// -----------------------------------------------------------------------

function Repeater({ items, onChange, blank, fields, label }) {
  return (
    <div className="d-flex flex-column gap-2">
      {items.map((item, idx) => (
        <div key={idx} className="p-2" style={{ border: '1px solid rgba(255,255,255,0.08)', borderRadius: 6 }}>
          <div className="d-flex justify-content-end mb-1">
            <Button size="sm" variant="outline-danger" onClick={() => onChange(items.filter((_, i) => i !== idx))}>
              <Trash2 size={12} />
            </Button>
          </div>
          <div className="d-flex flex-column gap-2">
            {fields.map((f) => (
              <div key={f.key}>
                <Form.Label className="small text-muted">{f.label}</Form.Label>
                {f.type === 'textarea' ? (
                  <Form.Control
                    as="textarea"
                    rows={2}
                    value={item[f.key] || ''}
                    onChange={(e) => onChange(items.map((it, i) => i === idx ? { ...it, [f.key]: e.target.value } : it))}
                  />
                ) : f.type === 'chips' ? (
                  <ChipList
                    values={item[f.key] || []}
                    onChange={(v) => onChange(items.map((it, i) => i === idx ? { ...it, [f.key]: v } : it))}
                    placeholder={`Add ${f.label.toLowerCase()}`}
                  />
                ) : (
                  <Form.Control
                    value={item[f.key] || ''}
                    onChange={(e) => onChange(items.map((it, i) => i === idx ? { ...it, [f.key]: e.target.value } : it))}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
      <Button
        size="sm"
        variant="outline-primary"
        onClick={() => onChange([...items, { ...blank }])}
      >
        <Plus size={12} className="me-1" /> Add {label}
      </Button>
    </div>
  )
}

// -----------------------------------------------------------------------
// Main editor form
// -----------------------------------------------------------------------

function CVEditor({ cv, onChange, onExport, onPreview, exporting }) {
  const s = cv.sections || EMPTY_SECTIONS
  const setSections = (updater) => {
    const next = typeof updater === 'function' ? updater(s) : updater
    onChange({ ...cv, sections: next })
  }
  const setContact = (k, v) => setSections({ ...s, contact: { ...s.contact, [k]: v } })

  return (
    <div className="d-flex flex-column gap-3">
      <div className="d-flex gap-2 align-items-center">
        <Form.Control
          placeholder="CV title"
          value={cv.title || ''}
          onChange={(e) => onChange({ ...cv, title: e.target.value })}
          style={{ fontWeight: 600 }}
        />
        <Form.Select
          value={cv.template}
          onChange={(e) => onChange({ ...cv, template: e.target.value })}
          style={{ maxWidth: 220 }}
        >
          {(TEMPLATE_OPTIONS[cv.kind] || TEMPLATE_OPTIONS.cv).map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </Form.Select>
        <Button variant="outline-secondary" onClick={onPreview} title="Preview HTML">
          <Eye size={14} />
        </Button>
        <Button variant="primary" onClick={onExport} disabled={exporting}>
          {exporting ? <Loader2 size={14} className="animate-spin me-2" /> : <Download size={14} className="me-2" />}
          Export PDF
        </Button>
      </div>

      <Tabs defaultActiveKey="contact" id="cv-editor-tabs">
        <Tab eventKey="contact" title="Contact">
          <div className="row g-2 pt-3">
            {['full_name', 'email', 'phone', 'location', 'website', 'linkedin', 'github'].map((k) => (
              <Form.Group className="col-md-6" key={k}>
                <Form.Label className="small text-muted text-capitalize">{k.replace('_', ' ')}</Form.Label>
                <Form.Control value={s.contact?.[k] || ''} onChange={(e) => setContact(k, e.target.value)} />
              </Form.Group>
            ))}
          </div>
        </Tab>

        <Tab eventKey="summary" title="Summary">
          <Form.Control
            as="textarea"
            rows={4}
            className="mt-3"
            value={s.summary || ''}
            onChange={(e) => setSections({ ...s, summary: e.target.value })}
          />
        </Tab>

        <Tab eventKey="experience" title={`Experience (${s.experience?.length || 0})`}>
          <div className="pt-3">
            <Repeater
              items={s.experience || []}
              onChange={(v) => setSections({ ...s, experience: v })}
              blank={{ company: '', title: '', start: '', end: '', location: '', bullets: [] }}
              fields={[
                { key: 'title', label: 'Title' },
                { key: 'company', label: 'Company' },
                { key: 'start', label: 'Start' },
                { key: 'end', label: 'End' },
                { key: 'location', label: 'Location' },
                { key: 'bullets', label: 'Bullets', type: 'chips' },
              ]}
              label="experience"
            />
          </div>
        </Tab>

        <Tab eventKey="education" title={`Education (${s.education?.length || 0})`}>
          <div className="pt-3">
            <Repeater
              items={s.education || []}
              onChange={(v) => setSections({ ...s, education: v })}
              blank={{ school: '', degree: '', field: '', start: '', end: '', gpa: '' }}
              fields={[
                { key: 'school', label: 'School' },
                { key: 'degree', label: 'Degree' },
                { key: 'field', label: 'Field' },
                { key: 'start', label: 'Start' },
                { key: 'end', label: 'End' },
                { key: 'gpa', label: 'GPA' },
              ]}
              label="education"
            />
          </div>
        </Tab>

        <Tab eventKey="skills" title={`Skills (${s.skills?.length || 0})`}>
          <div className="pt-3">
            <ChipList values={s.skills || []} onChange={(v) => setSections({ ...s, skills: v })} placeholder="Add skill" />
          </div>
        </Tab>

        <Tab eventKey="projects" title={`Projects (${s.projects?.length || 0})`}>
          <div className="pt-3">
            <Repeater
              items={s.projects || []}
              onChange={(v) => setSections({ ...s, projects: v })}
              blank={{ name: '', url: '', description: '', tech: [] }}
              fields={[
                { key: 'name', label: 'Name' },
                { key: 'url', label: 'URL' },
                { key: 'description', label: 'Description', type: 'textarea' },
                { key: 'tech', label: 'Tech', type: 'chips' },
              ]}
              label="project"
            />
          </div>
        </Tab>

        <Tab eventKey="certs" title={`Certifications (${s.certifications?.length || 0})`}>
          <div className="pt-3">
            <Repeater
              items={s.certifications || []}
              onChange={(v) => setSections({ ...s, certifications: v })}
              blank={{ name: '', issuer: '', date: '' }}
              fields={[
                { key: 'name', label: 'Name' },
                { key: 'issuer', label: 'Issuer' },
                { key: 'date', label: 'Date' },
              ]}
              label="certification"
            />
          </div>
        </Tab>

        <Tab eventKey="languages" title={`Languages (${s.languages?.length || 0})`}>
          <div className="pt-3">
            <Repeater
              items={s.languages || []}
              onChange={(v) => setSections({ ...s, languages: v })}
              blank={{ name: '', level: '' }}
              fields={[
                { key: 'name', label: 'Language' },
                { key: 'level', label: 'Level (Native/Fluent/…)' },
              ]}
              label="language"
            />
          </div>
        </Tab>

        <Tab eventKey="custom" title={`Custom (${s.custom?.length || 0})`}>
          <div className="pt-3">
            <Repeater
              items={s.custom || []}
              onChange={(v) => setSections({ ...s, custom: v })}
              blank={{ heading: '', body_markdown: '' }}
              fields={[
                { key: 'heading', label: 'Heading' },
                { key: 'body_markdown', label: 'Body (Markdown)', type: 'textarea' },
              ]}
              label="section"
            />
          </div>
        </Tab>
      </Tabs>
    </div>
  )
}

// -----------------------------------------------------------------------
// CVsPage — list + editor
// -----------------------------------------------------------------------

export default function CVsPage({ onBack }) {
  const [cvs, setCvs] = useState([])
  const [loading, setLoading] = useState(false)
  const [kindFilter, setKindFilter] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [draft, setDraft] = useState(null)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const fileInputRef = useRef(null)
  const saveTimer = useRef(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await cvsAPI.list(kindFilter || undefined)
      setCvs(data?.cvs || [])
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [kindFilter])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!selectedId) { setDraft(null); return }
    const cv = cvs.find((c) => c.id === selectedId)
    if (cv) setDraft(cv)
  }, [selectedId, cvs])

  // Debounced autosave
  const scheduleSave = useCallback((next) => {
    setDraft(next)
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      if (!next?.id) return
      setSaving(true)
      try {
        const { data } = await cvsAPI.update(next.id, {
          title: next.title,
          template: next.template,
          sections: next.sections,
        })
        setCvs((prev) => prev.map((c) => c.id === data.id ? data : c))
      } catch (err) {
        setError(err?.response?.data?.detail || err.message)
      } finally {
        setSaving(false)
      }
    }, 350)
  }, [])

  const createNew = async (kind = 'cv') => {
    try {
      const { data } = await cvsAPI.create({
        title: kind === 'portfolio' ? 'New Portfolio' : 'New CV',
        kind,
        template: kind === 'portfolio' ? 'portfolio_minimal' : 'minimal',
      })
      await load()
      setSelectedId(data.id)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    }
  }

  const uploadFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    try {
      const { data } = await cvsAPI.upload(file, kindFilter || 'cv')
      await load()
      setSelectedId(data.id)
      setMessage(`Imported CV — ${(data.sections?.skills || []).length} skills extracted.`)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const removeCV = async (id) => {
    if (!confirm('Delete this CV?')) return
    try {
      await cvsAPI.remove(id)
      if (selectedId === id) setSelectedId(null)
      load()
    } catch (err) { setError(err?.response?.data?.detail || err.message) }
  }

  const toggleDefault = async (cv) => {
    try {
      await cvsAPI.update(cv.id, { is_default: !cv.is_default })
      load()
    } catch (err) { setError(err?.response?.data?.detail || err.message) }
  }

  const exportPdf = async () => {
    if (!draft?.id) return
    setExporting(true)
    try {
      const { data } = await cvsAPI.exportPdf(draft.id)
      const url = data?.download_url || cvsAPI.downloadUrl(draft.id)
      window.open(url, '_blank', 'noreferrer')
      setMessage('PDF ready — opened in new tab.')
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setExporting(false)
    }
  }

  const openPreview = () => {
    if (!draft?.id) return
    window.open(cvsAPI.previewUrl(draft.id), '_blank', 'noreferrer')
  }

  return (
    <main className="flex-grow-1 d-flex flex-column" style={{ height: '100vh', overflow: 'hidden' }}>
      <header className="chat-header">
        <button onClick={onBack} className="sidebar-icon-btn" aria-label="Back">
          <ArrowLeft size={20} />
        </button>
        <h3 className="m-0 ms-2 flex-grow-1" style={{ fontSize: '1rem', fontWeight: 600 }}>
          CVs & Portfolios
        </h3>
        {saving && <small className="text-muted me-2">Saving…</small>}
      </header>

      <div className="flex-grow-1 d-flex" style={{ overflow: 'hidden' }}>
        {/* Left: list */}
        <aside
          style={{
            width: 320,
            minWidth: 280,
            borderRight: '1px solid rgba(255,255,255,0.08)',
            overflowY: 'auto',
            padding: 12,
          }}
        >
          <div className="d-flex gap-2 mb-2">
            <Form.Select
              size="sm"
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value)}
            >
              <option value="">All</option>
              <option value="cv">CVs</option>
              <option value="portfolio">Portfolios</option>
            </Form.Select>
            <Button size="sm" variant="outline-primary" onClick={() => createNew('cv')} title="New CV">
              <Plus size={12} />
            </Button>
            <Button size="sm" variant="outline-secondary" onClick={() => fileInputRef.current?.click()} disabled={uploading} title="Upload">
              {uploading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={uploadFile}
              style={{ display: 'none' }}
            />
          </div>

          <Button size="sm" variant="outline-secondary" className="w-100 mb-2" onClick={() => createNew('portfolio')}>
            <Plus size={12} className="me-1" /> New Portfolio
          </Button>

          {loading ? (
            <div className="d-flex justify-content-center py-3"><Loader2 className="animate-spin" size={18} /></div>
          ) : cvs.length === 0 ? (
            <div className="text-center text-muted small py-3">No CVs yet. Create one or upload.</div>
          ) : (
            <div className="d-flex flex-column gap-1">
              {cvs.map((cv) => (
                <div
                  key={cv.id}
                  onClick={() => setSelectedId(cv.id)}
                  style={{
                    padding: 8,
                    borderRadius: 6,
                    background: selectedId === cv.id ? 'rgba(99,102,241,0.18)' : 'rgba(255,255,255,0.02)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    cursor: 'pointer',
                  }}
                >
                  <div className="d-flex align-items-center justify-content-between">
                    <div style={{ minWidth: 0 }} className="d-flex align-items-center gap-1">
                      <FileText size={12} style={{ color: '#94a3b8' }} />
                      <strong style={{ fontSize: '0.85rem' }}>{cv.title}</strong>
                      {cv.is_default && <Star size={12} style={{ color: '#f6c643' }} />}
                    </div>
                    <div className="d-flex gap-1">
                      <button
                        className="btn btn-link p-0"
                        onClick={(e) => { e.stopPropagation(); toggleDefault(cv) }}
                        style={{ color: cv.is_default ? '#f6c643' : '#666' }}
                        title={cv.is_default ? 'Default' : 'Set default'}
                      >
                        {cv.is_default ? <Star size={12} /> : <StarOff size={12} />}
                      </button>
                      <button
                        className="btn btn-link p-0 text-danger"
                        onClick={(e) => { e.stopPropagation(); removeCV(cv.id) }}
                        title="Delete"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                  <div className="d-flex gap-1 mt-1 flex-wrap">
                    <Badge bg="secondary" style={{ fontSize: '0.65rem' }}>{cv.kind}</Badge>
                    <Badge bg="light" text="dark" style={{ fontSize: '0.65rem' }}>{cv.template}</Badge>
                    {cv.tailored_for_job_id && (
                      <Badge bg="info" style={{ fontSize: '0.65rem' }}>tailored</Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </aside>

        {/* Right: editor */}
        <section style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {message && <div className="text-success small mb-2">{message}</div>}
          {error && <div className="text-danger small mb-2">{error}</div>}
          {!draft ? (
            <div className="text-center text-muted py-5">
              Select a CV on the left, create a new one, or upload an existing résumé.
            </div>
          ) : (
            <CVEditor
              cv={draft}
              onChange={scheduleSave}
              onExport={exportPdf}
              onPreview={openPreview}
              exporting={exporting}
            />
          )}
        </section>
      </div>
    </main>
  )
}
