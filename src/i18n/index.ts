import { createI18n } from 'vue-i18n'
import en from './locales/en'
import ru from './locales/ru'

export type MessageSchema = typeof en

const savedLocale = (localStorage.getItem('locale') || 'ru') as 'en' | 'ru'

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'en',
  messages: {
    en,
    ru
  }
})

export function setLocale(locale: 'en' | 'ru') {
  // @ts-ignore - vue-i18n types issue
  i18n.global.locale.value = locale
  localStorage.setItem('locale', locale)
  document.documentElement.lang = locale
}

export function getLocale(): 'en' | 'ru' {
  // @ts-ignore - vue-i18n types issue
  return i18n.global.locale.value as 'en' | 'ru'
}

export default i18n
