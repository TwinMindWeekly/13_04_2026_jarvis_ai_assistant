import { useCallback, useEffect, useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import Modal from 'react-bootstrap/Modal'
import Badge from 'react-bootstrap/Badge'
import { Loader2, Plus, Trash2, Wifi, Star, StarOff } from 'lucide-react'
import { emailAccountsAPI } from '../services/api'

const EMPTY_FORM = {
  label: '',
  email_address: '',
  imap_host: 'imap.gmail.com',
  imap_port: 993,
  imap_user: '',
  imap_password: '',
  smtp_host: 'smtp.gmail.com',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  is_default: false,
  sync_enabled: true,
}

export default function EmailAccountsSection() {
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [testingId, setTestingId] = useState(null)
  const [testResult, setTestResult] = useState(null)
  const [error, setError] = useState('')

  const fetchAccounts = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await emailAccountsAPI.list()
      setAccounts(data?.accounts || [])
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAccounts() }, [fetchAccounts])

  const openCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setError('')
    setShowForm(true)
  }

  const openEdit = (acct) => {
    setEditingId(acct.id)
    setForm({
      ...EMPTY_FORM,
      label: acct.label || '',
      email_address: acct.email_address || '',
      imap_host: acct.imap_host || 'imap.gmail.com',
      imap_port: acct.imap_port || 993,
      imap_user: acct.imap_user || '',
      imap_password: '',
      smtp_host: acct.smtp_host || 'smtp.gmail.com',
      smtp_port: acct.smtp_port || 587,
      smtp_user: acct.smtp_user || '',
      smtp_password: '',
      is_default: acct.is_default,
      sync_enabled: acct.sync_enabled,
    })
    setError('')
    setShowForm(true)
  }

  const submit = async () => {
    setSaving(true)
    setError('')
    try {
      const payload = { ...form }
      if (!payload.imap_password) delete payload.imap_password
      if (!payload.smtp_password) delete payload.smtp_password
      if (editingId) {
        await emailAccountsAPI.update(editingId, payload)
      } else {
        await emailAccountsAPI.create(payload)
      }
      setShowForm(false)
      fetchAccounts()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!confirm('Delete this email account?')) return
    try {
      await emailAccountsAPI.remove(id)
      fetchAccounts()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    }
  }

  const test = async (id) => {
    setTestingId(id)
    setTestResult(null)
    try {
      const { data } = await emailAccountsAPI.test(id)
      setTestResult({ id, ok: data.ok, error: data.error })
    } catch (err) {
      setTestResult({ id, ok: false, error: err?.response?.data?.detail || err.message })
    } finally {
      setTestingId(null)
    }
  }

  const toggleDefault = async (acct) => {
    try {
      await emailAccountsAPI.update(acct.id, { is_default: !acct.is_default })
      fetchAccounts()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    }
  }

  return (
    <div className="d-flex flex-column gap-3">
      <div className="d-flex justify-content-between align-items-center">
        <small style={{ color: '#888' }}>
          Configure IMAP/SMTP accounts. Passwords are encrypted at rest.
        </small>
        <Button size="sm" variant="outline-primary" onClick={openCreate}>
          <Plus size={14} className="me-1" /> Add account
        </Button>
      </div>

      {error && (
        <div className="text-danger" style={{ fontSize: '0.8rem' }}>{error}</div>
      )}

      {loading ? (
        <div className="d-flex justify-content-center py-3">
          <Loader2 size={18} className="animate-spin" style={{ color: '#888' }} />
        </div>
      ) : accounts.length === 0 ? (
        <div className="text-center py-3" style={{ color: '#888', fontSize: '0.85rem' }}>
          No email accounts configured yet.
        </div>
      ) : (
        <div className="d-flex flex-column gap-2">
          {accounts.map((acct) => {
            const testing = testingId === acct.id
            const lastResult = testResult?.id === acct.id ? testResult : null
            return (
              <div
                key={acct.id}
                className="d-flex flex-column"
                style={{
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 8,
                  padding: 10,
                  background: 'rgba(255,255,255,0.02)',
                }}
              >
                <div className="d-flex justify-content-between align-items-center gap-2">
                  <div className="d-flex align-items-center gap-2" style={{ minWidth: 0 }}>
                    <button
                      className="btn btn-link p-0"
                      onClick={() => toggleDefault(acct)}
                      style={{ color: acct.is_default ? '#f6c643' : '#666' }}
                      title={acct.is_default ? 'Default account' : 'Set as default'}
                    >
                      {acct.is_default ? <Star size={14} /> : <StarOff size={14} />}
                    </button>
                    <div style={{ minWidth: 0 }}>
                      <div className="d-flex align-items-center gap-2">
                        <strong style={{ fontSize: '0.9rem' }}>{acct.label}</strong>
                        {acct.sync_enabled ? (
                          <Badge bg="success" style={{ fontSize: '0.65rem' }}>sync</Badge>
                        ) : (
                          <Badge bg="secondary" style={{ fontSize: '0.65rem' }}>paused</Badge>
                        )}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#888' }}>
                        {acct.email_address || acct.imap_user} · {acct.imap_host}
                      </div>
                    </div>
                  </div>
                  <div className="d-flex gap-1">
                    <Button
                      size="sm"
                      variant="outline-secondary"
                      onClick={() => test(acct.id)}
                      disabled={testing}
                      title="Test connection"
                    >
                      {testing ? <Loader2 size={12} className="animate-spin" /> : <Wifi size={12} />}
                    </Button>
                    <Button size="sm" variant="outline-secondary" onClick={() => openEdit(acct)}>
                      Edit
                    </Button>
                    <Button size="sm" variant="outline-danger" onClick={() => remove(acct.id)}>
                      <Trash2 size={12} />
                    </Button>
                  </div>
                </div>
                {lastResult && (
                  <div
                    className="mt-2"
                    style={{
                      fontSize: '0.75rem',
                      color: lastResult.ok ? '#34d399' : '#f87171',
                    }}
                  >
                    {lastResult.ok ? 'Connection OK.' : `Failed: ${lastResult.error}`}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <Modal show={showForm} onHide={() => setShowForm(false)} centered data-bs-theme="dark">
        <Modal.Header closeButton>
          <Modal.Title as="h5" style={{ fontSize: '0.95rem' }}>
            {editingId ? 'Edit email account' : 'Add email account'}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <div className="d-flex flex-column gap-3">
            <Form.Group>
              <Form.Label>Label</Form.Label>
              <Form.Control
                placeholder="work / personal"
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
              />
            </Form.Group>
            <Form.Group>
              <Form.Label>Email address</Form.Label>
              <Form.Control
                placeholder="you@gmail.com"
                value={form.email_address}
                onChange={(e) => setForm({ ...form, email_address: e.target.value })}
              />
            </Form.Group>
            <div className="row g-2">
              <Form.Group className="col-8">
                <Form.Label>IMAP host</Form.Label>
                <Form.Control
                  value={form.imap_host}
                  onChange={(e) => setForm({ ...form, imap_host: e.target.value })}
                />
              </Form.Group>
              <Form.Group className="col-4">
                <Form.Label>Port</Form.Label>
                <Form.Control
                  type="number"
                  value={form.imap_port}
                  onChange={(e) => setForm({ ...form, imap_port: Number(e.target.value) })}
                />
              </Form.Group>
            </div>
            <Form.Group>
              <Form.Label>IMAP user</Form.Label>
              <Form.Control
                value={form.imap_user}
                onChange={(e) => setForm({ ...form, imap_user: e.target.value })}
              />
            </Form.Group>
            <Form.Group>
              <Form.Label>
                IMAP app password {editingId ? <small className="text-muted">(leave blank to keep)</small> : null}
              </Form.Label>
              <Form.Control
                type="password"
                value={form.imap_password}
                onChange={(e) => setForm({ ...form, imap_password: e.target.value })}
              />
            </Form.Group>
            <div className="row g-2">
              <Form.Group className="col-8">
                <Form.Label>SMTP host</Form.Label>
                <Form.Control
                  value={form.smtp_host}
                  onChange={(e) => setForm({ ...form, smtp_host: e.target.value })}
                />
              </Form.Group>
              <Form.Group className="col-4">
                <Form.Label>Port</Form.Label>
                <Form.Control
                  type="number"
                  value={form.smtp_port}
                  onChange={(e) => setForm({ ...form, smtp_port: Number(e.target.value) })}
                />
              </Form.Group>
            </div>
            <Form.Group>
              <Form.Label>SMTP user</Form.Label>
              <Form.Control
                value={form.smtp_user}
                onChange={(e) => setForm({ ...form, smtp_user: e.target.value })}
              />
            </Form.Group>
            <Form.Group>
              <Form.Label>
                SMTP password {editingId ? <small className="text-muted">(leave blank to keep)</small> : null}
              </Form.Label>
              <Form.Control
                type="password"
                value={form.smtp_password}
                onChange={(e) => setForm({ ...form, smtp_password: e.target.value })}
              />
            </Form.Group>
            <div className="d-flex gap-3">
              <Form.Check
                type="switch"
                id="email-is-default"
                label="Default account"
                checked={form.is_default}
                onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
              />
              <Form.Check
                type="switch"
                id="email-sync-enabled"
                label="Sync enabled"
                checked={form.sync_enabled}
                onChange={(e) => setForm({ ...form, sync_enabled: e.target.checked })}
              />
            </div>
            {error && (
              <div className="text-danger" style={{ fontSize: '0.8rem' }}>{error}</div>
            )}
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="outline-secondary" onClick={() => setShowForm(false)}>Cancel</Button>
          <Button variant="primary" onClick={submit} disabled={saving || !form.label}>
            {saving ? <Loader2 size={14} className="animate-spin" /> : 'Save'}
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  )
}
