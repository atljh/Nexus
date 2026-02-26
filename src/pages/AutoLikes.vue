<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'

import { useTaskStore } from '@/stores/useTaskStore'
import { useAccountStore } from '@/stores/useAccountStore'
import { useGroupStore } from '@/stores/useGroupStore'
import type { Task } from '@/types'
import { REACTION_EMOJIS } from '@/types'

// Convert readonly array to mutable for Dropdown
const reactionOptions = [...REACTION_EMOJIS]

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const taskStore = useTaskStore()
const accountStore = useAccountStore()
const groupStore = useGroupStore()

// Form state
const channel = ref('')
const postId = ref<number | null>(null)
const selectedReactions = ref<string[]>(['👍'])
const emojiMode = ref<'single' | 'random' | 'all'>('single')
const totalActions = ref(10)
const minDelay = ref(30)
const maxDelay = ref(120)
const maxConcurrent = ref(1)
const selectedAccountIds = ref<number[]>([])
const selectedGroupId = ref<number | null>(null)

// UI state
const isCreating = ref(false)
const activeTab = ref(0)

// Tabs
const tabs = computed(() => [
  { label: t('autoLikes.settings') || 'Настройки', icon: 'pi pi-cog' },
  { label: t('autoLikes.selectAccounts') || 'Аккаунты', icon: 'pi pi-users' }
])

// Emoji mode options
const emojiModeOptions = [
  { value: 'single', label: 'Один эмодзи' },
  { value: 'random', label: 'Случайный' },
  { value: 'all', label: 'Все эмодзи' }
]

// Filter accounts by group and valid status
const availableAccounts = computed(() => {
  let accounts = accountStore.accounts.filter(a => a.status === 'valid')
  if (selectedGroupId.value) {
    accounts = accounts.filter(a => a.group_id === selectedGroupId.value)
  }
  return accounts
})

// Formatted account options for multiselect
const accountOptions = computed(() =>
  availableAccounts.value.map(a => ({
    value: a.id,
    label: a.username ? `@${a.username}` : a.phone || `ID: ${a.id}`
  }))
)

// Task status badge severity
function getStatusSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
  switch (status) {
    case 'completed': return 'success'
    case 'running': return 'info'
    case 'pending': return 'warn'
    case 'failed': return 'danger'
    case 'cancelled': return 'secondary'
    case 'paused': return 'warn'
    default: return 'secondary'
  }
}

// Create task
async function createTask() {
  if (!channel.value.trim()) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoLikes.errors.channelRequired'),
      life: 3000
    })
    return
  }

  if (selectedReactions.value.length === 0) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: 'Выберите хотя бы одну реакцию',
      life: 3000
    })
    return
  }

  if (selectedAccountIds.value.length === 0) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoLikes.errors.accountsRequired'),
      life: 3000
    })
    return
  }

  isCreating.value = true
  try {
    const task = await taskStore.createLikesTask({
      config: {
        channel: channel.value.trim(),
        post_id: postId.value || undefined,
        reactions: selectedReactions.value,
        emoji_mode: emojiMode.value
      },
      account_ids: selectedAccountIds.value,
      total_actions: totalActions.value,
      min_delay: minDelay.value,
      max_delay: maxDelay.value,
      max_concurrent: maxConcurrent.value
    })

    if (task) {
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('autoLikes.messages.taskCreated'),
        life: 3000
      })
    }
  } catch (e) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoLikes.messages.createFailed'),
      life: 3000
    })
  } finally {
    isCreating.value = false
  }
}

// Task actions
async function startTask(task: Task) {
  await taskStore.startTask(task.id)
  toast.add({
    severity: 'info',
    summary: t('autoLikes.messages.taskStarted'),
    life: 2000
  })
}

async function pauseTask(task: Task) {
  await taskStore.pauseTask(task.id)
}

async function cancelTask(task: Task) {
  await taskStore.cancelTask(task.id)
}

async function deleteTask(task: Task) {
  await taskStore.deleteTask(task.id)
  toast.add({
    severity: 'info',
    summary: t('autoLikes.messages.taskDeleted'),
    life: 2000
  })
}

function viewTaskDetails(task: Task) {
  router.push(`/task/${task.id}`)
}

async function refreshTasks() {
  await taskStore.fetchTasks('likes')
}

// Initialize
onMounted(async () => {
  await Promise.all([
    taskStore.fetchTasks('likes'),
    accountStore.fetchAccounts(),
    groupStore.fetchGroups()
  ])

  if (taskStore.hasRunningTasks) {
    taskStore.startPolling()
  }
})

onUnmounted(() => {
  taskStore.stopPolling()
})
</script>

<template>
  <MainLayout>
    <div class="autolikes-page">
      <!-- Page Header -->
      <div class="page-header">
        <div class="header-content">
          <div class="header-icon">
            <i class="pi pi-heart"></i>
          </div>
          <div class="header-text">
            <h1>{{ t('nav.autoLikes') }}</h1>
            <p class="header-subtitle">Автоматические реакции на посты в каналах</p>
          </div>
        </div>
        <div class="header-stats">
          <div class="stat-card">
            <span class="stat-value">{{ taskStore.tasks.filter(t => t.status === 'running').length }}</span>
            <span class="stat-label">Активные</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">{{ taskStore.tasks.filter(t => t.status === 'completed').length }}</span>
            <span class="stat-label">Завершены</span>
          </div>
        </div>
      </div>

      <div class="page-grid">
        <!-- Create Task Card -->
        <div class="create-card">
          <div class="card-header">
            <div class="card-header-icon">
              <i class="pi pi-plus-circle"></i>
            </div>
            <div class="card-header-text">
              <h2>{{ t('autoLikes.createTask') }}</h2>
              <span class="card-header-hint">Настройте параметры и запустите задачу</span>
            </div>
          </div>

          <!-- Custom Tabs -->
          <div class="custom-tabs">
            <button
              v-for="(tab, index) in tabs"
              :key="index"
              :class="['tab-btn', { active: activeTab === index }]"
              @click="activeTab = index"
            >
              <i :class="tab.icon"></i>
              <span>{{ tab.label }}</span>
            </button>
          </div>

          <!-- Tab Content -->
          <div class="tab-content">
            <!-- Settings Tab -->
            <div v-if="activeTab === 0" class="tab-panel">
              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-hashtag"></i>
                  <span>Целевой канал</span>
                </div>
                <div class="form-group">
                  <InputText
                    v-model="channel"
                    :placeholder="t('autoLikes.channelPlaceholder')"
                    class="w-full"
                  />
                </div>
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-cog"></i>
                  <span>Реакции</span>
                </div>
                <div class="form-group">
                  <label class="form-label">
                    <i class="pi pi-heart"></i>
                    {{ t('autoLikes.reaction') }}
                  </label>
                  <MultiSelect
                    v-model="selectedReactions"
                    :options="reactionOptions"
                    option-label="label"
                    option-value="value"
                    placeholder="Выберите реакции"
                    :maxSelectedLabels="5"
                    class="w-full"
                    display="chip"
                  />
                </div>
                <div class="form-group" style="margin-top: 14px">
                  <label class="form-label">
                    <i class="pi pi-sliders-h"></i>
                    Режим эмодзи
                  </label>
                  <Dropdown
                    v-model="emojiMode"
                    :options="emojiModeOptions"
                    option-label="label"
                    option-value="value"
                    class="w-full"
                  />
                  <small class="emoji-mode-hint">
                    <template v-if="emojiMode === 'single'">Первый эмодзи из списка для всех аккаунтов</template>
                    <template v-else-if="emojiMode === 'random'">Случайный эмодзи для каждого аккаунта</template>
                    <template v-else>Все эмодзи от каждого аккаунта</template>
                  </small>
                </div>

                <div class="form-group" style="margin-top: 14px">
                  <label class="form-label">{{ t('autoLikes.postId') }} ({{ t('common.optional') }})</label>
                  <InputNumber
                    v-model="postId"
                    :placeholder="t('autoLikes.postIdPlaceholder')"
                    class="w-full"
                    :use-grouping="false"
                  />
                </div>
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-chart-bar"></i>
                  <span>Лимиты</span>
                </div>
                <div class="form-grid-2">
                  <div class="form-group">
                    <label class="form-label">{{ t('autoLikes.totalReactions') }}</label>
                    <InputNumber
                      v-model="totalActions"
                      :min="1"
                      :max="10000"
                      class="w-full"
                      showButtons
                      buttonLayout="horizontal"
                      decrementButtonClass="decrement-btn"
                      incrementButtonClass="increment-btn"
                    />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Параллельно</label>
                    <InputNumber
                      v-model="maxConcurrent"
                      :min="1"
                      :max="10"
                      class="w-full"
                      showButtons
                      buttonLayout="horizontal"
                      decrementButtonClass="decrement-btn"
                      incrementButtonClass="increment-btn"
                    />
                  </div>
                </div>
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-clock"></i>
                  <span>Задержка между действиями</span>
                </div>
                <div class="delay-inputs">
                  <div class="form-group">
                    <label class="form-label">{{ t('autoLikes.minDelay') }}</label>
                    <div class="input-with-suffix">
                      <InputNumber
                        v-model="minDelay"
                        :min="1"
                        :max="3600"
                        class="w-full"
                      />
                      <span class="input-suffix">сек</span>
                    </div>
                  </div>
                  <div class="delay-separator">
                    <i class="pi pi-arrows-h"></i>
                  </div>
                  <div class="form-group">
                    <label class="form-label">{{ t('autoLikes.maxDelay') }}</label>
                    <div class="input-with-suffix">
                      <InputNumber
                        v-model="maxDelay"
                        :min="1"
                        :max="3600"
                        class="w-full"
                      />
                      <span class="input-suffix">сек</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Accounts Tab -->
            <div v-if="activeTab === 1" class="tab-panel">
              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-filter"></i>
                  <span>Фильтр аккаунтов</span>
                </div>
                <div class="form-group">
                  <label class="form-label">{{ t('autoLikes.filterByGroup') }}</label>
                  <Dropdown
                    v-model="selectedGroupId"
                    :options="[{ id: null, name: t('groups.allAccounts') }, ...groupStore.groups]"
                    option-label="name"
                    option-value="id"
                    class="w-full"
                  />
                </div>
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-users"></i>
                  <span>Выбор аккаунтов</span>
                  <span class="accounts-count">{{ availableAccounts.length }} доступно</span>
                </div>
                <div class="form-group">
                  <MultiSelect
                    v-model="selectedAccountIds"
                    :options="accountOptions"
                    option-label="label"
                    option-value="value"
                    :placeholder="t('autoLikes.selectAccountsPlaceholder')"
                    :maxSelectedLabels="5"
                    class="w-full"
                    display="chip"
                    filter
                    filterPlaceholder="Поиск аккаунта..."
                  />
                </div>
              </div>

              <div v-if="selectedAccountIds.length > 0" class="selected-accounts-preview">
                <div class="preview-header">
                  <span>Выбрано аккаунтов: {{ selectedAccountIds.length }}</span>
                  <Button
                    label="Сбросить"
                    icon="pi pi-times"
                    text
                    size="small"
                    @click="selectedAccountIds = []"
                  />
                </div>
                <div class="accounts-chips">
                  <span
                    v-for="id in selectedAccountIds.slice(0, 8)"
                    :key="id"
                    class="account-chip"
                  >
                    {{ accountOptions.find(a => a.value === id)?.label || id }}
                  </span>
                  <span v-if="selectedAccountIds.length > 8" class="more-accounts">
                    +{{ selectedAccountIds.length - 8 }} ещё
                  </span>
                </div>
              </div>

              <div v-else class="no-accounts-selected">
                <i class="pi pi-user-plus"></i>
                <p>Аккаунты не выбраны</p>
                <span>Выберите хотя бы один аккаунт для запуска задачи</span>
              </div>
            </div>
          </div>

          <!-- Create Button -->
          <div class="create-action">
            <div class="validation-summary">
              <div :class="['validation-item', { valid: channel.trim().length > 0 }]">
                <i :class="channel.trim().length > 0 ? 'pi pi-check' : 'pi pi-times'"></i>
                <span>Канал</span>
              </div>
              <div :class="['validation-item', { valid: selectedAccountIds.length > 0 }]">
                <i :class="selectedAccountIds.length > 0 ? 'pi pi-check' : 'pi pi-times'"></i>
                <span>Аккаунты</span>
              </div>
            </div>
            <Button
              :label="t('autoLikes.startTask')"
              icon="pi pi-play"
              :loading="isCreating"
              :disabled="!channel || selectedAccountIds.length === 0"
              class="create-task-btn"
              @click="createTask"
            />
          </div>
        </div>

        <!-- Tasks List Card -->
        <div class="tasks-card">
          <div class="card-header">
            <div class="card-header-icon tasks-icon">
              <i class="pi pi-list"></i>
            </div>
            <div class="card-header-text">
              <h2>{{ t('autoLikes.tasks') }}</h2>
              <span class="card-header-hint">{{ taskStore.tasks.length }} задач</span>
            </div>
            <Button
              v-if="taskStore.tasks.length > 0"
              icon="pi pi-refresh"
              text
              rounded
              @click="refreshTasks"
            />
          </div>

          <div v-if="taskStore.tasks.length > 0" class="tasks-list">
            <div
              v-for="task in taskStore.tasks"
              :key="task.id"
              :class="['task-item', `status-${task.status}`]"
            >
              <div class="task-main">
                <div class="task-id">
                  <span class="id-label">#{{ task.id }}</span>
                  <Tag
                    :value="t(`autoLikes.status.${task.status}`)"
                    :severity="getStatusSeverity(task.status)"
                    class="status-tag"
                  />
                </div>
                <div class="task-channel">
                  <i class="pi pi-hashtag"></i>
                  <span class="channel-name">{{ task.config?.channel }}</span>
                  <span class="reaction-emoji">{{ (task.config?.reactions || []).join('') }}</span>
                </div>
              </div>

              <div class="task-progress-section">
                <div class="progress-info">
                  <span class="progress-label">Прогресс</span>
                  <span class="progress-value">{{ task.completed_actions }}/{{ task.total_actions }}</span>
                </div>
                <div class="progress-bar-container">
                  <div
                    class="progress-bar-fill"
                    :style="{ width: `${task.progress}%` }"
                    :class="{ running: task.status === 'running' }"
                  ></div>
                </div>
              </div>

              <div class="task-actions">
                <Button
                  v-if="task.status === 'pending' || task.status === 'paused'"
                  icon="pi pi-play"
                  rounded
                  class="action-btn play"
                  v-tooltip.top="'Запустить'"
                  @click="startTask(task)"
                />
                <Button
                  v-if="task.status === 'running'"
                  icon="pi pi-pause"
                  rounded
                  class="action-btn pause"
                  v-tooltip.top="'Пауза'"
                  @click="pauseTask(task)"
                />
                <Button
                  v-if="task.status === 'running' || task.status === 'paused'"
                  icon="pi pi-stop"
                  rounded
                  class="action-btn stop"
                  v-tooltip.top="'Остановить'"
                  @click="cancelTask(task)"
                />
                <Button
                  icon="pi pi-eye"
                  rounded
                  class="action-btn view"
                  v-tooltip.top="'Детали'"
                  @click="viewTaskDetails(task)"
                />
                <Button
                  v-if="task.status !== 'running'"
                  icon="pi pi-trash"
                  rounded
                  class="action-btn delete"
                  v-tooltip.top="'Удалить'"
                  @click="deleteTask(task)"
                />
              </div>
            </div>
          </div>

          <div v-else class="empty-tasks">
            <div class="empty-icon">
              <i class="pi pi-inbox"></i>
            </div>
            <h3>Нет задач</h3>
            <p>Создайте первую задачу, заполнив форму слева</p>
          </div>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
/* Page Layout */
.autolikes-page {
  width: 100%;
  padding: 0;
}

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(236, 72, 153, 0.2) 0%, rgba(236, 72, 153, 0.05) 100%);
  border: 1px solid rgba(236, 72, 153, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-icon i {
  font-size: 24px;
  color: #ec4899;
}

.header-text h1 {
  font-size: 26px;
  font-weight: 700;
  color: #fafafa;
  margin: 0 0 4px 0;
  letter-spacing: -0.5px;
}

.header-subtitle {
  font-size: 14px;
  color: #71717a;
  margin: 0;
}

.header-stats {
  display: flex;
  gap: 12px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 12px 20px;
  text-align: center;
  min-width: 90px;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: #ec4899;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #71717a;
}

/* Page Grid */
.page-grid {
  display: grid;
  grid-template-columns: 480px 1fr;
  gap: 24px;
}

@media (max-width: 1280px) {
  .page-grid {
    grid-template-columns: 1fr;
  }
}

/* Cards Common Styles */
.create-card,
.tasks-card {
  background: linear-gradient(180deg, #141417 0%, #0f0f12 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 20px;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.card-header-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(236, 72, 153, 0.15) 0%, rgba(236, 72, 153, 0.05) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-header-icon i {
  font-size: 18px;
  color: #ec4899;
}

.card-header-icon.tasks-icon {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(59, 130, 246, 0.05) 100%);
}

.card-header-icon.tasks-icon i {
  color: #3b82f6;
}

.card-header-text {
  flex: 1;
}

.card-header-text h2 {
  font-size: 16px;
  font-weight: 600;
  color: #fafafa;
  margin: 0;
}

.card-header-hint {
  font-size: 12px;
  color: #71717a;
}

/* Custom Tabs */
.custom-tabs {
  display: flex;
  gap: 4px;
  padding: 16px 24px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border: none;
  background: transparent;
  color: #71717a;
  font-size: 13px;
  font-weight: 500;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn i {
  font-size: 14px;
}

.tab-btn:hover {
  color: #a1a1aa;
  background: rgba(255, 255, 255, 0.04);
}

.tab-btn.active {
  color: #ec4899;
  background: rgba(236, 72, 153, 0.12);
}

/* Tab Content */
.tab-content {
  padding: 24px;
}

.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Form Sections */
.form-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 14px;
  padding: 18px;
}

.form-section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.form-section-header i {
  font-size: 14px;
  color: #ec4899;
}

.form-section-header span {
  font-size: 13px;
  font-weight: 600;
  color: #e4e4e7;
}

.accounts-count {
  margin-left: auto;
  font-size: 11px;
  font-weight: 500;
  color: #ec4899;
  background: rgba(236, 72, 153, 0.1);
  padding: 4px 10px;
  border-radius: 20px;
}

.emoji-mode-hint {
  font-size: 11px;
  color: #71717a;
  margin-top: 4px;
}

/* Form Groups */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #a1a1aa;
}

.form-label i {
  font-size: 12px;
  color: #71717a;
}

.form-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

/* Delay Inputs */
.delay-inputs {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 12px;
  align-items: end;
}

.delay-separator {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 42px;
}

.delay-separator i {
  color: #52525b;
  font-size: 14px;
}

.input-with-suffix {
  position: relative;
}

.input-suffix {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: #71717a;
  pointer-events: none;
}

/* Selected Accounts Preview */
.selected-accounts-preview {
  background: rgba(236, 72, 153, 0.05);
  border: 1px solid rgba(236, 72, 153, 0.2);
  border-radius: 12px;
  padding: 14px;
  margin-top: 12px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.preview-header span {
  font-size: 12px;
  font-weight: 500;
  color: #ec4899;
}

.accounts-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.account-chip {
  background: rgba(236, 72, 153, 0.15);
  color: #f9a8d4;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
}

.more-accounts {
  color: #ec4899;
  font-size: 11px;
  font-weight: 500;
  padding: 4px 8px;
}

.no-accounts-selected {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.no-accounts-selected i {
  font-size: 40px;
  color: #3f3f46;
  margin-bottom: 12px;
}

.no-accounts-selected p {
  font-size: 14px;
  font-weight: 500;
  color: #71717a;
  margin: 0 0 4px 0;
}

.no-accounts-selected span {
  font-size: 12px;
  color: #52525b;
}

/* Create Action */
.create-action {
  padding: 20px 24px;
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.validation-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.validation-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #52525b;
}

.validation-item i {
  font-size: 12px;
}

.validation-item.valid {
  color: #22c55e;
}

.create-task-btn {
  width: 100%;
  height: 48px;
  font-size: 14px;
  font-weight: 600;
}

/* Tasks Card */
.tasks-card {
  display: flex;
  flex-direction: column;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 24px;
  max-height: calc(100vh - 320px);
  overflow-y: auto;
}

.task-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 20px;
  align-items: center;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  padding: 16px 20px;
  transition: all 0.2s ease;
}

.task-item:hover {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
}

.task-item.status-running {
  border-color: rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.05);
}

.task-item.status-completed {
  border-color: rgba(34, 197, 94, 0.3);
  background: rgba(34, 197, 94, 0.05);
}

.task-item.status-failed {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.05);
}

.task-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-id {
  display: flex;
  align-items: center;
  gap: 10px;
}

.id-label {
  font-size: 14px;
  font-weight: 600;
  color: #fafafa;
}

.status-tag {
  font-size: 10px;
  padding: 3px 8px;
}

.task-channel {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #71717a;
}

.task-channel i {
  font-size: 11px;
}

.channel-name {
  color: #a1a1aa;
}

.reaction-emoji {
  font-size: 16px;
}

/* Task Progress */
.task-progress-section {
  min-width: 160px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.progress-label {
  font-size: 11px;
  color: #52525b;
}

.progress-value {
  font-size: 11px;
  font-weight: 600;
  color: #a1a1aa;
}

.progress-bar-container {
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #ec4899 0%, #db2777 100%);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-bar-fill.running {
  animation: progress-pulse 1.5s ease-in-out infinite;
}

@keyframes progress-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* Task Actions */
.task-actions {
  display: flex;
  gap: 6px;
}

.action-btn {
  width: 34px;
  height: 34px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  color: #71717a;
  transition: all 0.15s ease;
}

.action-btn:hover {
  border-color: rgba(255, 255, 255, 0.15);
  color: #fafafa;
}

.action-btn.play:hover {
  background: rgba(34, 197, 94, 0.15);
  border-color: rgba(34, 197, 94, 0.5);
  color: #22c55e;
}

.action-btn.pause:hover {
  background: rgba(245, 158, 11, 0.15);
  border-color: rgba(245, 158, 11, 0.5);
  color: #f59e0b;
}

.action-btn.stop:hover,
.action-btn.delete:hover {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.5);
  color: #ef4444;
}

.action-btn.view:hover {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.5);
  color: #3b82f6;
}

/* Empty Tasks */
.empty-tasks {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 40px;
  text-align: center;
}

.empty-icon {
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.empty-icon i {
  font-size: 32px;
  color: #3f3f46;
}

.empty-tasks h3 {
  font-size: 16px;
  font-weight: 600;
  color: #71717a;
  margin: 0 0 6px 0;
}

.empty-tasks p {
  font-size: 13px;
  color: #52525b;
  margin: 0;
}

/* Override PrimeVue styles */
:deep(.p-inputnumber-buttons-horizontal .p-button) {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
  color: #71717a;
}

:deep(.p-inputnumber-buttons-horizontal .p-button:hover) {
  background: rgba(236, 72, 153, 0.15);
  color: #ec4899;
}

:deep(.p-inputtext),
:deep(.p-dropdown),
:deep(.p-multiselect),
:deep(.p-inputnumber) {
  width: 100%;
  max-width: 100%;
}

:deep(.p-inputnumber-input) {
  width: 100%;
}
</style>
