import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import vi from './vi.json'

function getInitialLanguage() {
  try {
    const stored = localStorage.getItem('jarvis-settings')
    return stored ? JSON.parse(stored).language || 'en' : 'en'
  } catch {
    return 'en'
  }
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    vi: { translation: vi },
  },
  lng: getInitialLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export default i18n
