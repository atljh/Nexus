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
  // @ts-ignore - vue-i18n types issue
  i18n.global.locale.value = locale
  localStorage.setItem('locale', locale)
  document.documentElement.lang = locale
}

export function getLocale(): 'en' | 'uk' {
  // @ts-ignore - vue-i18n types issue
  return i18n.global.locale.value as 'en' | 'uk'
}

export default i18n
