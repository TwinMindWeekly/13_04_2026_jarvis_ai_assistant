import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, CheckCircle, XCircle, Loader2, Wifi } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { chatAPI } from '../services/api'

const PROVIDER_MODELS = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  gemini: ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
  claude: ['claude-sonnet-4-20250514', 'claude-haiku-4-5-20251001'],
  ollama: ['llama3.2', 'mistral', 'gemma2'],
}

const LANGUAGES = [
  { code: 'en', label: 'EN', full: 'English' },
  { code: 'vi', label: 'VI', full: 'Tiếng Việt' },
]

function SelectField({ label, value, onChange, options }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label
        className="text-xs font-semibold uppercase tracking-widest"
        style={{ color: 'var(--text-muted)' }}
      >
        {label}
      </label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none text-sm px-3 py-2.5 rounded-xl outline-none transition-all duration-150"
          style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid var(--glass-border)',
            color: 'var(--text-primary)',
            cursor: 'pointer',
          }}
          onFocus={(e) => {
            e.target.style.borderColor = 'rgba(99,102,241,0.5)'
          }}
          onBlur={(e) => {
            e.target.style.borderColor = 'var(--glass-border)'
          }}
        >
          {options.map((opt) => (
            <option
              key={opt.value}
              value={opt.value}
              style={{ background: 'var(--surface-2)', color: 'var(--text-primary)' }}
            >
              {opt.label}
            </option>
          ))}
        </select>
        <span
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[10px]"
          style={{ color: 'var(--text-muted)' }}
        >
          ▾
        </span>
      </div>
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

  const [localProvider, setLocalProvider] = useState(settings?.provider ?? 'openai')
  const [localModel, setLocalModel] = useState(settings?.model ?? 'gpt-4o')
  const [localLanguage, setLocalLanguage] = useState(settings?.language ?? 'en')
  const [testStatus, setTestStatus] = useState(null) // null | 'testing' | 'success' | 'failed'
  const [testMessage, setTestMessage] = useState('')

  // Sync from props when panel opens
  useEffect(() => {
    if (isOpen && settings) {
      setLocalProvider(settings.provider)
      setLocalModel(settings.model)
      setLocalLanguage(settings.language)
      setTestStatus(null)
      setTestMessage('')
    }
  }, [isOpen, settings])

  // When provider changes, reset model to first available
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

  const availableProviders = providers.length > 0
    ? providers.map((p) => ({ value: p, label: p.charAt(0).toUpperCase() + p.slice(1) }))
    : Object.keys(PROVIDER_MODELS).map((p) => ({
        value: p,
        label: p.charAt(0).toUpperCase() + p.slice(1),
      }))

  const availableModels = (PROVIDER_MODELS[localProvider] ?? []).map((m) => ({
    value: m,
    label: m,
  }))

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            className="fixed inset-0 z-40"
            style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <motion.div
              className="w-full max-w-md rounded-2xl overflow-hidden flex flex-col"
              style={{
                background: 'rgba(26,26,46,0.95)',
                border: '1px solid var(--glass-border)',
                backdropFilter: 'blur(20px)',
                WebkitBackdropFilter: 'blur(20px)',
                boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
              }}
              initial={{ scale: 0.93, y: 16 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.93, y: 16 }}
              transition={{ duration: 0.22, ease: [0.25, 0.46, 0.45, 0.94] }}
            >
              {/* Header */}
              <div
                className="flex items-center px-6 py-4"
                style={{ borderBottom: '1px solid var(--glass-border)' }}
              >
                <h2
                  className="text-base font-semibold flex-1"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {t('settings.title')}
                </h2>
                <button
                  onClick={onClose}
                  className="w-8 h-8 rounded-xl flex items-center justify-center transition-colors hover:bg-white/10"
                  aria-label="Close settings"
                >
                  <X size={16} style={{ color: 'var(--text-secondary)' }} />
                </button>
              </div>

              {/* Body */}
              <div className="px-6 py-5 flex flex-col gap-5">
                {/* Provider */}
                <SelectField
                  label={t('settings.provider')}
                  value={localProvider}
                  onChange={handleProviderChange}
                  options={availableProviders}
                />

                {/* Model */}
                <SelectField
                  label={t('settings.model')}
                  value={localModel}
                  onChange={setLocalModel}
                  options={availableModels}
                />

                {/* Language toggle */}
                <div className="flex flex-col gap-1.5">
                  <label
                    className="text-xs font-semibold uppercase tracking-widest"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {t('settings.language')}
                  </label>
                  <div className="flex gap-2">
                    {LANGUAGES.map((lang) => (
                      <button
                        key={lang.code}
                        onClick={() => setLocalLanguage(lang.code)}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150"
                        style={
                          localLanguage === lang.code
                            ? {
                                background: 'rgba(99,102,241,0.2)',
                                border: '1px solid rgba(99,102,241,0.45)',
                                color: 'var(--accent-hover)',
                              }
                            : {
                                background: 'rgba(255,255,255,0.05)',
                                border: '1px solid var(--glass-border)',
                                color: 'var(--text-secondary)',
                              }
                        }
                      >
                        <span className="font-bold">{lang.label}</span>
                        <span className="text-xs opacity-70">{lang.full}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Test Connection */}
                <div className="flex flex-col gap-2">
                  <button
                    onClick={handleTestConnection}
                    disabled={testStatus === 'testing'}
                    className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 disabled:opacity-60 disabled:cursor-not-allowed"
                    style={{
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid var(--glass-border)',
                      color: 'var(--text-secondary)',
                    }}
                    onMouseEnter={(e) => {
                      if (testStatus !== 'testing') {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.1)'
                        e.currentTarget.style.color = 'var(--text-primary)'
                      }
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(255,255,255,0.06)'
                      e.currentTarget.style.color = 'var(--text-secondary)'
                    }}
                  >
                    {testStatus === 'testing' ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Wifi size={14} />
                    )}
                    {testStatus === 'testing' ? t('settings.testing') : t('settings.test')}
                  </button>

                  <AnimatePresence>
                    {testStatus && testStatus !== 'testing' && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.18 }}
                        className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm overflow-hidden"
                        style={
                          testStatus === 'success'
                            ? {
                                background: 'rgba(34,197,94,0.08)',
                                border: '1px solid rgba(34,197,94,0.2)',
                                color: 'var(--success)',
                              }
                            : {
                                background: 'rgba(239,68,68,0.08)',
                                border: '1px solid rgba(239,68,68,0.2)',
                                color: 'var(--error)',
                              }
                        }
                      >
                        {testStatus === 'success' ? (
                          <CheckCircle size={14} className="flex-shrink-0" />
                        ) : (
                          <XCircle size={14} className="flex-shrink-0" />
                        )}
                        <span className="truncate">{testMessage}</span>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>

              {/* Footer */}
              <div
                className="flex items-center justify-end gap-2 px-6 py-4"
                style={{ borderTop: '1px solid var(--glass-border)' }}
              >
                <button
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl text-sm transition-colors hover:bg-white/10"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Cancel
                </button>
                <motion.button
                  onClick={handleSave}
                  className="px-5 py-2 rounded-xl text-sm font-medium text-white transition-all duration-150"
                  style={{
                    background: 'var(--accent)',
                    boxShadow: '0 4px 16px rgba(99,102,241,0.3)',
                  }}
                  whileHover={{ boxShadow: '0 4px 24px rgba(99,102,241,0.5)' }}
                  whileTap={{ scale: 0.97 }}
                >
                  Save
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
