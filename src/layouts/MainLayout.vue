<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useThemeStore } from '@/stores/useThemeStore'

const { t } = useI18n()
const route = useRoute()
const themeStore = useThemeStore()

const menuItems = computed(() => [
  { label: t('nav.dashboard'), icon: 'pi-home', to: '/' },
  { label: t('nav.accounts'), icon: 'pi-users', to: '/accounts' },
  { label: t('nav.proxy'), icon: 'pi-globe', to: '/proxy' },
  { label: t('nav.autoLikes'), icon: 'pi-heart', to: '/autolikes' },
  { label: t('nav.autoComments'), icon: 'pi-comments', to: '/autocomments' },
  { label: t('nav.settings'), icon: 'pi-cog', to: '/settings' }
])

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

const themeIcon = computed(() => {
  return themeStore.resolvedTheme === 'dark' ? 'pi-sun' : 'pi-moon'
})

function toggleTheme() {
  themeStore.toggleTheme()
}
</script>

<template>
  <div class="layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <div class="logo-icon">
            <i class="pi pi-bolt"></i>
          </div>
          <span class="logo-text">Nexus</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <router-link
          v-for="item in menuItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item.to) }"
        >
          <i :class="['pi', item.icon]"></i>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="footer-row">
          <div class="backend-status">
            <span class="status-dot connected"></span>
            <span class="status-text">{{ t('sidebar.backendConnected') }}</span>
          </div>
          <button class="theme-toggle" @click="toggleTheme" :title="themeStore.resolvedTheme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'">
            <i :class="['pi', themeIcon]"></i>
          </button>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="main-content">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 260px;
  background: linear-gradient(180deg, #141414 0%, #0d0d0d 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
}

.sidebar-header {
  padding: 24px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo {
  display: flex;
  align-items: center;
  gap: 14px;
}

.logo-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
  box-shadow: 0 4px 16px rgba(168, 85, 247, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
}

.logo-text {
  font-size: 22px;
  font-weight: 700;
  background: linear-gradient(135deg, #a855f7, #7c3aed);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.5px;
}

.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  border-radius: 10px;
  color: #6b7280;
  text-decoration: none;
  transition: all 0.2s ease;
  font-size: 14px;
  font-weight: 500;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: #9ca3af;
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(124, 58, 237, 0.1) 100%);
  color: #a855f7;
  box-shadow: inset 0 0 0 1px rgba(168, 85, 247, 0.2);
}

.nav-item i {
  font-size: 18px;
  width: 24px;
  text-align: center;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.backend-status {
  display: flex;
  align-items: center;
  gap: 10px;
}

.theme-toggle {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: rgba(255, 255, 255, 0.06);
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.theme-toggle:hover {
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
}

.theme-toggle i {
  font-size: 14px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6b7280;
  flex-shrink: 0;
}

.status-dot.connected {
  background: #10b981;
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.6);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.status-text {
  font-size: 12px;
  color: #6b7280;
}

.main-content {
  flex: 1;
  margin-left: 260px;
  padding: 28px 32px;
  background: #0a0a0a;
  min-height: 100vh;
  transition: background-color 0.2s ease;
}
</style>
