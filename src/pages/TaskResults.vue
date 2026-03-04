<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'

import { useTaskStore } from '@/stores/useTaskStore'
import type { Task } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const taskStore = useTaskStore()

// State
const task = ref<Task | null>(null)
const loading = ref(true)
const logsFilter = ref<'all' | 'success' | 'failed'>('all')
const logsSearch = ref('')
const showConfirmDialog = ref(false)
const confirmAction = ref<'cancel' | 'delete' | 'restart' | null>(null)
const pollingInterval = ref<number | null>(null)

// Get task ID from route
const taskId = computed(() => Number(route.params.id))

// Filtered logs
const filteredLogs = computed(() => {
  let logs = taskStore.taskLogs

  if (logsFilter.value === 'success') {
    logs = logs.filter(log => log.success)
  } else if (logsFilter.value === 'failed') {
    logs = logs.filter(log => !log.success)
  }

  if (logsSearch.value.trim()) {
    const search = logsSearch.value.toLowerCase()
    logs = logs.filter(log =>
      log.target?.toLowerCase().includes(search) ||
      log.message?.toLowerCase().includes(search) ||
      log.error?.toLowerCase().includes(search)
    )
  }

  return logs
})

// Task type label
const taskTypeLabel = computed(() => {
  if (!task.value) return ''
  return t(`taskResults.taskType.${task.value.task_type}`)
})

// Task status info
const statusInfo = computed(() => {
  if (!task.value) return { label: '', severity: 'secondary' as const, icon: 'pi-question' }

  const statusMap: Record<string, { label: string; severity: 'success' | 'info' | 'warn' | 'danger' | 'secondary'; icon: string }> = {
    pending: { label: t('taskResults.status.pending'), severity: 'warn', icon: 'pi-clock' },
    running: { label: t('taskResults.status.running'), severity: 'info', icon: 'pi-spin pi-spinner' },
    paused: { label: t('taskResults.status.paused'), severity: 'warn', icon: 'pi-pause' },
    completed: { label: t('taskResults.status.completed'), severity: 'success', icon: 'pi-check-circle' },
    failed: { label: t('taskResults.status.failed'), severity: 'danger', icon: 'pi-times-circle' },
    cancelled: { label: t('taskResults.status.cancelled'), severity: 'secondary', icon: 'pi-ban' }
  }

  return statusMap[task.value.status] || { label: task.value.status, severity: 'secondary', icon: 'pi-question' }
})

// Statistics
const stats = computed(() => {
  if (!task.value) return null

  const totalDone = task.value.completed_actions + task.value.failed_actions
  const successRate = totalDone > 0
    ? Math.round(task.value.completed_actions / totalDone * 100)
    : 0

  const duration = task.value.started_at
    ? (task.value.completed_at
        ? new Date(task.value.completed_at).getTime() - new Date(task.value.started_at).getTime()
        : Date.now() - new Date(task.value.started_at).getTime())
    : 0

  const avgTimePerAction = task.value.completed_actions > 0
    ? Math.round(duration / task.value.completed_actions / 1000)
    : 0

  return {
    successRate,
    duration,
    avgTimePerAction,
    actionsPerMinute: duration > 60000 && task.value.completed_actions > 0
      ? Math.round(task.value.completed_actions / (duration / 60000) * 10) / 10
      : 0
  }
})

// Format duration
function formatDuration(ms: number): string {
  if (ms < 1000) return t('taskResults.time.lessThanSecond')

  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  const s = t('taskResults.time.seconds')
  const m = t('taskResults.time.minutes')
  const h = t('taskResults.time.hours')

  if (hours > 0) {
    return `${hours} ${h} ${minutes % 60} ${m}`
  } else if (minutes > 0) {
    return `${minutes} ${m} ${seconds % 60} ${s}`
  }
  return `${seconds} ${s}`
}

// Format date
function formatDate(date: string | null): string {
  if (!date) return '—'
  return new Date(date).toLocaleString('uk-UA', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// Format relative time
function formatRelativeTime(date: string | null): string {
  if (!date) return '—'

  const now = Date.now()
  const time = new Date(date).getTime()
  const diff = now - time

  if (diff < 60000) return t('taskResults.time.justNow')
  if (diff < 3600000) return t('taskResults.time.minutesAgo', { count: Math.floor(diff / 60000) })
  if (diff < 86400000) return t('taskResults.time.hoursAgo', { count: Math.floor(diff / 3600000) })
  return t('taskResults.time.daysAgo', { count: Math.floor(diff / 86400000) })
}

// Channel status severity
function getChannelStatusSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
  const map: Record<string, 'success' | 'info' | 'warn' | 'danger' | 'secondary'> = {
    joined: 'success',
    pending: 'info',
    error: 'danger',
    cannot_comment: 'warn'
  }
  return map[status] || 'secondary'
}

// Task actions
async function startTask() {
  if (!task.value) return
  await taskStore.startTask(task.value.id)
  toast.add({ severity: 'info', summary: 'Завдання запущено', life: 2000 })
  await loadTask()
  startPolling()
}

async function pauseTask() {
  if (!task.value) return
  await taskStore.pauseTask(task.value.id)
  toast.add({ severity: 'info', summary: 'Завдання призупинено', life: 2000 })
  await loadTask()
}

async function cancelTask() {
  if (!task.value) return
  await taskStore.cancelTask(task.value.id)
  toast.add({ severity: 'info', summary: 'Завдання скасовано', life: 2000 })
  showConfirmDialog.value = false
  confirmAction.value = null
  await loadTask()
  stopPolling()
}

async function deleteTask() {
  if (!task.value) return
  await taskStore.deleteTask(task.value.id)
  toast.add({ severity: 'info', summary: 'Завдання видалено', life: 2000 })
  showConfirmDialog.value = false
  confirmAction.value = null
  router.push(task.value.task_type === 'likes' ? '/autolikes' : '/autocomments')
}

function showConfirm(action: 'cancel' | 'delete' | 'restart') {
  confirmAction.value = action
  showConfirmDialog.value = true
}

function executeConfirmAction() {
  if (confirmAction.value === 'cancel') {
    cancelTask()
  } else if (confirmAction.value === 'delete') {
    deleteTask()
  }
}

// Load task data
async function loadTask() {
  loading.value = true
  try {
    const result = await taskStore.fetchTask(taskId.value)
    if (result) {
      task.value = result
      await Promise.all([
        taskStore.fetchTaskLogs(taskId.value),
        task.value.task_type === 'comments' ? taskStore.fetchTargetChannels(taskId.value) : Promise.resolve()
      ])
    }
  } catch (e) {
    console.error('Failed to load task:', e)
    toast.add({ severity: 'error', summary: t('taskResults.loadError'), life: 3000 })
  } finally {
    loading.value = false
  }
}

// Polling for running tasks
function startPolling() {
  if (pollingInterval.value) return
  pollingInterval.value = window.setInterval(async () => {
    if (task.value?.status === 'running') {
      await loadTask()
    } else {
      stopPolling()
    }
  }, 2000)
}

function stopPolling() {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
}

// Initialize
onMounted(async () => {
  await loadTask()

  // Redirect if task not found
  if (!task.value) {
    toast.add({ severity: 'warn', summary: t('taskResults.notFound'), life: 3000 })
    router.replace('/auto-likes')
    return
  }

  if (task.value?.status === 'running') {
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})

// Watch for status changes
watch(() => task.value?.status, (newStatus) => {
  if (newStatus === 'running') {
    startPolling()
  } else {
    stopPolling()
  }
})
</script>

<template>
  <MainLayout>
    <div class="task-results-page">
      <!-- Loading State -->
      <div v-if="loading && !task" class="loading-state">
        <i class="pi pi-spin pi-spinner"></i>
        <span>Завантаження...</span>
      </div>

      <!-- Task Content -->
      <div v-else-if="task" class="task-content">
        <!-- Header -->
        <div class="page-header">
          <div class="header-left">
            <Button
              icon="pi pi-arrow-left"
              text
              rounded
              class="back-btn"
              @click="router.back()"
            />
            <div class="header-info">
              <div class="header-top">
                <span class="task-id">#{{ task.id }}</span>
                <span class="task-type-badge">{{ taskTypeLabel }}</span>
              </div>
              <h1>{{ t('taskResults.title') }}</h1>
            </div>
          </div>

          <div class="header-actions">
            <Button
              v-if="task.status === 'pending' || task.status === 'paused'"
              icon="pi pi-play"
              :label="t('taskResults.actions.start')"
              class="action-btn start"
              @click="startTask"
            />
            <Button
              v-if="task.status === 'running'"
              icon="pi pi-pause"
              :label="t('taskResults.actions.pause')"
              class="action-btn pause"
              @click="pauseTask"
            />
            <Button
              v-if="task.status === 'running' || task.status === 'paused'"
              icon="pi pi-stop"
              :label="t('taskResults.actions.stop')"
              class="action-btn stop"
              @click="showConfirm('cancel')"
            />
            <Button
              v-if="task.status !== 'running'"
              icon="pi pi-trash"
              :label="t('taskResults.actions.delete')"
              class="action-btn delete"
              @click="showConfirm('delete')"
            />
          </div>
        </div>

        <!-- Status Banner -->
        <div :class="['status-banner', `status-${task.status}`]">
          <div class="status-main">
            <i :class="['status-icon', 'pi', statusInfo.icon]"></i>
            <div class="status-text">
              <span class="status-label">{{ statusInfo.label }}</span>
              <span v-if="task.status === 'running'" class="status-progress">
                {{ t('taskResults.actions.actionsOf', { completed: task.completed_actions, total: task.total_actions }) }}
              </span>
              <span v-else-if="task.status === 'completed'" class="status-detail">
                {{ t('taskResults.time.completedIn', { time: formatDuration(stats?.duration || 0) }) }}
              </span>
              <span v-else-if="task.last_error" class="status-error">
                {{ task.last_error }}
              </span>
            </div>
          </div>

          <div class="status-progress-bar">
            <div class="progress-fill" :style="{ width: `${task.progress}%` }"></div>
          </div>
          <span class="progress-percent">{{ task.progress }}%</span>
        </div>

        <!-- Stats Grid -->
        <div class="stats-grid">
          <div class="stat-card">
            <i class="pi pi-check-circle stat-icon success"></i>
            <div class="stat-content">
              <span class="stat-value">{{ task.completed_actions }}</span>
              <span class="stat-label">{{ t('taskResults.stats.success') }}</span>
            </div>
          </div>
          <div class="stat-card">
            <i class="pi pi-times-circle stat-icon danger"></i>
            <div class="stat-content">
              <span class="stat-value">{{ task.failed_actions }}</span>
              <span class="stat-label">{{ t('taskResults.stats.errors') }}</span>
            </div>
          </div>
          <div class="stat-card">
            <i class="pi pi-percentage stat-icon info"></i>
            <div class="stat-content">
              <span class="stat-value">{{ stats?.successRate || 0 }}%</span>
              <span class="stat-label">{{ t('taskResults.stats.successRate') }}</span>
            </div>
          </div>
          <div class="stat-card">
            <i class="pi pi-clock stat-icon warn"></i>
            <div class="stat-content">
              <span class="stat-value">{{ formatDuration(stats?.duration || 0) }}</span>
              <span class="stat-label">{{ t('taskResults.stats.duration') }}</span>
            </div>
          </div>
          <div class="stat-card">
            <i class="pi pi-bolt stat-icon primary"></i>
            <div class="stat-content">
              <span class="stat-value">{{ stats?.avgTimePerAction || 0 }}{{ t('taskResults.time.seconds') }}</span>
              <span class="stat-label">{{ t('taskResults.stats.avgSpeed') }}</span>
            </div>
          </div>
          <div class="stat-card">
            <i class="pi pi-users stat-icon secondary"></i>
            <div class="stat-content">
              <span class="stat-value">{{ task.accounts_count || 0 }}</span>
              <span class="stat-label">{{ t('taskResults.stats.accounts') }}</span>
            </div>
          </div>
        </div>

        <!-- Main Content Grid -->
        <div class="main-grid">
          <!-- Left Column: Config & Channels -->
          <div class="left-column">
            <!-- Configuration Card -->
            <div class="config-card">
              <div class="card-header">
                <i class="pi pi-cog"></i>
                <h3>{{ t('common.configuration') }}</h3>
              </div>
              <div class="config-content">
                <!-- For Likes -->
                <template v-if="task.task_type === 'likes'">
                  <div class="config-row">
                    <span class="config-label">{{ t('taskResults.config.channel') }}</span>
                    <span class="config-value channel">{{ task.config?.channel }}</span>
                  </div>
                  <div class="config-row">
                    <span class="config-label">{{ t('taskResults.config.reactions') }}</span>
                    <span class="config-value emoji">{{ (task.config?.reactions || []).join(' ') }}</span>
                  </div>
                  <div v-if="task.config?.emoji_mode" class="config-row">
                    <span class="config-label">{{ t('taskResults.config.emojiMode') }}</span>
                    <span class="config-value">{{ t(`taskResults.emojiModes.${task.config.emoji_mode}`) }}</span>
                  </div>
                  <div v-if="task.config?.post_id" class="config-row">
                    <span class="config-label">{{ t('taskResults.config.postId') }}</span>
                    <span class="config-value">{{ task.config?.post_id }}</span>
                  </div>
                </template>

                <!-- For Comments -->
                <template v-if="task.task_type === 'comments'">
                  <div class="config-row">
                    <span class="config-label">Канали</span>
                    <div class="config-tags">
                      <span
                        v-for="(ch, idx) in task.config?.channels"
                        :key="idx"
                        class="config-tag channel"
                      >
                        {{ ch }}
                      </span>
                    </div>
                  </div>
                  <div class="config-row">
                    <span class="config-label">Шаблони</span>
                    <span class="config-value">{{ task.config?.templates?.length || 0 }} шт.</span>
                  </div>
                  <div class="config-row">
                    <span class="config-label">Ротація</span>
                    <span class="config-value">{{ task.config?.rotation_mode === 'random' ? t('taskResults.emojiModes.random') : 'Round-robin' }}</span>
                  </div>
                  <div class="config-row">
                    <span class="config-label">Коментарів/акаунт</span>
                    <span class="config-value">{{ task.config?.comments_per_account }}</span>
                  </div>
                </template>

                <div class="config-divider"></div>

                <div class="config-row">
                  <span class="config-label">{{ t('taskResults.config.delay') }}</span>
                  <span class="config-value">{{ task.min_delay }} — {{ task.max_delay }} {{ t('taskResults.time.seconds') }}</span>
                </div>
                <div class="config-row">
                  <span class="config-label">{{ t('taskResults.config.createdAt') }}</span>
                  <span class="config-value time">{{ formatDate(task.created_at) }}</span>
                </div>
                <div v-if="task.started_at" class="config-row">
                  <span class="config-label">{{ t('taskResults.config.startedAt') }}</span>
                  <span class="config-value time">{{ formatDate(task.started_at) }}</span>
                </div>
                <div v-if="task.completed_at" class="config-row">
                  <span class="config-label">{{ t('taskResults.config.completedAt') }}</span>
                  <span class="config-value time">{{ formatDate(task.completed_at) }}</span>
                </div>
              </div>
            </div>

            <!-- Target Channels Card (for comments) -->
            <div v-if="task.task_type === 'comments' && taskStore.targetChannels.length > 0" class="channels-card">
              <div class="card-header">
                <i class="pi pi-hashtag"></i>
                <h3>Цільові канали</h3>
              </div>
              <div class="channels-list">
                <div
                  v-for="channel in taskStore.targetChannels"
                  :key="channel.id"
                  class="channel-item"
                >
                  <div class="channel-main">
                    <span class="channel-name">@{{ channel.channel_username }}</span>
                    <span v-if="channel.channel_title" class="channel-title">{{ channel.channel_title }}</span>
                  </div>
                  <div class="channel-stats">
                    <Tag
                      :value="channel.status"
                      :severity="getChannelStatusSeverity(channel.status)"
                      class="channel-status"
                    />
                    <span class="channel-sent">{{ channel.comments_sent }} коментарів</span>
                  </div>
                  <span v-if="channel.error_message" class="channel-error">
                    {{ channel.error_message }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Templates Card (for comments) -->
            <div v-if="task.task_type === 'comments' && task.config?.templates" class="templates-card">
              <div class="card-header">
                <i class="pi pi-file-edit"></i>
                <h3>Шаблони коментарів</h3>
              </div>
              <div class="templates-list">
                <div
                  v-for="(template, idx) in task.config?.templates"
                  :key="idx"
                  class="template-item"
                >
                  <span class="template-number">{{ idx + 1 }}</span>
                  <span class="template-content">{{ template }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Right Column: Logs -->
          <div class="right-column">
            <div class="logs-card">
              <div class="card-header">
                <i class="pi pi-history"></i>
                <h3>{{ t('taskResults.logs.title') }}</h3>
                <span class="logs-count">{{ t('taskResults.logs.entries', { count: filteredLogs.length }) }}</span>
              </div>

              <div class="logs-filters">
                <div class="filter-tabs">
                  <button
                    :class="['filter-tab', { active: logsFilter === 'all' }]"
                    @click="logsFilter = 'all'"
                  >
                    {{ t('taskResults.logs.all') }}
                    <span class="filter-count">{{ taskStore.taskLogs.length }}</span>
                  </button>
                  <button
                    :class="['filter-tab', { active: logsFilter === 'success' }]"
                    @click="logsFilter = 'success'"
                  >
                    {{ t('taskResults.logs.successful') }}
                    <span class="filter-count success">{{ taskStore.taskLogs.filter(l => l.success).length }}</span>
                  </button>
                  <button
                    :class="['filter-tab', { active: logsFilter === 'failed' }]"
                    @click="logsFilter = 'failed'"
                  >
                    {{ t('taskResults.logs.failed') }}
                    <span class="filter-count danger">{{ taskStore.taskLogs.filter(l => !l.success).length }}</span>
                  </button>
                </div>
                <div class="search-input">
                  <i class="pi pi-search"></i>
                  <InputText
                    v-model="logsSearch"
                    :placeholder="t('taskResults.logs.search')"
                    class="w-full"
                  />
                </div>
              </div>

              <div class="logs-list">
                <div
                  v-for="log in filteredLogs"
                  :key="log.id"
                  :class="['log-item', { success: log.success, error: !log.success }]"
                >
                  <div class="log-status">
                    <i :class="log.success ? 'pi pi-check' : 'pi pi-times'"></i>
                  </div>
                  <div class="log-content">
                    <div class="log-main">
                      <span class="log-target">{{ log.target }}</span>
                      <span class="log-time">{{ formatRelativeTime(log.created_at) }}</span>
                    </div>
                    <span v-if="log.message" class="log-message">{{ log.message }}</span>
                    <span v-if="log.error" class="log-error">{{ log.error }}</span>
                    <span v-if="log.extra_data?.comment" class="log-comment">
                      "{{ log.extra_data.comment }}"
                    </span>
                  </div>
                </div>

                <div v-if="filteredLogs.length === 0" class="logs-empty">
                  <i class="pi pi-inbox"></i>
                  <span>Немає записів</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Not Found State -->
      <div v-else class="not-found-state">
        <i class="pi pi-exclamation-triangle"></i>
        <h2>Завдання не знайдено</h2>
        <p>Завдання з ID {{ taskId }} не існує або було видалено</p>
        <Button
          label="Повернутися"
          icon="pi pi-arrow-left"
          @click="router.back()"
        />
      </div>

      <!-- Confirm Dialog -->
      <Dialog
        v-model:visible="showConfirmDialog"
        :header="confirmAction === 'delete' ? 'Видалити завдання?' : 'Зупинити завдання?'"
        :style="{ width: '400px' }"
        modal
        class="confirm-dialog"
      >
        <div class="confirm-content">
          <i :class="['confirm-icon', 'pi', confirmAction === 'delete' ? 'pi-trash' : 'pi-stop-circle']"></i>
          <p v-if="confirmAction === 'delete'">
            Ви впевнені, що хочете видалити це завдання? Цю дію неможливо скасувати.
          </p>
          <p v-else>
            Ви впевнені, що хочете зупинити виконання цього завдання?
          </p>
        </div>
        <template #footer>
          <Button
            label="Скасувати"
            severity="secondary"
            outlined
            @click="showConfirmDialog = false"
          />
          <Button
            :label="confirmAction === 'delete' ? 'Видалити' : 'Зупинити'"
            :severity="confirmAction === 'delete' ? 'danger' : 'warn'"
            @click="executeConfirmAction"
          />
        </template>
      </Dialog>
    </div>
  </MainLayout>
</template>

<style scoped>
.task-results-page {
  width: 100%;
}

/* Loading State */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 80px;
  color: #71717a;
}

.loading-state i {
  font-size: 40px;
  color: #a855f7;
}

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  color: #71717a;
}

.back-btn:hover {
  color: #fafafa;
  background: rgba(255, 255, 255, 0.05);
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.task-id {
  font-size: 14px;
  font-weight: 600;
  color: #a855f7;
}

.task-type-badge {
  font-size: 11px;
  font-weight: 500;
  color: #a1a1aa;
  background: rgba(255, 255, 255, 0.05);
  padding: 3px 10px;
  border-radius: 20px;
}

.header-info h1 {
  font-size: 24px;
  font-weight: 700;
  color: #fafafa;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.action-btn {
  height: 40px;
  padding: 0 20px;
  font-size: 13px;
}

.action-btn.start {
  background: rgba(34, 197, 94, 0.15);
  border: 1px solid rgba(34, 197, 94, 0.3);
  color: #4ade80;
}

.action-btn.start:hover {
  background: rgba(34, 197, 94, 0.25);
}

.action-btn.pause {
  background: rgba(245, 158, 11, 0.15);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #fbbf24;
}

.action-btn.pause:hover {
  background: rgba(245, 158, 11, 0.25);
}

.action-btn.stop {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.action-btn.stop:hover {
  background: rgba(239, 68, 68, 0.25);
}

.action-btn.delete {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #71717a;
}

.action-btn.delete:hover {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

/* Status Banner */
.status-banner {
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%);
  border: 1px solid rgba(168, 85, 247, 0.2);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  gap: 24px;
}

.status-banner.status-running {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%);
  border-color: rgba(59, 130, 246, 0.3);
}

.status-banner.status-completed {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(34, 197, 94, 0.05) 100%);
  border-color: rgba(34, 197, 94, 0.3);
}

.status-banner.status-failed {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%);
  border-color: rgba(239, 68, 68, 0.3);
}

.status-banner.status-paused {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%);
  border-color: rgba(245, 158, 11, 0.3);
}

.status-banner.status-cancelled {
  background: linear-gradient(135deg, rgba(107, 114, 128, 0.1) 0%, rgba(107, 114, 128, 0.05) 100%);
  border-color: rgba(107, 114, 128, 0.3);
}

.status-main {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 250px;
}

.status-icon {
  font-size: 32px;
  color: #a855f7;
}

.status-banner.status-running .status-icon { color: #3b82f6; }
.status-banner.status-completed .status-icon { color: #22c55e; }
.status-banner.status-failed .status-icon { color: #ef4444; }
.status-banner.status-paused .status-icon { color: #f59e0b; }
.status-banner.status-cancelled .status-icon { color: #6b7280; }

.status-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-label {
  font-size: 18px;
  font-weight: 600;
  color: #fafafa;
}

.status-progress,
.status-detail {
  font-size: 13px;
  color: #a1a1aa;
}

.status-error {
  font-size: 12px;
  color: #f87171;
}

.status-progress-bar {
  flex: 1;
  height: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #a855f7 0%, #7c3aed 100%);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.status-banner.status-running .progress-fill {
  background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
  animation: progress-glow 1.5s ease-in-out infinite;
}

.status-banner.status-completed .progress-fill {
  background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%);
}

.status-banner.status-cancelled .progress-fill {
  background: linear-gradient(90deg, #6b7280 0%, #4b5563 100%);
}

@keyframes progress-glow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.progress-percent {
  font-size: 20px;
  font-weight: 700;
  color: #a855f7;
  min-width: 60px;
  text-align: right;
}

.status-banner.status-running .progress-percent { color: #3b82f6; }
.status-banner.status-completed .progress-percent { color: #22c55e; }
.status-banner.status-cancelled .progress-percent { color: #6b7280; }

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

@media (max-width: 1400px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  padding: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.stat-icon {
  font-size: 24px;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.success {
  color: #4ade80;
  background: rgba(34, 197, 94, 0.1);
}

.stat-icon.danger {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
}

.stat-icon.info {
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.1);
}

.stat-icon.warn {
  color: #fbbf24;
  background: rgba(245, 158, 11, 0.1);
}

.stat-icon.primary {
  color: #c4b5fd;
  background: rgba(168, 85, 247, 0.1);
}

.stat-icon.secondary {
  color: #a1a1aa;
  background: rgba(255, 255, 255, 0.05);
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #fafafa;
}

.stat-label {
  font-size: 12px;
  color: #71717a;
}

/* Main Grid */
.main-grid {
  display: grid;
  grid-template-columns: 400px 1fr;
  gap: 24px;
}

@media (max-width: 1200px) {
  .main-grid {
    grid-template-columns: 1fr;
  }
}

/* Cards Common */
.config-card,
.channels-card,
.templates-card,
.logs-card {
  background: linear-gradient(180deg, #141417 0%, #0f0f12 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.card-header i {
  font-size: 16px;
  color: #a855f7;
}

.card-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #fafafa;
  margin: 0;
  flex: 1;
}

/* Left Column */
.left-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Config Card */
.config-content {
  padding: 18px 20px;
}

.config-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 10px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.config-row:last-child {
  border-bottom: none;
}

.config-label {
  font-size: 13px;
  color: #71717a;
}

.config-value {
  font-size: 13px;
  font-weight: 500;
  color: #e4e4e7;
  text-align: right;
}

.config-value.channel {
  color: #a855f7;
}

.config-value.emoji {
  font-size: 20px;
}

.config-value.time {
  font-family: 'SF Mono', monospace;
  font-size: 12px;
  color: #a1a1aa;
}

.config-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.config-tag {
  font-size: 11px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(168, 85, 247, 0.1);
  color: #c4b5fd;
}

.config-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 12px 0;
}

/* Channels Card */
.channels-list {
  padding: 12px 16px;
}

.channel-item {
  padding: 14px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 10px;
  margin-bottom: 10px;
}

.channel-item:last-child {
  margin-bottom: 0;
}

.channel-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.channel-name {
  font-size: 14px;
  font-weight: 600;
  color: #a855f7;
}

.channel-title {
  font-size: 12px;
  color: #71717a;
}

.channel-stats {
  display: flex;
  align-items: center;
  gap: 12px;
}

.channel-status {
  font-size: 10px;
}

.channel-sent {
  font-size: 12px;
  color: #a1a1aa;
}

.channel-error {
  display: block;
  font-size: 11px;
  color: #f87171;
  margin-top: 8px;
}

/* Templates Card */
.templates-list {
  padding: 12px 16px;
}

.template-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: rgba(168, 85, 247, 0.05);
  border-radius: 8px;
  margin-bottom: 8px;
}

.template-item:last-child {
  margin-bottom: 0;
}

.template-number {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: rgba(168, 85, 247, 0.2);
  color: #a855f7;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.template-content {
  font-size: 12px;
  color: #a1a1aa;
  line-height: 1.5;
}

/* Right Column - Logs */
.right-column {
  display: flex;
  flex-direction: column;
}

.logs-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.logs-count {
  font-size: 12px;
  color: #71717a;
  margin-left: auto;
}

.logs-filters {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.filter-tabs {
  display: flex;
  gap: 4px;
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: #71717a;
  font-size: 12px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-tab:hover {
  color: #a1a1aa;
  background: rgba(255, 255, 255, 0.04);
}

.filter-tab.active {
  color: #fafafa;
  background: rgba(168, 85, 247, 0.15);
}

.filter-count {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.1);
}

.filter-count.success {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.filter-count.danger {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.search-input {
  position: relative;
  flex: 1;
  max-width: 250px;
}

.search-input i {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #52525b;
  font-size: 14px;
}

.search-input :deep(.p-inputtext) {
  padding-left: 36px;
  height: 36px;
  font-size: 13px;
}

/* Logs List */
.logs-list {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  max-height: 600px;
}

.log-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 10px;
  margin-bottom: 8px;
  border-left: 3px solid transparent;
}

.log-item.success {
  border-left-color: #22c55e;
}

.log-item.error {
  border-left-color: #ef4444;
  background: rgba(239, 68, 68, 0.05);
}

.log-status {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.log-item.success .log-status {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.log-item.error .log-status {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.log-content {
  flex: 1;
  min-width: 0;
}

.log-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.log-target {
  font-size: 13px;
  font-weight: 500;
  color: #e4e4e7;
}

.log-time {
  font-size: 11px;
  color: #52525b;
}

.log-message {
  font-size: 12px;
  color: #a1a1aa;
  display: block;
}

.log-error {
  font-size: 12px;
  color: #f87171;
  display: block;
}

.log-comment {
  font-size: 12px;
  color: #a855f7;
  font-style: italic;
  display: block;
  margin-top: 4px;
}

.logs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px;
  color: #52525b;
}

.logs-empty i {
  font-size: 40px;
}

/* Not Found State */
.not-found-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 100px;
  text-align: center;
}

.not-found-state i {
  font-size: 60px;
  color: #f59e0b;
}

.not-found-state h2 {
  font-size: 20px;
  font-weight: 600;
  color: #fafafa;
  margin: 0;
}

.not-found-state p {
  font-size: 14px;
  color: #71717a;
  margin: 0;
}

/* Confirm Dialog */
.confirm-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
  padding: 20px 0;
}

.confirm-icon {
  font-size: 48px;
  color: #f87171;
}

.confirm-content p {
  font-size: 14px;
  color: #a1a1aa;
  margin: 0;
  max-width: 300px;
}

/* Dialog overrides */
:deep(.p-dialog) {
  background: #141417;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
}

:deep(.p-dialog .p-dialog-header) {
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.p-dialog .p-dialog-content) {
  background: transparent;
}

:deep(.p-dialog .p-dialog-footer) {
  background: transparent;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
</style>
