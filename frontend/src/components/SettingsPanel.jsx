import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Modal from 'react-bootstrap/Modal'
import Form from 'react-bootstrap/Form'
import Button from 'react-bootstrap/Button'
import Tab from 'react-bootstrap/Tab'
import Nav from 'react-bootstrap/Nav'
import ProgressBar from 'react-bootstrap/ProgressBar'
import Badge from 'react-bootstrap/Badge'
import { CheckCircle, XCircle, Loader2, Wifi, BarChart3, Settings } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { chatAPI, usageAPI } from '../services/api'

const PROVIDER_MODELS = {
  auto: [],
  groq: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'gemma2-9b-it'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  gemini: ['gemini-3.1-pro-high', 'gemini-3-pro-high', 'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-3-flash', 'gemini-3.1-flash-lite'],
  sambanova: ['Meta-Llama-3.3-70B-Instruct'],
  claude: ['claude-opus-4-6-thinking', 'claude-sonnet-4-6', 'claude-sonnet-4-20250514', 'claude-haiku-4-5-20251001'],
  ollama: ['huihui_ai/llama3.2-abliterate:3b'],
}

const LANGUAGES = [
  { code: 'en', label: 'EN', full: 'English' },
  { code: 'vi', label: 'VI', full: 'Tiếng Việt' },
]

function UsageTab() {
  const { t } = useTranslation()
  const [usage, setUsage] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchUsage = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await usageAPI.getUsage()
      setUsage(data)
    } catch {
      setUsage(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchUsage() }, [fetchUsage])

  const formatResetTime = (isoStr) => {
    if (!isoStr) return '-'
    try {
      const d = new Date(isoStr)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch { return isoStr }
  }

  const formatLastUsed = (isoStr) => {
    if (!isoStr) return t('usage.never', 'Never')
    try {
      const d = new Date(isoStr)
      const diff = Math.floor((Date.now() - d.getTime()) / 1000)
      if (diff < 60) return t('usage.justNow', 'Just now')
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
      return d.toLocaleDateString()
    } catch { return isoStr }
  }

  if (loading) {
    return (
      <div className="d-flex justify-content-center py-4">
        <Loader2 size={20} className="animate-spin" style={{ color: '#888' }} />
      </div>
    )
  }

  if (!usage || !usage.providers) {
    return (
      <div className="text-center py-4" style={{ color: '#888', fontSize: '0.85rem' }}>
        {t('usage.noData', 'No usage data yet. Send a message to start tracking.')}
      </div>
    )
  }

  const providerEntries = Object.entries(usage.providers)

  return (
    <div className="d-flex flex-column gap-3">
      <div className="d-flex justify-content-between align-items-center">
        <small style={{ color: '#888' }}>
          {t('usage.resetsAt', 'Daily reset')}: {formatResetTime(usage.resets_at)}
        </small>
        <Button size="sm" variant="outline-secondary" onClick={fetchUsage}>
          {t('usage.refresh', 'Refresh')}
        </Button>
      </div>

      {providerEntries.length === 0 && (
        <div className="text-center py-3" style={{ color: '#888', fontSize: '0.85rem' }}>
          {t('usage.noData', 'No usage data yet. Send a message to start tracking.')}
        </div>
      )}

      {providerEntries.map(([key, stats]) => {
        const limit = stats.daily_request_limit || 0
        const used = stats.requests_today || 0
        const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0
        const isExhausted = limit > 0 && used >= limit
        const hasError = !!stats.last_error

        return (
          <div key={key} className="usage-provider-card">
            <div className="d-flex justify-content-between align-items-center mb-1">
              <div className="d-flex align-items-center gap-2">
                <strong style={{ fontSize: '0.9rem', textTransform: 'capitalize' }}>
                  {stats.provider || key}
                </strong>
                {isExhausted && <Badge bg="danger" style={{ fontSize: '0.65rem' }}>Exhausted</Badge>}
                {hasError && !isExhausted && <Badge bg="warning" style={{ fontSize: '0.65rem' }}>Error</Badge>}
                {!hasError && !isExhausted && used > 0 && <Badge bg="success" style={{ fontSize: '0.65rem' }}>Active</Badge>}
              </div>
              <small style={{ color: '#888' }}>
                {formatLastUsed(stats.last_used_at)}
              </small>
            </div>

            <div style={{ fontSize: '0.75rem', color: '#aaa', marginBottom: 4 }}>
              {stats.model || '-'}
            </div>

            {limit > 0 ? (
              <>
                <ProgressBar
                  now={pct}
                  variant={pct > 80 ? 'danger' : pct > 50 ? 'warning' : 'info'}
                  style={{ height: 6, marginBottom: 4 }}
                />
                <div className="d-flex justify-content-between" style={{ fontSize: '0.72rem', color: '#888' }}>
                  <span>{used} / {limit} req/day</span>
                  <span>{pct}%</span>
                </div>
              </>
            ) : (
              <div style={{ fontSize: '0.72rem', color: '#888' }}>
                {used} requests today {limit === 0 ? '(no daily limit)' : ''}
              </div>
            )}

            {stats.tokens_in_today + stats.tokens_out_today > 0 && (
              <div style={{ fontSize: '0.72rem', color: '#666', marginTop: 2 }}>
                Tokens: {stats.tokens_in_today + stats.tokens_out_today} total
              </div>
            )}

            {hasError && (
              <div style={{ fontSize: '0.7rem', color: '#f87171', marginTop: 4, wordBreak: 'break-word' }}>
                {String(stats.last_error).slice(0, 120)}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function SettingsPanel({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  providers = [],
}) {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('settings')

  const [localProvider, setLocalProvider] = useState(settings?.provider ?? 'auto')
  const [localModel, setLocalModel] = useState(settings?.model ?? '')
  const [localLanguage, setLocalLanguage] = useState(settings?.language ?? 'en')
  const [localVoiceEnabled, setLocalVoiceEnabled] = useState(settings?.voiceEnabled !== false)
  const [testStatus, setTestStatus] = useState(null)
  const [testMessage, setTestMessage] = useState('')

  useEffect(() => {
    if (isOpen && settings) {
      setLocalProvider(settings.provider || 'auto')
      setLocalModel(settings.model || '')
      setLocalLanguage(settings.language)
      setLocalVoiceEnabled(settings.voiceEnabled !== false)
      setTestStatus(null)
      setTestMessage('')
    }
  }, [isOpen, settings])

  const handleProviderChange = (newProvider) => {
    setLocalProvider(newProvider)
    const models = PROVIDER_MODELS[newProvider] ?? []
    setLocalModel(models[0] ?? '')
    setTestStatus(null)
  }

  const handleSave = () => {
    onUpdateSettings({ provider: localProvider, model: localModel, language: localLanguage, voiceEnabled: localVoiceEnabled })
    onClose()
  }

  const handleTestConnection = async () => {
    setTestStatus('testing')
    setTestMessage('')
    try {
      await chatAPI.testProvider(localProvider === 'auto' ? 'groq' : localProvider, null)
      setTestStatus('success')
      setTestMessage(t('settings.success'))
    } catch (err) {
      setTestStatus('failed')
      const detail = err.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : err.message || t('settings.failed')
      setTestMessage(msg)
    }
  }

  const allProviders = Object.keys(PROVIDER_MODELS).map((p) => ({
    value: p,
    label: p === 'auto' ? 'Auto (fallback chain)' : p.charAt(0).toUpperCase() + p.slice(1),
  }))

  const availableModels = (PROVIDER_MODELS[localProvider] ?? []).map((m) => ({
    value: m,
    label: m,
  }))

  return (
    <Modal
      show={isOpen}
      onHide={onClose}
      centered
      className="settings-modal"
      data-bs-theme="dark"
    >
      <Modal.Header closeButton>
        <Modal.Title
          as="h2"
          style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}
        >
          {t('settings.title')}
        </Modal.Title>
      </Modal.Header>

      <Modal.Body className="px-4 py-3">
        <Tab.Container activeKey={activeTab} onSelect={setActiveTab}>
          <Nav variant="pills" className="mb-3 gap-2">
            <Nav.Item>
              <Nav.Link eventKey="settings" className="d-flex align-items-center gap-1" style={{ fontSize: '0.82rem' }}>
                <Settings size={14} /> {t('settings.title', 'Settings')}
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link eventKey="usage" className="d-flex align-items-center gap-1" style={{ fontSize: '0.82rem' }}>
                <BarChart3 size={14} /> {t('usage.title', 'Usage')}
              </Nav.Link>
            </Nav.Item>
          </Nav>

          <Tab.Content>
            <Tab.Pane eventKey="settings">
              <div className="d-flex flex-column gap-4">
                {/* Provider */}
                <Form.Group>
                  <Form.Label>{t('settings.provider')}</Form.Label>
                  <Form.Select
                    value={localProvider}
                    onChange={(e) => handleProviderChange(e.target.value)}
                  >
                    {allProviders.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </Form.Select>
                </Form.Group>

                {/* Model — hidden when auto */}
                {localProvider !== 'auto' && (
                  <Form.Group>
                    <Form.Label>{t('settings.model')}</Form.Label>
                    <Form.Select
                      value={localModel}
                      onChange={(e) => setLocalModel(e.target.value)}
                    >
                      {availableModels.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </Form.Select>
                  </Form.Group>
                )}

                {localProvider === 'auto' && (
                  <div style={{ fontSize: '0.78rem', color: '#888', padding: '8px 12px', background: 'rgba(99,102,241,0.08)', borderRadius: 8 }}>
                    Auto mode: Groq → Gemini → SambaNova → OpenAI → Claude → Ollama.
                    Automatically switches on quota errors.
                  </div>
                )}

                {/* Language */}
                <Form.Group>
                  <Form.Label>{t('settings.language')}</Form.Label>
                  <div className="d-flex gap-2">
                    {LANGUAGES.map((lang) => (
                      <button
                        key={lang.code}
                        onClick={() => setLocalLanguage(lang.code)}
                        className={`lang-btn${localLanguage === lang.code ? ' active' : ''}`}
                      >
                        <span style={{ fontWeight: 700 }}>{lang.label}</span>
                        <span style={{ fontSize: '0.75rem', opacity: 0.7 }}>{lang.full}</span>
                      </button>
                    ))}
                  </div>
                </Form.Group>

                {/* Voice */}
                <Form.Group>
                  <Form.Label>Voice</Form.Label>
                  <Form.Check
                    type="switch"
                    id="voice-toggle"
                    label={localVoiceEnabled ? 'Voice enabled (mic + TTS)' : 'Voice disabled'}
                    checked={localVoiceEnabled}
                    onChange={(e) => setLocalVoiceEnabled(e.target.checked)}
                    style={{ color: 'var(--text-secondary)' }}
                  />
                </Form.Group>

                {/* Test connection */}
                <Form.Group className="d-flex flex-column gap-2">
                  <Button
                    variant="outline-secondary"
                    onClick={handleTestConnection}
                    disabled={testStatus === 'testing'}
                    className="d-flex align-items-center justify-content-center gap-2 w-100"
                    style={{ padding: '10px 16px' }}
                  >
                    {testStatus === 'testing' ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Wifi size={14} />
                    )}
                    {testStatus === 'testing' ? t('settings.testing') : t('settings.test')}
                  </Button>

                  <AnimatePresence>
                    {testStatus && testStatus !== 'testing' && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.18 }}
                        style={{ overflow: 'hidden' }}
                      >
                        <div className={`test-result${testStatus === 'success' ? ' success' : ' failed'}`}>
                          {testStatus === 'success' ? (
                            <CheckCircle size={14} style={{ flexShrink: 0 }} />
                          ) : (
                            <XCircle size={14} style={{ flexShrink: 0 }} />
                          )}
                          <span className="text-truncate">{testMessage}</span>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </Form.Group>
              </div>
            </Tab.Pane>

            <Tab.Pane eventKey="usage">
              <UsageTab />
            </Tab.Pane>
          </Tab.Content>
        </Tab.Container>
      </Modal.Body>

      <Modal.Footer className="d-flex justify-content-end gap-2 px-4 py-3">
        <button
          onClick={onClose}
          className="sidebar-nav-item"
          style={{ width: 'auto', padding: '8px 20px' }}
        >
          Cancel
        </button>
        <motion.button
          onClick={handleSave}
          className="px-4 py-2 rounded-2 fw-medium text-white border-0"
          style={{
            background: 'var(--accent)',
            cursor: 'pointer',
            fontSize: '0.875rem',
          }}
          whileHover={{ background: 'var(--accent-hover)' }}
          whileTap={{ scale: 0.97 }}
        >
          Save
        </motion.button>
      </Modal.Footer>
    </Modal>
  )
}
