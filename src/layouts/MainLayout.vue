<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const menuItems = [
  { label: 'Dashboard', icon: 'pi-home', to: '/' },
  { label: 'Accounts', icon: 'pi-users', to: '/accounts' },
  { label: 'Proxy', icon: 'pi-globe', to: '/proxy' },
  { label: 'Auto Likes', icon: 'pi-heart', to: '/autolikes' },
  { label: 'Auto Comments', icon: 'pi-comments', to: '/autocomments' },
  { label: 'Settings', icon: 'pi-cog', to: '/settings' }
]

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>

<template>
  <div class="layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <div class="icon-wrapper">
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
        <div class="backend-status">
          <span class="status-dot connected"></span>
          <span class="text-xs text-gray-500">Backend connected</span>
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
  width: 240px;
  background: #141414;
  border-right: 1px solid #222;
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #222;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-text {
  font-size: 20px;
  font-weight: 600;
  background: linear-gradient(135deg, #a855f7, #7c3aed);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.sidebar-nav {
  flex: 1;
  padding: 12px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  color: #888;
  text-decoration: none;
  transition: all 0.2s;
  margin-bottom: 4px;
}

.nav-item:hover {
  background: #1a1a1a;
  color: #ccc;
}

.nav-item.active {
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
}

.nav-item i {
  font-size: 16px;
  width: 20px;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid #222;
}

.backend-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #666;
}

.status-dot.connected {
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  padding: 24px;
  background: #0f0f0f;
  min-height: 100vh;
}
</style>
