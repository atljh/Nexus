<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAccountStore } from '@/stores/useAccountStore'
import { useProxyStore } from '@/stores/useProxyStore'
import { useTaskStore } from '@/stores/useTaskStore'

const { t } = useI18n()

const accountStore = useAccountStore()
const proxyStore = useProxyStore()
const taskStore = useTaskStore()

const stats = computed(() => ({
  accounts: {
    total: accountStore.accounts.length,
    active: accountStore.accounts.filter(a => a.status === 'valid').length,
  },
  proxies: {
    total: proxyStore.proxies.length,
    working: proxyStore.statusCounts.working,
  },
  tasks: {
    running: taskStore.stats.running || 0,
    completed: taskStore.stats.completed || 0,
  },
}))

const loaded = ref(false)
let refreshInterval: ReturnType<typeof setInterval> | null = null

async function loadStats() {
  await Promise.all([
    accountStore.fetchAccounts(),
    proxyStore.fetchProxies(),
    taskStore.fetchStats(),
  ])
}

onMounted(async () => {
  await loadStats()
  loaded.value = true
  refreshInterval = setInterval(loadStats, 30000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<template>
  <MainLayout>
    <div class="dashboard" :class="{ loaded }">
      <!-- Header -->
      <div class="dash-header">
        <h1 class="dash-title">{{ t('nav.dashboard') }}</h1>
      </div>

      <!-- Stats Grid -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-top">
            <div class="stat-icon stat-icon-purple">
              <i class="pi pi-users"></i>
            </div>
            <div class="stat-badge" v-if="stats.accounts.active > 0">
              <span class="stat-badge-dot"></span>
              {{ stats.accounts.active }} {{ t('dashboard.active') || 'active' }}
            </div>
          </div>
          <div class="stat-value">{{ stats.accounts.total }}</div>
          <div class="stat-label">{{ t('dashboard.accounts') }}</div>
        </div>

        <div class="stat-card">
          <div class="stat-top">
            <div class="stat-icon stat-icon-blue">
              <i class="pi pi-globe"></i>
            </div>
            <div class="stat-badge" v-if="stats.proxies.working > 0">
              <span class="stat-badge-dot stat-badge-dot-green"></span>
              {{ stats.proxies.working }} {{ t('dashboard.working') || 'working' }}
            </div>
          </div>
          <div class="stat-value">{{ stats.proxies.total }}</div>
          <div class="stat-label">{{ t('dashboard.proxies') }}</div>
        </div>

        <div class="stat-card">
          <div class="stat-top">
            <div class="stat-icon stat-icon-pink">
              <i class="pi pi-bolt"></i>
            </div>
            <div class="stat-badge" v-if="stats.tasks.running > 0">
              <span class="stat-badge-dot stat-badge-dot-green"></span>
              {{ stats.tasks.running }} active
            </div>
          </div>
          <div class="stat-value">{{ stats.tasks.completed }}</div>
          <div class="stat-label">{{ t('dashboard.tasksCompleted') || 'Tasks completed' }}</div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="section">
        <div class="section-label">
          <i class="pi pi-bolt"></i>
          <span>{{ t('dashboard.quickActions') }}</span>
        </div>
        <div class="actions-grid">
          <router-link to="/accounts" class="action-card">
            <div class="action-icon action-icon-purple">
              <i class="pi pi-users"></i>
            </div>
            <div class="action-body">
              <span class="action-title">{{ t('dashboard.addAccount') }}</span>
              <span class="action-desc">{{ t('dashboard.accounts') }}</span>
            </div>
            <i class="pi pi-arrow-right action-arrow"></i>
          </router-link>

          <router-link to="/proxy" class="action-card">
            <div class="action-icon action-icon-blue">
              <i class="pi pi-globe"></i>
            </div>
            <div class="action-body">
              <span class="action-title">{{ t('dashboard.addProxy') }}</span>
              <span class="action-desc">{{ t('dashboard.proxies') }}</span>
            </div>
            <i class="pi pi-arrow-right action-arrow"></i>
          </router-link>

          <router-link to="/autolikes" class="action-card">
            <div class="action-icon action-icon-pink">
              <i class="pi pi-heart"></i>
            </div>
            <div class="action-body">
              <span class="action-title">{{ t('dashboard.newLikeTask') }}</span>
              <span class="action-desc">AutoLikes</span>
            </div>
            <i class="pi pi-arrow-right action-arrow"></i>
          </router-link>

          <router-link to="/autocomments" class="action-card">
            <div class="action-icon action-icon-orange">
              <i class="pi pi-comments"></i>
            </div>
            <div class="action-body">
              <span class="action-title">{{ t('dashboard.commentsToday') }}</span>
              <span class="action-desc">AutoComments</span>
            </div>
            <i class="pi pi-arrow-right action-arrow"></i>
          </router-link>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 24px;
  opacity: 0;
  transform: translateY(6px);
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.dashboard.loaded {
  opacity: 1;
  transform: translateY(0);
}

/* Header */
.dash-header {
  margin-bottom: 4px;
}

.dash-title {
  font-size: 24px;
  font-weight: 700;
  color: #f3f4f6;
  letter-spacing: -0.4px;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.stat-card {
  background: #111113;
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 14px;
  padding: 20px;
  transition: border-color 0.2s;
}

.stat-card:hover {
  border-color: rgba(255, 255, 255, 0.1);
}

.stat-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  color: white;
}

.stat-icon-purple {
  background: linear-gradient(135deg, #a855f7, #7c3aed);
}

.stat-icon-blue {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
}

.stat-icon-pink {
  background: linear-gradient(135deg, #ec4899, #be185d);
}

.stat-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #9ca3af;
  background: rgba(255, 255, 255, 0.04);
  padding: 4px 10px;
  border-radius: 20px;
}

.stat-badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #a855f7;
}

.stat-badge-dot-green {
  background: #22c55e;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #f9fafb;
  line-height: 1;
  letter-spacing: -1px;
}

.stat-label {
  font-size: 13px;
  color: #8b8f9a;
  font-weight: 500;
  margin-top: 6px;
}

/* Section */
.section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #8b8f9a;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.section-label i {
  font-size: 13px;
  color: #a855f7;
}

/* Actions Grid */
.actions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.action-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: #111113;
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 12px;
  text-decoration: none;
  transition: all 0.15s ease;
}

.action-card:hover {
  border-color: rgba(255, 255, 255, 0.1);
  background: #141416;
}

.action-icon {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
  transition: transform 0.15s ease;
}

.action-card:hover .action-icon {
  transform: scale(1.05);
}

.action-icon-purple {
  background: rgba(168, 85, 247, 0.12);
  color: #a855f7;
}

.action-icon-blue {
  background: rgba(59, 130, 246, 0.12);
  color: #3b82f6;
}

.action-icon-pink {
  background: rgba(236, 72, 153, 0.12);
  color: #ec4899;
}

.action-icon-orange {
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
}

.action-body {
  flex: 1;
  min-width: 0;
}

.action-title {
  display: block;
  font-size: 13.5px;
  color: #e5e7eb;
  font-weight: 500;
}

.action-desc {
  display: block;
  font-size: 12px;
  color: #4b5563;
  margin-top: 1px;
}

.action-arrow {
  color: #55555e;
  font-size: 11px;
  transition: all 0.15s ease;
}

.action-card:hover .action-arrow {
  color: #9ca3af;
  transform: translateX(2px);
}
</style>
