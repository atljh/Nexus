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

onMounted(async () => {
  try {
    const [accountsRes, proxiesRes] = await Promise.all([
      window.api.get('/api/accounts'),
      window.api.get('/api/proxy')
    ])

    const accounts = accountsRes.data || []
    const proxies = proxiesRes.data || []

    stats.value.accounts.total = accounts.length
    stats.value.accounts.active = accounts.filter((a: any) => a.status === 'valid').length
    stats.value.proxies.total = proxies.length
    stats.value.proxies.working = proxies.filter((p: any) => p.status === 'valid').length
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
})
</script>

<template>
  <MainLayout>
    <div class="dashboard">
      <h1 class="page-title">{{ t('dashboard.title') }}</h1>

      <!-- Stats cards -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-header">
            <div class="stat-icon stat-icon-purple">
              <i class="pi pi-users"></i>
            </div>
            <span class="stat-label">{{ t('dashboard.accounts') }}</span>
          </div>
          <div class="stat-value">{{ stats.accounts.total }}</div>
          <div class="stat-sub">{{ t('dashboard.accountsActive', { count: stats.accounts.active }) }}</div>
        </div>

        <div class="stat-card">
          <div class="stat-header">
            <div class="stat-icon stat-icon-blue">
              <i class="pi pi-globe"></i>
            </div>
            <span class="stat-label">{{ t('dashboard.proxies') }}</span>
          </div>
          <div class="stat-value">{{ stats.proxies.total }}</div>
          <div class="stat-sub">{{ t('dashboard.proxiesWorking', { count: stats.proxies.working }) }}</div>
        </div>

        <div class="stat-card">
          <div class="stat-header">
            <div class="stat-icon stat-icon-green">
              <i class="pi pi-heart"></i>
            </div>
            <span class="stat-label">{{ t('dashboard.likesToday') }}</span>
          </div>
          <div class="stat-value">{{ stats.likes.today }}</div>
          <div class="stat-sub">{{ t('dashboard.tasksCount', { count: stats.likes.tasks }) }}</div>
        </div>

        <div class="stat-card">
          <div class="stat-header">
            <div class="stat-icon stat-icon-orange">
              <i class="pi pi-comments"></i>
            </div>
            <span class="stat-label">{{ t('dashboard.commentsToday') }}</span>
          </div>
          <div class="stat-value">{{ stats.comments.today }}</div>
          <div class="stat-sub">{{ t('dashboard.tasksCount', { count: stats.comments.tasks }) }}</div>
        </div>
      </div>

      <!-- Quick actions -->
      <div class="section-card">
        <div class="section-header">
          <div class="section-icon">
            <i class="pi pi-bolt"></i>
          </div>
          <h2 class="section-title">{{ t('dashboard.quickActions') }}</h2>
        </div>
        <div class="actions-grid">
          <router-link to="/accounts" class="action-card">
            <div class="action-icon">
              <i class="pi pi-plus"></i>
            </div>
            <span class="action-label">{{ t('dashboard.addAccount') }}</span>
          </router-link>
          <router-link to="/proxy" class="action-card">
            <div class="action-icon action-icon-blue">
              <i class="pi pi-globe"></i>
            </div>
            <span class="action-label">{{ t('dashboard.addProxy') }}</span>
          </router-link>
          <router-link to="/autolikes" class="action-card">
            <div class="action-icon action-icon-pink">
              <i class="pi pi-heart"></i>
            </div>
            <span class="action-label">{{ t('dashboard.newLikeTask') }}</span>
          </router-link>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.dashboard {
  max-width: 1400px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #f3f4f6;
  margin-bottom: 28px;
  letter-spacing: -0.5px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 32px;
}

.stat-card {
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 24px;
  transition: all 0.3s ease;
}

.stat-card:hover {
  border-color: rgba(168, 85, 247, 0.3);
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: white;
}

.stat-icon-purple {
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
  box-shadow: 0 4px 16px rgba(168, 85, 247, 0.35);
}

.stat-icon-blue {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.35);
}

.stat-icon-green {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  box-shadow: 0 4px 16px rgba(16, 185, 129, 0.35);
}

.stat-icon-orange {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  box-shadow: 0 4px 16px rgba(245, 158, 11, 0.35);
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-size: 36px;
  font-weight: 700;
  color: #f9fafb;
  line-height: 1;
  margin-bottom: 6px;
}

.stat-sub {
  font-size: 13px;
  color: #4b5563;
}

.section-card {
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.section-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
  box-shadow: 0 4px 16px rgba(168, 85, 247, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #e5e7eb;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  padding: 24px;
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 24px;
  border: 1px dashed rgba(107, 114, 128, 0.3);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.02);
  text-decoration: none;
  transition: all 0.3s ease;
}

.action-card:hover {
  border-color: rgba(168, 85, 247, 0.5);
  border-style: solid;
  background: rgba(168, 85, 247, 0.08);
  transform: translateY(-2px);
}

.action-card:hover .action-icon {
  transform: scale(1.1);
}

.action-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.2) 0%, rgba(124, 58, 237, 0.15) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
  transition: all 0.3s ease;
  color: #a855f7;
  font-size: 20px;
}

.action-icon-blue {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2) 0%, rgba(37, 99, 235, 0.15) 100%);
  color: #3b82f6;
}

.action-icon-pink {
  background: linear-gradient(135deg, rgba(236, 72, 153, 0.2) 0%, rgba(219, 39, 119, 0.15) 100%);
  color: #ec4899;
}

.action-label {
  font-size: 14px;
  color: #9ca3af;
  font-weight: 500;
}

.action-card:hover .action-label {
  color: #e5e7eb;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .actions-grid {
    grid-template-columns: 1fr;
  }
}
</style>
