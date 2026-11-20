// Manual English/Hindi translation store - no auto-translate plugins (TS Cl. 11.1; FRD CMN-01).
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import hi from './hi.json'

function storedLang(): string {
  try {
    return localStorage.getItem('oms.lang') || 'en'
  } catch {
    return 'en'
  }
}

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi } },
  lng: storedLang(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export function setLanguage(lng: 'en' | 'hi') {
  i18n.changeLanguage(lng)
  try {
    localStorage.setItem('oms.lang', lng)
  } catch {
    /* storage unavailable */
  }
  document.documentElement.lang = lng
}

/** Pick the Hindi or English field of a bilingual record. */
export function bi<T extends Record<string, any>>(row: T, field: string): string {
  const hi = row[`${field}_hi`]
  return i18n.language === 'hi' && hi ? hi : row[`${field}_en`] ?? row[field] ?? ''
}

export default i18n
