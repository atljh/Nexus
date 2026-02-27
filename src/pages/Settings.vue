<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import { setLocale, getLocale } from '@/i18n'

const { t } = useI18n()

const currentLocale = ref(getLocale())

const languages = [
  { label: 'English', value: 'en', flag: '🇬🇧' },
  { label: 'Українська', value: 'uk', flag: '🇺🇦' }
]

function changeLanguage(locale: 'en' | 'uk') {
  currentLocale.value = locale
  setLocale(locale)
}
</script>

<template>
  <MainLayout>
    <div class="settings-page">
      <h1 class="page-title">{{ t('settings.title') }}</h1>

      <!-- Language Settings -->
      <div class="settings-card">
        <div class="card-header">
          <div class="header-icon header-icon-purple">
            <i class="pi pi-globe"></i>
          </div>
          <h2 class="header-title">{{ t('settings.language') }}</h2>
        </div>
        <div class="card-content">
          <div class="setting-row">
            <div class="setting-info">
              <div class="setting-title">{{ t('settings.language') }}</div>
              <div class="setting-desc">{{ t('settings.languageDesc') }}</div>
            </div>
            <Select
              :modelValue="currentLocale"
              :options="languages"
              optionLabel="label"
              optionValue="value"
              @update:modelValue="changeLanguage"
              class="language-dropdown"
            >
              <template #value="{ value }">
                <div class="language-option">
                  <span class="flag">{{ languages.find(l => l.value === value)?.flag }}</span>
                  <span>{{ languages.find(l => l.value === value)?.label }}</span>
                </div>
              </template>
              <template #option="{ option }">
                <div class="language-option">
                  <span class="flag">{{ option.flag }}</span>
                  <span>{{ option.label }}</span>
                </div>
              </template>
            </Select>
          </div>
        </div>
      </div>

      <!-- Application Settings -->
      <div class="settings-card">
        <div class="card-header">
          <div class="header-icon header-icon-blue">
            <i class="pi pi-cog"></i>
          </div>
          <h2 class="header-title">{{ t('settings.application') }}</h2>
        </div>
        <div class="card-content">
          <div class="setting-row">
            <div class="setting-info">
              <div class="setting-title">{{ t('settings.dataLocation') }}</div>
              <div class="setting-desc">~/.Nexus</div>
            </div>
            <Button :label="t('settings.change')" severity="secondary" size="small" />
          </div>

          <div class="setting-divider"></div>

          <div class="setting-row">
            <div class="setting-info">
              <div class="setting-title danger">{{ t('settings.clearAllData') }}</div>
              <div class="setting-desc">{{ t('settings.clearAllDataDesc') }}</div>
            </div>
            <Button :label="t('settings.clear')" severity="danger" size="small" />
          </div>
        </div>
      </div>

      <!-- About -->
      <div class="about-section">
        <div class="about-logo">
          <div class="logo-icon">
            <i class="pi pi-bolt"></i>
          </div>
          <span class="logo-text">Nexus</span>
        </div>
        <div class="about-version">v1.0.0</div>
        <div class="about-copyright">Telegram Automation Tool</div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.settings-page {
  max-width: 800px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #f3f4f6;
  margin-bottom: 28px;
  letter-spacing: -0.5px;
}

.settings-card {
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.header-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 16px;
}

.header-icon-purple {
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
  box-shadow: 0 4px 16px rgba(168, 85, 247, 0.35);
}

.header-icon-blue {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.35);
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #e5e7eb;
}

.card-content {
  padding: 20px 24px;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
}

.setting-info {
  flex: 1;
}

.setting-title {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
  margin-bottom: 4px;
}

.setting-title.danger {
  color: #ef4444;
}

.setting-desc {
  font-size: 13px;
  color: #6b7280;
}

.setting-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.06);
  margin: 8px 0;
}

.language-dropdown {
  min-width: 160px;
}

.language-option {
  display: flex;
  align-items: center;
  gap: 10px;
}

.flag {
  font-size: 18px;
}

.about-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px;
  margin-top: 20px;
}

.about-logo {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 12px;
}

.logo-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
  box-shadow: 0 4px 20px rgba(168, 85, 247, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 22px;
}

.logo-text {
  font-size: 26px;
  font-weight: 700;
  background: linear-gradient(135deg, #a855f7, #7c3aed);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.about-version {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 4px;
}

.about-copyright {
  font-size: 12px;
  color: #4b5563;
}
</style>
