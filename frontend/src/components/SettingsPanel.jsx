import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Modal from 'react-bootstrap/Modal'
import Form from 'react-bootstrap/Form'
import Button from 'react-bootstrap/Button'
import { CheckCircle, XCircle, Loader2, Wifi } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { chatAPI } from '../services/api'

const PROVIDER_MODELS = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  gemini: ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash'],
  claude: ['claude-sonnet-4-20250514', 'claude-haiku-4-5-20251001'],
  ollama: ['llama3.2', 'mistral', 'gemma2'],
}

const LANGUAGES = [
  { code: 'en', label: 'EN', full: 'English' },
  { code: 'vi', label: 'VI', full: 'Tiếng Việt' },
]

export default function SettingsPanel({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  providers = [],
}) {
  const { t } = useTranslation()

  const [localProvider, setLocalProvider] = useState(settings?.provider ?? 'openai')
  const [localModel, setLocalModel] = useState(settings?.model ?? 'gpt-4o')
  const [localLanguage, setLocalLanguage] = useState(settings?.language ?? 'en')
  const [testStatus, setTestStatus] = useState(null)
  const [testMessage, setTestMessage] = useState('')

  useEffect(() => {
    if (isOpen && settings) {
      setLocalProvider(settings.provider)
      setLocalModel(settings.model)
      setLocalLanguage(settings.language)
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
    onUpdateSettings({ provider: localProvider, model: localModel, language: localLanguage })
    onClose()
  }

  const handleTestConnection = async () => {
    setTestStatus('testing')
    setTestMessage('')
    try {
      await chatAPI.testProvider(localProvider, null)
      setTestStatus('success')
      setTestMessage(t('settings.success'))
    } catch (err) {
      setTestStatus('failed')
      setTestMessage(
        err.response?.data?.detail ?? err.message ?? t('settings.failed')
      )
    }
  }

  const availableProviders =
    providers.length > 0
      ? providers.map((p) => {
          const name = typeof p === 'string' ? p : p.name
          return { value: name, label: name.charAt(0).toUpperCase() + name.slice(1) }
        })
      : Object.keys(PROVIDER_MODELS).map((p) => ({
          value: p,
          label: p.charAt(0).toUpperCase() + p.slice(1),
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

      <Modal.Body className="d-flex flex-column gap-4 px-4 py-4">
        {/* Provider */}
        <Form.Group>
          <Form.Label>{t('settings.provider')}</Form.Label>
          <Form.Select
            value={localProvider}
            onChange={(e) => handleProviderChange(e.target.value)}
          >
            {availableProviders.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Form.Select>
        </Form.Group>

        {/* Model */}
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

        {/* Language toggle */}
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
                <div
                  className={`test-result${testStatus === 'success' ? ' success' : ' failed'}`}
                >
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
