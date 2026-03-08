import { createI18n } from 'vue-i18n'
import en from './locales/en'
import uk from './locales/uk'

export type MessageSchema = typeof en

const savedLocale = (localStorage.getItem('locale') || 'uk') as 'en' | 'uk'

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'en',
  messages: {
    en,
    uk
  }
})

export function setLocale(locale: 'en' | 'uk') {
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
