import { useCallback, useEffect, useRef, useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import Badge from 'react-bootstrap/Badge'
import { ArrowLeft, Upload, Loader2, Save, X } from 'lucide-react'
import { profileAPI } from '../services/api'

function ChipEditor({ label, values, onChange, placeholder }) {
  const [draft, setDraft] = useState('')

  const add = () => {
    const v = draft.trim()
    if (!v) return
    if (values.includes(v)) {
      setDraft('')
      return
    }
    onChange([...values, v])
    setDraft('')
  }

  const remove = (v) => onChange(values.filter((x) => x !== v))

  return (
    <Form.Group>
      <Form.Label>{label}</Form.Label>
      <div className="d-flex flex-wrap gap-1 mb-2">
        {values.length === 0 && (
          <small className="text-muted">No items yet.</small>
        )}
        {values.map((v) => (
          <Badge
            key={v}
            bg="secondary"
            className="d-flex align-items-center gap-1"
            style={{ cursor: 'default', fontSize: '0.8rem', padding: '4px 8px' }}
          >
            {v}
            <X size={12} style={{ cursor: 'pointer' }} onClick={() => remove(v)} />
          </Badge>
        ))}
      </div>
      <div className="d-flex gap-2">
        <Form.Control
          placeholder={placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              add()
            }
          }}
        />
        <Button variant="outline-secondary" onClick={add}>Add</Button>
      </div>
    </Form.Group>
  )
}

export default function ProfilePage({ onBack }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const fileInputRef = useRef(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await profileAPI.get()
      setProfile(data)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const updateField = (field, value) => {
    setProfile((prev) => ({ ...(prev || {}), [field]: value }))
  }

  const save = async () => {
    if (!profile) return
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const { data } = await profileAPI.update({
        full_name: profile.full_name,
        headline: profile.headline,
        summary: profile.summary,
        skills: profile.skills,
        preferred_titles: profile.preferred_titles,
        preferred_locations: profile.preferred_locations,
        preferred_remote: profile.preferred_remote,
      })
      setProfile(data)
      setMessage('Profile saved.')
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setSaving(false)
    }
  }

  const uploadCV = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    setMessage('')
    try {
      const { data } = await profileAPI.uploadCV(file)
      setProfile(data)
      setMessage(`CV uploaded. Extracted ${data.skills.length} skills and ${data.preferred_titles.length} titles.`)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <main className="flex-grow-1 d-flex flex-column" style={{ height: '100vh', overflow: 'hidden' }}>
      <header className="chat-header">
        <button onClick={onBack} className="sidebar-icon-btn" aria-label="Back">
          <ArrowLeft size={20} />
        </button>
        <h3 className="m-0 ms-2" style={{ fontSize: '1rem', fontWeight: 600 }}>
          Profile
        </h3>
      </header>

      <div className="flex-grow-1 overflow-auto p-4" style={{ maxWidth: 900, width: '100%', margin: '0 auto' }}>
        {loading ? (
          <div className="d-flex justify-content-center py-5">
            <Loader2 size={24} className="animate-spin" style={{ color: '#888' }} />
          </div>
        ) : (
          <div className="d-flex flex-column gap-4">
            {/* CV upload */}
            <div
              className="d-flex align-items-center justify-content-between"
              style={{
                padding: 14,
                borderRadius: 10,
                background: 'rgba(99,102,241,0.06)',
                border: '1px dashed rgba(99,102,241,0.3)',
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>Upload CV / Résumé</div>
                <small className="text-muted">
                  PDF, DOCX, or TXT. We'll extract skills, titles, and locations automatically.
                </small>
                {profile?.cv_path && (
                  <div style={{ fontSize: '0.75rem', color: '#4ade80', marginTop: 4 }}>
                    Current CV: {profile.cv_path.split(/[\\/]/).pop()}
                  </div>
                )}
              </div>
              <Button
                variant="primary"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? <Loader2 size={16} className="animate-spin me-2" /> : <Upload size={16} className="me-2" />}
                {uploading ? 'Uploading…' : 'Upload CV'}
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt,.md"
                onChange={uploadCV}
                style={{ display: 'none' }}
              />
            </div>

            {/* Details */}
            <Form.Group>
              <Form.Label>Full name</Form.Label>
              <Form.Control
                value={profile?.full_name || ''}
                onChange={(e) => updateField('full_name', e.target.value)}
              />
            </Form.Group>

            <Form.Group>
              <Form.Label>Headline</Form.Label>
              <Form.Control
                value={profile?.headline || ''}
                onChange={(e) => updateField('headline', e.target.value)}
                placeholder="Senior Python Engineer — 6 yrs backend"
              />
            </Form.Group>

            <Form.Group>
              <Form.Label>Summary</Form.Label>
              <Form.Control
                as="textarea"
                rows={3}
                value={profile?.summary || ''}
                onChange={(e) => updateField('summary', e.target.value)}
              />
            </Form.Group>

            <ChipEditor
              label="Skills"
              values={profile?.skills || []}
              onChange={(v) => updateField('skills', v)}
              placeholder="Add a skill"
            />

            <ChipEditor
              label="Preferred titles"
              values={profile?.preferred_titles || []}
              onChange={(v) => updateField('preferred_titles', v)}
              placeholder="Add a job title"
            />

            <ChipEditor
              label="Preferred locations"
              values={profile?.preferred_locations || []}
              onChange={(v) => updateField('preferred_locations', v)}
              placeholder="Add a city/region"
            />

            <Form.Check
              type="switch"
              id="preferred-remote"
              label="Prefer remote / WFH / distributed roles"
              checked={!!profile?.preferred_remote}
              onChange={(e) => updateField('preferred_remote', e.target.checked)}
            />

            {message && <div className="text-success small">{message}</div>}
            {error && <div className="text-danger small">{error}</div>}

            <div className="d-flex justify-content-end">
              <Button variant="primary" onClick={save} disabled={saving}>
                {saving ? <Loader2 size={16} className="animate-spin me-2" /> : <Save size={16} className="me-2" />}
                {saving ? 'Saving…' : 'Save profile'}
              </Button>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
