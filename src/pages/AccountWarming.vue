<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { useToast } from 'primevue/usetoast'
import { AccountPicker } from '@/components/shared'

import { useTaskStore } from '@/stores/useTaskStore'
import { useAccountStore } from '@/stores/useAccountStore'
import type { Task, WarmingSpeedPreset } from '@/types'

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const taskStore = useTaskStore()
const accountStore = useAccountStore()

const targetsInput = ref('')
const speedPreset = ref<WarmingSpeedPreset>('safe')
const selectedAccountIds = ref<number[]>([])
const isCreating = ref(false)

const FORM_KEY = 'nexus_warming_form'
const FORM_SAVE_DELAY_MS = 250
let formSaveTimer: number | null = null

const parsedTargets = computed(() => {
  const lines = targetsInput.value
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)

  const seen = new Set<string>()
  return lines.filter(line => {
    const key = line.toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
})

const speedOptions = computed(() => [
  {
    value: 'safe',
    label: t('warming.speed.safe'),
    description: t('warming.speed.safeHint')
  },
  {
    value: 'normal',
    label: t('warming.speed.normal'),
    description: t('warming.speed.normalHint')
  }
])

const estimatedPerAccountHours = computed(() => {
  if (parsedTargets.value.length <= 1) return 0
  const avgDelayHours = speedPreset.value === 'safe' ? 5 : 3
  return avgDelayHours * (parsedTargets.value.length - 1)
})

const runningTasks = computed(() => taskStore.tasks.filter(task => task.status === 'running'))

function saveForm() {
  localStorage.setItem(FORM_KEY, JSON.stringify({
    targetsInput: targetsInput.value,
    speedPreset: speedPreset.value,
    selectedAccountIds: selectedAccountIds.value
  }))
}

function clearPendingFormSave() {
  if (formSaveTimer !== null) {
    window.clearTimeout(formSaveTimer)
    formSaveTimer = null
  }
}

function scheduleFormSave() {
  clearPendingFormSave()
  formSaveTimer = window.setTimeout(() => {
    formSaveTimer = null
    saveForm()
  }, FORM_SAVE_DELAY_MS)
}

function flushPendingFormSave() {
  if (formSaveTimer === null) return
  clearPendingFormSave()
  saveForm()
}

function loadForm() {
  try {
    const saved = localStorage.getItem(FORM_KEY)
    if (!saved) return

    const data = JSON.parse(saved)
    if (typeof data.targetsInput === 'string') targetsInput.value = data.targetsInput
    if (data.speedPreset === 'safe' || data.speedPreset === 'normal') {
      speedPreset.value = data.speedPreset
    }
    if (Array.isArray(data.selectedAccountIds)) {
      selectedAccountIds.value = data.selectedAccountIds
    }
  } catch {
    // ignore malformed local state
  }
}

watch([targetsInput, speedPreset, selectedAccountIds], scheduleFormSave, { deep: true })

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

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return t('common.time.justNow')
  if (mins < 60) return t('common.time.minutesShort', { count: mins })
  const hours = Math.floor(mins / 60)
  if (hours < 24) return t('common.time.hoursShort', { count: hours })
  const days = Math.floor(hours / 24)
  return t('common.time.daysShort', { count: days })
}

async function createTask() {
  if (parsedTargets.value.length === 0) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('warming.errors.targetsRequired'),
      life: 3000
    })
    return
  }

  if (selectedAccountIds.value.length === 0) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('warming.errors.accountsRequired'),
      life: 3000
    })
    return
  }

  isCreating.value = true
  try {
    const task = await taskStore.createWarmingTask({
      config: {
        targets: parsedTargets.value,
        speed_preset: speedPreset.value
      },
      account_ids: selectedAccountIds.value,
      max_concurrent: 1
    })

    if (task) {
      clearPendingFormSave()
      localStorage.removeItem(FORM_KEY)

      if ((task as Task & { skipped_accounts?: number }).skipped_accounts) {
        toast.add({
          severity: 'warn',
          summary: t('common.warning'),
          detail: t('warming.messages.accountsSkipped', { count: (task as Task & { skipped_accounts?: number }).skipped_accounts }),
          life: 5000
        })
      }

      const started = await taskStore.startTask(task.id)
      toast.add({
        severity: started ? 'success' : 'warn',
        summary: started ? t('common.success') : t('common.warning'),
        detail: started ? t('warming.messages.taskStarted') : t('warming.messages.taskCreated'),
        life: 3000
      })
    }
  } catch {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('warming.messages.createFailed'),
      life: 3000
    })
  } finally {
    isCreating.value = false
  }
}

async function startTask(task: Task) {
  const ok = await taskStore.startTask(task.id)
  if (!ok) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('taskResults.loadError'),
      life: 2500
    })
  }
}

async function pauseTask(task: Task) {
  const ok = await taskStore.pauseTask(task.id)
  if (!ok) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('taskResults.loadError'),
      life: 2500
    })
  }
}

async function cancelTask(task: Task) {
  const ok = await taskStore.cancelTask(task.id)
  if (!ok) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('taskResults.loadError'),
      life: 2500
    })
  }
}

async function restartTask(task: Task) {
  const result = await taskStore.restartTask(task.id)
  if (!result) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('taskResults.loadError'),
      life: 2500
    })
  }
}

async function deleteTask(task: Task) {
  const deleted = await taskStore.deleteTask(task.id)
  if (!deleted) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('taskResults.loadError'),
      life: 2500
    })
    return
  }

  toast.add({
    severity: 'info',
    summary: t('warming.messages.taskDeleted'),
    life: 2000
  })
}

function viewTaskDetails(task: Task) {
  router.push(`/task/${task.id}`)
}

async function refreshTasks() {
  await taskStore.fetchTasks('warming')
}

onMounted(async () => {
  loadForm()
  await Promise.all([
    taskStore.fetchTasks('warming'),
    accountStore.fetchAccounts()
  ])

  if (taskStore.hasRunningTasks) {
    taskStore.startPolling()
  }
})

onUnmounted(() => {
  flushPendingFormSave()
  taskStore.stopPolling()
})
</script>

<template>
  <MainLayout>
    <div class="warming-page">
      <div class="page-header">
        <div class="header-content">
          <div class="header-icon">
            <i class="pi pi-sun"></i>
          </div>
          <div class="header-text">
            <h1>{{ t('nav.warming') }}</h1>
            <p class="header-subtitle">{{ t('warming.subtitle') }}</p>
          </div>
        </div>

        <div class="header-stats">
          <div class="stat-card">
            <span class="stat-value">{{ runningTasks.length }}</span>
            <span class="stat-label">{{ t('warming.statsActive') }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">{{ taskStore.tasks.filter(task => task.status === 'completed').length }}</span>
            <span class="stat-label">{{ t('warming.statsCompleted') }}</span>
          </div>
        </div>
      </div>

      <div class="page-grid">
        <div class="create-card">
          <div class="card-header">
            <div class="card-header-icon">
              <i class="pi pi-plus-circle"></i>
            </div>
            <div class="card-header-text">
              <h2>{{ t('warming.createTask') }}</h2>
              <span class="card-header-hint">{{ t('warming.createTaskHint') }}</span>
            </div>
          </div>

          <div class="card-body">
            <AccountPicker
              v-model="selectedAccountIds"
              accent-color="#f59e0b"
            />

            <div class="form-section">
              <div class="form-section-header">
                <i class="pi pi-list"></i>
                <span>{{ t('warming.targetsTitle') }}</span>
              </div>

              <Textarea
                v-model="targetsInput"
                autoResize
                :rows="8"
                class="targets-input"
                :placeholder="t('warming.targetsPlaceholder')"
              />

              <div class="helper-row">
                <span>{{ t('warming.targetsCount', { count: parsedTargets.length }) }}</span>
                <span>{{ t('warming.supportedFormats') }}</span>
              </div>
            </div>

            <div class="form-section">
              <div class="form-section-header">
                <i class="pi pi-clock"></i>
                <span>{{ t('warming.speedTitle') }}</span>
              </div>

              <Select
                v-model="speedPreset"
                :options="speedOptions"
                option-label="label"
                option-value="value"
                class="speed-select"
              />

              <div class="speed-hint">
                {{
                  speedOptions.find(option => option.value === speedPreset)?.description
                }}
              </div>

              <div v-if="estimatedPerAccountHours > 0" class="estimate-box">
                {{ t('warming.estimatePerAccount', { hours: estimatedPerAccountHours }) }}
              </div>
            </div>
          </div>

          <div class="create-action">
            <button
              class="launch-btn"
              :class="{ ready: parsedTargets.length > 0 && selectedAccountIds.length > 0, loading: isCreating }"
              :disabled="parsedTargets.length === 0 || selectedAccountIds.length === 0 || isCreating"
              @click="createTask"
            >
              <span class="launch-btn-glow"></span>
              <span class="launch-btn-content">
                <i v-if="isCreating" class="pi pi-spin pi-spinner"></i>
                <i v-else class="pi pi-play"></i>
                <span>{{ t('warming.startTask') }}</span>
              </span>
              <span class="launch-btn-badges">
                <span :class="['badge', { ok: parsedTargets.length > 0 }]">
                  <i :class="parsedTargets.length > 0 ? 'pi pi-check' : 'pi pi-minus'"></i>
                  {{ t('warming.badgeTargets', { count: parsedTargets.length }) }}
                </span>
                <span :class="['badge', { ok: selectedAccountIds.length > 0 }]">
                  <i :class="selectedAccountIds.length > 0 ? 'pi pi-check' : 'pi pi-minus'"></i>
                  {{ t('warming.badgeAccounts', { count: selectedAccountIds.length }) }}
                </span>
              </span>
            </button>
          </div>
        </div>

        <div class="tasks-card">
          <div class="card-header">
            <div class="card-header-icon tasks-icon">
              <i class="pi pi-list"></i>
            </div>
            <div class="card-header-text">
              <h2>{{ t('warming.tasks') }}</h2>
              <span class="card-header-hint">{{ t('warming.tasksCount', { count: taskStore.tasks.length }) }}</span>
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
                    :value="t(`taskResults.status.${task.status}`)"
                    :severity="getStatusSeverity(task.status)"
                    class="status-tag"
                  />
                </div>

                <div class="task-targets">
                  <i class="pi pi-hashtag"></i>
                  <span class="targets-preview">
                    {{ (task.config?.targets || []).slice(0, 2).join(', ') }}
                  </span>
                  <span v-if="(task.config?.targets || []).length > 2" class="targets-more">
                    +{{ (task.config?.targets || []).length - 2 }}
                  </span>
                </div>
              </div>

              <div class="task-meta">
                <span class="task-accounts-count">
                  <i class="pi pi-users"></i> {{ task.accounts_count }}
                </span>
                <span class="task-preset">{{ t(`warming.speed.${task.config?.speed_preset || 'safe'}`) }}</span>
                <span class="task-time">{{ timeAgo(task.created_at) }}</span>
              </div>

              <div class="task-progress-section">
                <div class="progress-info">
                  <span class="progress-label">{{ t('warming.progress') }}</span>
                  <span class="progress-value">{{ task.completed_actions + task.failed_actions }}/{{ task.total_actions }}</span>
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
                  @click="startTask(task)"
                />
                <Button
                  v-if="task.status === 'running'"
                  icon="pi pi-pause"
                  rounded
                  class="action-btn pause"
                  @click="pauseTask(task)"
                />
                <Button
                  v-if="task.status === 'running' || task.status === 'paused'"
                  icon="pi pi-stop"
                  rounded
                  class="action-btn stop"
                  @click="cancelTask(task)"
                />
                <Button
                  v-if="task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled'"
                  icon="pi pi-refresh"
                  rounded
                  class="action-btn restart"
                  @click="restartTask(task)"
                />
                <Button
                  icon="pi pi-eye"
                  rounded
                  class="action-btn view"
                  @click="viewTaskDetails(task)"
                />
                <Button
                  v-if="task.status !== 'running' && task.status !== 'paused'"
                  icon="pi pi-trash"
                  rounded
                  class="action-btn delete"
                  @click="deleteTask(task)"
                />
              </div>
            </div>
          </div>

          <div v-else class="empty-tasks">
            <div class="empty-visual">
              <div class="empty-rings">
                <span class="ring ring-1"></span>
                <span class="ring ring-2"></span>
                <span class="ring ring-3"></span>
              </div>
              <i class="pi pi-sun"></i>
            </div>
            <h3>{{ t('warming.noTasks') }}</h3>
            <p>{{ t('warming.noTasksHint') }}</p>
          </div>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.warming-page {
  width: 100%;
  height: calc(100vh - 40px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
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
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.22) 0%, rgba(245, 158, 11, 0.06) 100%);
  border: 1px solid rgba(245, 158, 11, 0.32);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-icon i {
  font-size: 24px;
  color: #f59e0b;
}

.header-text h1 {
  font-size: 26px;
  font-weight: 700;
  color: #fafafa;
  margin: 0 0 4px;
  letter-spacing: -0.5px;
}

.header-subtitle {
  font-size: 14px;
  color: #8b8b95;
  margin: 0;
}

.header-stats {
  display: flex;
  gap: 12px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px 20px;
  text-align: center;
  min-width: 90px;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: #f59e0b;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #8b8b95;
}

.page-grid {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 24px;
  flex: 1;
  min-height: 0;
}

@media (max-width: 1280px) {
  .page-grid {
    grid-template-columns: 1fr;
  }
}

.create-card,
.tasks-card {
  background: linear-gradient(180deg, #161619 0%, #111114 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.card-header-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: rgba(245, 158, 11, 0.14);
  color: #f59e0b;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tasks-icon {
  background: rgba(255, 255, 255, 0.08);
  color: #d4d4d8;
}

.card-header-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.card-header-text h2 {
  margin: 0;
  font-size: 18px;
  color: #fafafa;
}

.card-header-hint {
  font-size: 12px;
  color: #8b8b95;
}

.card-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #e4e4e7;
  font-size: 13px;
  font-weight: 600;
}

.targets-input,
.speed-select {
  width: 100%;
}

.helper-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: #8b8b95;
}

.speed-hint {
  font-size: 12px;
  color: #a1a1aa;
}

.estimate-box {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.14);
  color: #f6c453;
  font-size: 12px;
}

.create-action {
  padding: 18px 20px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.launch-btn {
  width: 100%;
  position: relative;
  border: none;
  border-radius: 18px;
  padding: 18px 18px 16px;
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.16), rgba(245, 158, 11, 0.08));
  color: #f5f5f5;
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.18s ease, border-color 0.18s ease;
  border: 1px solid rgba(245, 158, 11, 0.16);
}

.launch-btn.ready {
  border-color: rgba(245, 158, 11, 0.34);
}

.launch-btn:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.launch-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.launch-btn-glow {
  position: absolute;
  inset: -40% auto auto 20%;
  width: 160px;
  height: 160px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(251, 191, 36, 0.2) 0%, rgba(251, 191, 36, 0) 72%);
  pointer-events: none;
}

.launch-btn-content,
.launch-btn-badges {
  position: relative;
  z-index: 1;
}

.launch-btn-content {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 12px;
}

.launch-btn-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #c7c7cf;
  font-size: 12px;
  font-weight: 600;
}

.badge.ok {
  background: rgba(245, 158, 11, 0.18);
  color: #fcd34d;
}

.tasks-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item {
  border-radius: 16px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-main,
.task-id,
.task-meta,
.progress-info,
.task-actions,
.task-targets {
  display: flex;
  align-items: center;
}

.task-main,
.task-meta,
.progress-info {
  justify-content: space-between;
  gap: 12px;
}

.task-id {
  gap: 10px;
}

.id-label {
  font-weight: 700;
  color: #fafafa;
}

.task-targets {
  gap: 8px;
  color: #d4d4d8;
  min-width: 0;
}

.targets-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.targets-more {
  color: #fbbf24;
  font-size: 12px;
}

.task-meta {
  font-size: 12px;
  color: #8b8b95;
}

.task-preset {
  color: #f6c453;
}

.task-progress-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-label,
.progress-value {
  font-size: 12px;
  color: #a1a1aa;
}

.progress-bar-container {
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
  transition: width 0.2s ease;
}

.progress-bar-fill.running {
  box-shadow: 0 0 12px rgba(245, 158, 11, 0.34);
}

.task-actions {
  gap: 8px;
  justify-content: flex-end;
}

.action-btn {
  width: 34px;
  height: 34px;
}

.empty-tasks {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #8b8b95;
  text-align: center;
  padding: 24px;
}

.empty-visual {
  position: relative;
  width: 88px;
  height: 88px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-visual i {
  font-size: 26px;
  color: #f59e0b;
  position: relative;
  z-index: 1;
}

.empty-rings {
  position: absolute;
  inset: 0;
}

.ring {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  border: 1px solid rgba(245, 158, 11, 0.12);
}

.ring-2 {
  inset: 10px;
}

.ring-3 {
  inset: 20px;
}
</style>
