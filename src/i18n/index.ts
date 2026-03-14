import { createI18n } from 'vue-i18n'
import en from './locales/en'

export type MessageSchema = typeof en

const savedLocale = (localStorage.getItem('locale') || 'uk') as 'en' | 'uk'

// Load initial locale eagerly, lazy-load the other
const messages: Record<string, MessageSchema> = { en }

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'en',
  messages
})

// Lazy-load Ukrainian locale
async function loadUkLocale() {
  if (messages.uk) return
  const uk = await import('./locales/uk')
  messages.uk = uk.default
  i18n.global.setLocaleMessage('uk', uk.default)
}

// If saved locale is uk, load it immediately
if (savedLocale === 'uk') {
  loadUkLocale()
}

export async function setLocale(locale: 'en' | 'uk') {
  if (locale === 'uk') {
    await loadUkLocale()
  }
  const localeRef = i18n.global.locale as unknown as { value: 'en' | 'uk' }
  localeRef.value = locale
  localStorage.setItem('locale', locale)
  document.documentElement.lang = locale
}

export function getLocale(): 'en' | 'uk' {
  const localeRef = i18n.global.locale as unknown as { value: 'en' | 'uk' }
  return localeRef.value
}

export default i18n
