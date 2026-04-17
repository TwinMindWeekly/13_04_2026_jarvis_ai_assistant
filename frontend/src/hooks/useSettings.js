import { useState, useCallback } from 'react'

const STORAGE_KEY = 'jarvis-settings'
const DEFAULTS = {
  provider: 'auto',
  model: '',
  language: 'en',
  theme: 'dark',
  voiceEnabled: true,
  ttsVoice: '',
}

export function useSettings() {
  const [settings, setSettingsState] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      return stored ? { ...DEFAULTS, ...JSON.parse(stored) } : DEFAULTS
    } catch {
      return DEFAULTS
    }
  })

  const updateSettings = useCallback((updates) => {
    setSettingsState((prev) => {
      const next = { ...prev, ...updates }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }, [])

  const resetSettings = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    setSettingsState(DEFAULTS)
  }, [])

  return { settings, updateSettings, resetSettings }
}
