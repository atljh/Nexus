<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'

const { t } = useI18n()

const stats = ref({
  accounts: { total: 0, active: 0 },
  proxies: { total: 0, working: 0 },
  likes: { today: 0, tasks: 0 },
  comments: { today: 0, tasks: 0 }
})

interface Account { id: number; status: string }
interface ProxyItem { id: number; status: string }
interface AccountsResponse { data: Account[] }
interface ProxiesResponse { data: ProxyItem[] }

onMounted(async () => {
  try {
    const [accountsRes, proxiesRes] = await Promise.all([
      window.api.get('/api/accounts') as Promise<AccountsResponse>,
      window.api.get('/api/proxy') as Promise<ProxiesResponse>
    ])

    const accounts = accountsRes.data || []
    const proxies = proxiesRes.data || []

    stats.value.accounts.total = accounts.length
    stats.value.accounts.active = accounts.filter((a: Account) => a.status === 'valid').length
    stats.value.proxies.total = proxies.length
    stats.value.proxies.working = proxies.filter((p: ProxyItem) => p.status === 'working').length
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
})
</script>

<template>
  <MainLayout>
    <div class="dashboard">
      <!-- Stats Row -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon-wrap stat-icon-purple">
            <i class="pi pi-users"></i>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.accounts.total }}</div>
            <div class="stat-label">{{ t('dashboard.accounts') }}</div>
            <div class="stat-sub">{{ t('dashboard.accountsActive', { count: stats.accounts.active }) }}</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrap stat-icon-blue">
            <i class="pi pi-globe"></i>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.proxies.total }}</div>
            <div class="stat-label">{{ t('dashboard.proxies') }}</div>
            <div class="stat-sub">{{ t('dashboard.proxiesWorking', { count: stats.proxies.working }) }}</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrap stat-icon-green">
            <i class="pi pi-heart"></i>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.likes.today }}</div>
            <div class="stat-label">{{ t('dashboard.likesToday') }}</div>
            <div class="stat-sub">{{ t('dashboard.tasksCount', { count: stats.likes.tasks }) }}</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrap stat-icon-orange">
            <i class="pi pi-comments"></i>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.comments.today }}</div>
            <div class="stat-label">{{ t('dashboard.commentsToday') }}</div>
            <div class="stat-sub">{{ t('dashboard.tasksCount', { count: stats.comments.tasks }) }}</div>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="section-card">
        <div class="section-header">
          <i class="pi pi-bolt section-icon"></i>
          <h2 class="section-title">{{ t('dashboard.quickActions') }}</h2>
        </div>
        <div class="actions-grid">
          <router-link to="/accounts" class="action-card">
            <div class="action-icon">
              <i class="pi pi-users"></i>
            </div>
            <div class="action-text">
              <span class="action-label">{{ t('dashboard.addAccount') }}</span>
              <span class="action-hint">{{ t('dashboard.accounts') }}</span>
            </div>
            <i class="pi pi-chevron-right action-arrow"></i>
          </router-link>
          <router-link to="/proxy" class="action-card">
            <div class="action-icon action-icon-blue">
              <i class="pi pi-globe"></i>
            </div>
            <div class="action-text">
              <span class="action-label">{{ t('dashboard.addProxy') }}</span>
              <span class="action-hint">{{ t('dashboard.proxies') }}</span>
            </div>
            <i class="pi pi-chevron-right action-arrow"></i>
          </router-link>
          <router-link to="/autolikes" class="action-card">
            <div class="action-icon action-icon-pink">
              <i class="pi pi-heart"></i>
            </div>
            <div class="action-text">
              <span class="action-label">{{ t('dashboard.newLikeTask') }}</span>
              <span class="action-hint">Autolikes</span>
            </div>
            <i class="pi pi-chevron-right action-arrow"></i>
          </router-link>
          <router-link to="/autocomments" class="action-card">
            <div class="action-icon action-icon-orange">
              <i class="pi pi-comments"></i>
            </div>
            <div class="action-text">
              <span class="action-label">{{ t('dashboard.commentsToday') }}</span>
              <span class="action-hint">Autocomments</span>
            </div>
            <i class="pi pi-chevron-right action-arrow"></i>
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
  gap: 20px;
}

/* Stats Row */
.stats-row {
  display: flex;
  gap: 12px;
}

.stat-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 20px;
  transition: all 0.2s;
}

.stat-card:hover {
  border-color: rgba(255, 255, 255, 0.12);
}

.stat-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: white;
  flex-shrink: 0;
}

.stat-icon-purple {
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
}

.stat-icon-blue {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
}

.stat-icon-green {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.stat-icon-orange {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.stat-content {
  min-width: 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #f9fafb;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
  margin-top: 2px;
}

.stat-sub {
  font-size: 12px;
  color: #4b5563;
  margin-top: 2px;
}

/* Section Card */
.section-card {
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.section-icon {
  color: #a855f7;
  font-size: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

/* Actions Grid */
.actions-grid {
  display: flex;
  flex-direction: column;
}

.action-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 20px;
  text-decoration: none;
  transition: all 0.15s;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.action-card:last-child {
  border-bottom: none;
}

.action-card:hover {
  background: rgba(255, 255, 255, 0.03);
}

.action-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: rgba(168, 85, 247, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #a855f7;
  font-size: 16px;
  flex-shrink: 0;
  transition: all 0.2s;
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

.action-text {
  flex: 1;
  min-width: 0;
}

.action-label {
  display: block;
  font-size: 14px;
  color: #e5e7eb;
  font-weight: 500;
}

.action-hint {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-top: 1px;
}

.action-arrow {
  color: #4b5563;
  font-size: 12px;
  transition: all 0.2s;
}

.action-card:hover .action-arrow {
  color: #9ca3af;
  transform: translateX(2px);
}

.action-card:hover .action-icon {
  transform: scale(1.05);
}
</style>
