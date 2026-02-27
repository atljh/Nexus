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
          <div class="nav-icon-wrap">
            <i :class="['pi', item.icon]"></i>
          </div>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <button class="theme-toggle" @click="toggleTheme" :title="themeStore.resolvedTheme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'">
          <i :class="['pi', themeIcon]"></i>
        </button>
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
  width: 230px;
  background: #0c0c0e;
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
}

.sidebar-header {
  padding: 20px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
  box-shadow: 0 2px 12px rgba(168, 85, 247, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 15px;
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(135deg, #c084fc, #a855f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.3px;
}

.sidebar-nav {
  flex: 1;
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  color: #6b7280;
  text-decoration: none;
  transition: all 0.15s ease;
  font-size: 13.5px;
  font-weight: 500;
  position: relative;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: #9ca3af;
}

.nav-item.active {
  background: rgba(168, 85, 247, 0.08);
  color: #c084fc;
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: #a855f7;
  border-radius: 0 3px 3px 0;
}

.nav-icon-wrap {
  width: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-icon-wrap i {
  font-size: 16px;
}

.sidebar-footer {
  padding: 14px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.theme-toggle {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: rgba(255, 255, 255, 0.05);
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.theme-toggle:hover {
  background: rgba(168, 85, 247, 0.12);
  color: #a855f7;
}

.theme-toggle i {
  font-size: 14px;
}

.main-content {
  flex: 1;
  margin-left: 230px;
  padding: 20px 24px;
  background: #09090b;
  min-height: 100vh;
}
</style>
