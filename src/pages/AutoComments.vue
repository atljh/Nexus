<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import MultiSelect from 'primevue/multiselect'
import AutoComplete from 'primevue/autocomplete'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'
import { AccountPicker } from '@/components/shared'

import { useTaskStore } from '@/stores/useTaskStore'
import { useAccountStore } from '@/stores/useAccountStore'
import type { Task, CommentTemplate } from '@/types'
import { DEFAULT_COMMENT_TEMPLATES } from '@/types'

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const taskStore = useTaskStore()
const accountStore = useAccountStore()

// Form state
const channels = ref<string[]>([])
const selectedTemplateIds = ref<number[]>([])
const customTemplates = ref<string[]>([])
const rotationMode = ref<'random' | 'round_robin'>('random')
const commentsPerAccount = ref(10)
const totalActions = ref(50)
const minDelay = ref(60)
const maxDelay = ref(300)
const selectedAccountIds = ref<number[]>([])

// Template management
const showTemplateDialog = ref(false)
const newTemplateName = ref('')
const newTemplateContent = ref('')
const templatePreview = ref<string[]>([])

// UI state
const isCreating = ref(false)
const activeTab = ref(0)

// Tabs configuration (Settings + Templates only, accounts moved to settings)
const tabs = computed(() => [
  { label: t('autoComments.settings'), icon: 'pi pi-cog' },
  { label: t('autoComments.templates'), icon: 'pi pi-file-edit' }
])

// Rotation mode options
const rotationOptions = computed(() => [
  { value: 'random', label: t('autoComments.rotation.random') },
  { value: 'round_robin', label: t('autoComments.rotation.roundRobin') }
])

// Template options for multiselect
const templateOptions = computed(() =>
  taskStore.templates.map(tmpl => ({
    value: tmpl.id,
    label: tmpl.name
  }))
)

// Combined templates for task
const selectedTemplates = computed(() => {
  const fromDb = taskStore.templates
    .filter(tmpl => selectedTemplateIds.value.includes(tmpl.id))
    .map(tmpl => tmpl.content)
  return [...fromDb, ...customTemplates.value]
})

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

// Create task and auto-start
async function createTask() {
  if (channels.value.length === 0) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoComments.errors.channelsRequired'),
      life: 3000
    })
    return
  }

  // Validate all channel formats
  const invalidChannel = channels.value.find(ch => {
    const clean = ch.startsWith('@') ? ch.slice(1) : ch
    return !/^[a-zA-Z0-9_]{5,32}$/.test(clean)
  })
  if (invalidChannel) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoComments.errors.invalidChannel', { channel: invalidChannel }),
      life: 3000
    })
    return
  }

  if (selectedTemplates.value.length === 0) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoComments.errors.templatesRequired'),
      life: 3000
    })
    return
  }

  if (selectedAccountIds.value.length === 0) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoComments.errors.accountsRequired'),
      life: 3000
    })
    return
  }

  isCreating.value = true
  try {
    const task = await taskStore.createCommentsTask({
      config: {
        channels: channels.value,
        templates: selectedTemplates.value,
        rotation_mode: rotationMode.value,
        comments_per_account: commentsPerAccount.value,
        mode: 'single'
      },
      account_ids: selectedAccountIds.value,
      total_actions: totalActions.value,
      min_delay: minDelay.value,
      max_delay: maxDelay.value
    })

    if (task) {
      // Warn if some accounts were skipped
      if ((task as any).skipped_accounts) {
        toast.add({
          severity: 'warn',
          summary: t('common.warning'),
          detail: t('autoComments.messages.accountsSkipped', { count: (task as any).skipped_accounts }),
          life: 5000
        })
      }
      // Auto-start the created task
      const started = await taskStore.startTask(task.id)
      if (started) {
        toast.add({
          severity: 'success',
          summary: t('common.success'),
          detail: t('autoComments.messages.taskStarted'),
          life: 3000
        })
      } else {
        toast.add({
          severity: 'warn',
          summary: t('common.warning'),
          detail: t('autoComments.messages.taskCreated'),
          life: 3000
        })
      }
    }
  } catch (e) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoComments.messages.createFailed'),
      life: 3000
    })
  } finally {
    isCreating.value = false
  }
}

// Computed task counts
const runningTasks = computed(() => taskStore.tasks.filter(t => t.status === 'running'))
const pendingTasks = computed(() => taskStore.tasks.filter(t => t.status === 'pending' || t.status === 'paused'))

// Batch actions
async function startAllPending() {
  const tasks = [...pendingTasks.value]
  let started = 0
  for (const task of tasks) {
    if (await taskStore.startTask(task.id)) {
      started += 1
    }
  }
  if (started > 0) {
    toast.add({
      severity: 'info',
      summary: t('autoComments.tasksStarted', { count: started }),
      life: 2000
    })
  }
  if (started < tasks.length) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('taskResults.loadError'),
      life: 2500
    })
  }
}

async function stopAllRunning() {
  const tasks = [...runningTasks.value]
  let stopped = 0
  for (const task of tasks) {
    if (await taskStore.cancelTask(task.id)) {
      stopped += 1
    }
  }
  if (stopped > 0) {
    toast.add({
      severity: 'info',
      summary: t('autoComments.tasksStopped'),
      life: 2000
    })
  }
  if (stopped < tasks.length) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('taskResults.loadError'),
      life: 2500
    })
  }
}

// Template management
async function createTemplate() {
  if (!newTemplateName.value.trim() || !newTemplateContent.value.trim()) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoComments.errors.templateRequired'),
      life: 3000
    })
    return
  }

  const template = await taskStore.createTemplate(
    newTemplateName.value.trim(),
    newTemplateContent.value.trim()
  )

  if (template) {
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('autoComments.messages.templateCreated'),
      life: 3000
    })
    newTemplateName.value = ''
    newTemplateContent.value = ''
    showTemplateDialog.value = false
  }
}

async function deleteTemplate(template: CommentTemplate) {
  const success = await taskStore.deleteTemplate(template.id)
  if (success) {
    selectedTemplateIds.value = selectedTemplateIds.value.filter(id => id !== template.id)
    toast.add({
      severity: 'info',
      summary: t('autoComments.messages.templateDeleted'),
      life: 2000
    })
  }
}

async function loadDefaultTemplates() {
  for (const template of DEFAULT_COMMENT_TEMPLATES) {
    await taskStore.createTemplate(template.name, template.content)
  }
  toast.add({
    severity: 'success',
    summary: t('autoComments.messages.defaultsLoaded'),
    life: 2000
  })
}

// Toggle template selection
function toggleTemplate(templateId: number) {
  const index = selectedTemplateIds.value.indexOf(templateId)
  if (index === -1) {
    selectedTemplateIds.value.push(templateId)
  } else {
    selectedTemplateIds.value.splice(index, 1)
  }
}

// Refresh tasks
async function refreshTasks() {
  await taskStore.fetchTasks('comments')
}

// Preview spintax
function generatePreview() {
  const content = newTemplateContent.value
  templatePreview.value = []
  for (let i = 0; i < 3; i++) {
    let result = content
    const regex = /\{([^{}]+)\}/g
    result = result.replace(regex, (_, options) => {
      const parts = options.split('|')
      return parts[Math.floor(Math.random() * parts.length)]
    })
    templatePreview.value.push(result)
  }
}

// Watch for template content changes
watch(newTemplateContent, () => {
  if (newTemplateContent.value) {
    generatePreview()
  } else {
    templatePreview.value = []
  }
})

// Task actions
async function startTask(task: Task) {
  if (task.status === 'running') return
  const ok = await taskStore.startTask(task.id)
  if (ok) {
    toast.add({
      severity: 'info',
      summary: t('autoComments.messages.taskStarted'),
      life: 2000
    })
    return
  }
  toast.add({
    severity: 'error',
    summary: t('common.error'),
    detail: t('taskResults.loadError'),
    life: 2500
  })
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
  if (result) {
    toast.add({
      severity: 'success',
      summary: t('taskResults.messages.restarted'),
      life: 2000
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
    summary: t('autoComments.messages.taskDeleted'),
    life: 2000
  })
}

function viewTaskDetails(task: Task) {
  router.push(`/task/${task.id}`)
}

// Initialize
onMounted(async () => {
  await Promise.all([
    taskStore.fetchTasks('comments'),
    taskStore.fetchTemplates(),
    accountStore.fetchAccounts()
  ])

  if (taskStore.hasRunningTasks) {
    taskStore.startPolling()
  }
})

onUnmounted(() => {
  if (!taskStore.hasRunningTasks) {
    taskStore.stopPolling()
  }
})
</script>

<template>
  <MainLayout>
    <div class="autocomments-page">
      <!-- Page Header -->
      <div class="page-header">
        <div class="header-content">
          <div class="header-icon">
            <i class="pi pi-comments"></i>
          </div>
          <div class="header-text">
            <h1>{{ t('nav.autoComments') }}</h1>
            <p class="header-subtitle">{{ t('autoComments.subtitle') }}</p>
          </div>
        </div>
        <div class="header-right">
          <!-- Control panel -->
          <div v-if="taskStore.tasks.length > 0" class="control-panel">
            <div class="control-status" :class="{ active: runningTasks.length > 0 }">
              <span class="status-dot"></span>
              <span class="status-text">
                <template v-if="runningTasks.length > 0">{{ t('autoComments.controlStatus.running', { count: runningTasks.length }) }}</template>
                <template v-else-if="pendingTasks.length > 0">{{ t('autoComments.controlStatus.pending', { count: pendingTasks.length }) }}</template>
                <template v-else>{{ t('autoComments.controlStatus.none') }}</template>
              </span>
            </div>
            <div class="control-buttons">
              <button
                v-if="pendingTasks.length > 0 && runningTasks.length === 0"
                class="ctrl-btn ctrl-start"
                @click="startAllPending"
              >
                <i class="pi pi-play"></i>
                <span>{{ t('autoComments.controlStart') }}</span>
              </button>
              <button
                v-if="runningTasks.length > 0"
                class="ctrl-btn ctrl-stop"
                @click="stopAllRunning"
              >
                <i class="pi pi-stop-circle"></i>
                <span>{{ t('autoComments.controlStop') }}</span>
              </button>
            </div>
          </div>
          <div class="header-stats">
            <div class="stat-card">
              <span class="stat-value">{{ runningTasks.length }}</span>
              <span class="stat-label">{{ t('autoComments.statsActive') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ taskStore.tasks.filter(t => t.status === 'completed').length }}</span>
              <span class="stat-label">{{ t('autoComments.statsCompleted') }}</span>
            </div>
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
              <h2>{{ t('autoComments.createTask') }}</h2>
              <span class="card-header-hint">{{ t('autoComments.createTaskHint') }}</span>
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
              <!-- Account Picker -->
              <AccountPicker
                v-model="selectedAccountIds"
                accent-color="#a855f7"
              />
              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-hashtag"></i>
                  <span>{{ t('autoComments.targetChannels') }}</span>
                </div>
                <div class="form-group">
                  <AutoComplete
                    v-model="channels"
                    :placeholder="t('autoComments.channelsPlaceholder')"
                    class="w-full custom-chips"
                    separator=","
                    multiple
                    :typeahead="false"
                  />
                  <small class="input-hint">
                    <i class="pi pi-info-circle"></i>
                    {{ t('autoComments.channelsHint') }}
                  </small>
                </div>
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-cog"></i>
                  <span>{{ t('autoComments.operatingMode') }}</span>
                </div>
                <div class="form-group">
                  <label class="form-label">
                    <i class="pi pi-sync"></i>
                    {{ t('autoComments.rotationMode') }}
                  </label>
                  <Select
                    v-model="rotationMode"
                    :options="rotationOptions"
                    option-label="label"
                    option-value="value"
                    class="w-full"
                  />
                </div>
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-chart-bar"></i>
                  <span>{{ t('autoComments.limits') }}</span>
                </div>
                <div class="form-grid-2">
                  <div class="form-group">
                    <label class="form-label">{{ t('autoComments.commentsPerAccount') }}</label>
                    <InputNumber
                      v-model="commentsPerAccount"
                      :min="1"
                      :max="100"
                      class="w-full"
                      showButtons
                      buttonLayout="horizontal"
                      decrementButtonClass="decrement-btn"
                      incrementButtonClass="increment-btn"
                    />
                  </div>
                  <div class="form-group">
                    <label class="form-label">{{ t('autoComments.totalComments') }}</label>
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
                </div>
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-clock"></i>
                  <span>{{ t('autoComments.delay') }}</span>
                </div>
                <div class="delay-inputs">
                  <div class="form-group">
                    <label class="form-label">{{ t('autoComments.minDelay') }}</label>
                    <div class="input-with-suffix">
                      <InputNumber
                        v-model="minDelay"
                        :min="1"
                        :max="3600"
                        class="w-full"
                      />
                      <span class="input-suffix">{{ t('autoComments.sec') }}</span>
                    </div>
                  </div>
                  <div class="delay-separator">
                    <i class="pi pi-arrows-h"></i>
                  </div>
                  <div class="form-group">
                    <label class="form-label">{{ t('autoComments.maxDelay') }}</label>
                    <div class="input-with-suffix">
                      <InputNumber
                        v-model="maxDelay"
                        :min="1"
                        :max="3600"
                        class="w-full"
                      />
                      <span class="input-suffix">{{ t('autoComments.sec') }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Templates Tab -->
            <div v-if="activeTab === 1" class="tab-panel">
              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-file-edit"></i>
                  <span>{{ t('autoComments.selectTemplates') }}</span>
                </div>
                <div class="form-group">
                  <MultiSelect
                    v-model="selectedTemplateIds"
                    :options="templateOptions"
                    option-label="label"
                    option-value="value"
                    :placeholder="t('autoComments.selectTemplatesPlaceholder')"
                    class="w-full"
                    display="chip"
                  />
                </div>
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-pencil"></i>
                  <span>{{ t('autoComments.customComments') }}</span>
                </div>
                <div class="form-group">
                  <AutoComplete
                    v-model="customTemplates"
                    :placeholder="t('autoComments.customTemplatesPlaceholder')"
                    class="w-full custom-chips"
                    multiple
                    :typeahead="false"
                  />
                  <small class="input-hint">
                    <i class="pi pi-info-circle"></i>
                    {{ t('autoComments.customTemplatesHint') }}
                  </small>
                </div>
              </div>

              <div class="template-actions-bar">
                <Button
                  :label="t('autoComments.createTemplate')"
                  icon="pi pi-plus"
                  class="create-template-btn"
                  @click="showTemplateDialog = true"
                />
                <Button
                  v-if="taskStore.templates.length === 0"
                  :label="t('autoComments.loadDefaults')"
                  icon="pi pi-download"
                  severity="secondary"
                  outlined
                  @click="loadDefaultTemplates"
                />
              </div>

              <div v-if="taskStore.templates.length > 0" class="templates-grid">
                <div
                  v-for="tmpl in taskStore.templates"
                  :key="tmpl.id"
                  :class="['template-card', { selected: selectedTemplateIds.includes(tmpl.id) }]"
                  @click="toggleTemplate(tmpl.id)"
                >
                  <div class="template-card-header">
                    <div class="template-checkbox">
                      <i :class="selectedTemplateIds.includes(tmpl.id) ? 'pi pi-check-circle' : 'pi pi-circle'"></i>
                    </div>
                    <span class="template-name">{{ tmpl.name }}</span>
                    <Button
                      icon="pi pi-trash"
                      text
                      rounded
                      severity="danger"
                      size="small"
                      class="template-delete-btn"
                      @click.stop="deleteTemplate(tmpl)"
                    />
                  </div>
                  <p class="template-content">{{ tmpl.content }}</p>
                </div>
              </div>

              <div v-else class="empty-templates">
                <i class="pi pi-file-edit"></i>
                <p>{{ t('autoComments.noTemplates') }}</p>
                <span>{{ t('autoComments.noTemplatesHint') }}</span>
              </div>
            </div>
          </div>

          <!-- Create Button -->
          <div class="create-action">
            <button
              class="launch-btn"
              :class="{ ready: channels.length > 0 && selectedTemplates.length > 0 && selectedAccountIds.length > 0, loading: isCreating }"
              :disabled="channels.length === 0 || selectedTemplates.length === 0 || selectedAccountIds.length === 0 || isCreating"
              @click="createTask"
            >
              <span class="launch-btn-glow"></span>
              <span class="launch-btn-content">
                <i v-if="isCreating" class="pi pi-spin pi-spinner"></i>
                <i v-else class="pi pi-play"></i>
                <span>{{ t('autoComments.startTask') }}</span>
              </span>
              <span class="launch-btn-badges">
                <span :class="['badge', { ok: channels.length > 0 }]">
                  <i :class="channels.length > 0 ? 'pi pi-check' : 'pi pi-minus'"></i>
                  {{ t('autoComments.badgeChannels') }}
                </span>
                <span :class="['badge', { ok: selectedTemplates.length > 0 }]">
                  <i :class="selectedTemplates.length > 0 ? 'pi pi-check' : 'pi pi-minus'"></i>
                  {{ t('autoComments.badgeTemplates') }}
                </span>
                <span :class="['badge', { ok: selectedAccountIds.length > 0 }]">
                  <i :class="selectedAccountIds.length > 0 ? 'pi pi-check' : 'pi pi-minus'"></i>
                  {{ t('autoComments.badgeAccounts', { count: selectedAccountIds.length }) }}
                </span>
              </span>
            </button>
          </div>
        </div>

        <!-- Tasks List Card -->
        <div class="tasks-card">
          <div class="card-header">
            <div class="card-header-icon tasks-icon">
              <i class="pi pi-list"></i>
            </div>
            <div class="card-header-text">
              <h2>{{ t('autoComments.tasks') }}</h2>
              <span class="card-header-hint">{{ t('autoComments.tasksCount', { count: taskStore.tasks.length }) }}</span>
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
                    :value="t(`autoComments.status.${task.status}`)"
                    :severity="getStatusSeverity(task.status)"
                    class="status-tag"
                  />
                </div>
                <div class="task-channels">
                  <i class="pi pi-hashtag"></i>
                  <span v-for="(channel, idx) in (task.config?.channels || []).slice(0, 2)" :key="idx" class="channel-name">
                    {{ channel }}
                  </span>
                  <span v-if="(task.config?.channels || []).length > 2" class="more">
                    +{{ (task.config?.channels || []).length - 2 }}
                  </span>
                </div>
              </div>

              <div class="task-meta">
                <span class="task-accounts-count">
                  <i class="pi pi-users"></i> {{ task.accounts_count }}
                </span>
                <span class="task-time">{{ timeAgo(task.created_at) }}</span>
              </div>

              <div class="task-progress-section">
                <div class="progress-info">
                  <span class="progress-label">{{ t('autoComments.progress') }}</span>
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
                  v-tooltip.top="t('autoComments.tooltipStart')"
                  @click="startTask(task)"
                />
                <Button
                  v-if="task.status === 'running'"
                  icon="pi pi-pause"
                  rounded
                  class="action-btn pause"
                  v-tooltip.top="t('autoComments.tooltipPause')"
                  @click="pauseTask(task)"
                />
                <Button
                  v-if="task.status === 'running' || task.status === 'paused'"
                  icon="pi pi-stop"
                  rounded
                  class="action-btn stop"
                  v-tooltip.top="t('autoComments.tooltipStop')"
                  @click="cancelTask(task)"
                />
                <Button
                  v-if="task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled'"
                  icon="pi pi-refresh"
                  rounded
                  class="action-btn restart"
                  v-tooltip.top="t('autoComments.tooltipRestart')"
                  @click="restartTask(task)"
                />
                <Button
                  icon="pi pi-eye"
                  rounded
                  class="action-btn view"
                  v-tooltip.top="t('autoComments.tooltipDetails')"
                  @click="viewTaskDetails(task)"
                />
                <Button
                  v-if="task.status !== 'running' && task.status !== 'paused'"
                  icon="pi pi-trash"
                  rounded
                  class="action-btn delete"
                  v-tooltip.top="t('autoComments.tooltipDelete')"
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
              <i class="pi pi-comments"></i>
            </div>
            <h3>{{ t('autoComments.noTasks') }}</h3>
            <p>{{ t('autoComments.noTasksHint') }}</p>
          </div>
        </div>
      </div>

      <!-- Create Template Dialog -->
      <Dialog
        v-model:visible="showTemplateDialog"
        :header="t('autoComments.createTemplate')"
        :style="{ width: '550px' }"
        modal
        class="template-dialog"
      >
        <div class="template-form">
          <div class="form-group">
            <label class="form-label">
              <i class="pi pi-tag"></i>
              {{ t('autoComments.templateName') }}
            </label>
            <InputText
              v-model="newTemplateName"
              :placeholder="t('autoComments.templateNamePlaceholder')"
              class="w-full"
            />
          </div>

          <div class="form-group">
            <label class="form-label">
              <i class="pi pi-align-left"></i>
              {{ t('autoComments.templateContent') }}
            </label>
            <Textarea
              v-model="newTemplateContent"
              :placeholder="t('autoComments.templateContentPlaceholder')"
              class="w-full"
              rows="5"
              autoResize
            />
            <div class="spintax-hint">
              <i class="pi pi-lightbulb"></i>
              <span>{{ t('autoComments.spintaxHint') }}</span>
            </div>
          </div>

          <div v-if="templatePreview.length > 0" class="preview-section">
            <div class="preview-header">
              <i class="pi pi-eye"></i>
              <span>{{ t('autoComments.preview') }}</span>
              <Button
                icon="pi pi-refresh"
                text
                rounded
                size="small"
                @click="generatePreview"
              />
            </div>
            <div class="preview-list">
              <div v-for="(preview, idx) in templatePreview" :key="idx" class="preview-item">
                <span class="preview-number">{{ idx + 1 }}</span>
                <span class="preview-text">{{ preview }}</span>
              </div>
            </div>
          </div>
        </div>

        <template #footer>
          <div class="dialog-footer">
            <Button
              :label="t('common.cancel')"
              severity="secondary"
              outlined
              @click="showTemplateDialog = false"
            />
            <Button
              :label="t('common.save')"
              icon="pi pi-check"
              @click="createTemplate"
            />
          </div>
        </template>
      </Dialog>
    </div>
  </MainLayout>
</template>

<style scoped>
/* Page Layout — viewport-constrained, no page scroll */
.autocomments-page {
  width: 100%;
  height: calc(100vh - 40px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Page Header — always visible */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
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
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.2) 0%, rgba(168, 85, 247, 0.05) 100%);
  border: 1px solid rgba(168, 85, 247, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-icon i {
  font-size: 24px;
  color: #a855f7;
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
  color: #8b8b95;
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* Control Panel */
.control-panel {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 14px;
  padding: 8px 12px 8px 16px;
}

.control-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6e6e78;
  flex-shrink: 0;
}

.control-status.active .status-dot {
  background: #22c55e;
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.5);
  animation: dot-pulse 1.5s ease-in-out infinite;
}

@keyframes dot-pulse {
  0%, 100% { box-shadow: 0 0 8px rgba(34, 197, 94, 0.5); }
  50% { box-shadow: 0 0 14px rgba(34, 197, 94, 0.8); }
}

.status-text {
  font-size: 12px;
  font-weight: 500;
  color: #ababb5;
  white-space: nowrap;
}

.control-buttons {
  display: flex;
  gap: 6px;
}

.ctrl-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: none;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ctrl-btn i {
  font-size: 13px;
}

.ctrl-start {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(34, 197, 94, 0.1));
  color: #4ade80;
}

.ctrl-start:hover {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.35), rgba(34, 197, 94, 0.2));
  transform: translateY(-1px);
}

.ctrl-stop {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.1));
  color: #f87171;
}

.ctrl-stop:hover {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.35), rgba(239, 68, 68, 0.2));
  transform: translateY(-1px);
}

.header-stats {
  display: flex;
  gap: 12px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 12px;
  padding: 12px 20px;
  text-align: center;
  min-width: 90px;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: #a855f7;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #8b8b95;
}

/* Page Grid — fills remaining height */
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

/* Cards Common Styles */
.create-card,
.tasks-card {
  background: linear-gradient(180deg, #161619 0%, #111114 100%);
  border: 1px solid rgba(255, 255, 255, 0.10);
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
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
  flex-shrink: 0;
}

.card-header-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(168, 85, 247, 0.05) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-header-icon i {
  font-size: 15px;
  color: #a855f7;
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
  color: #8b8b95;
}

/* Custom Tabs */
.custom-tabs {
  display: flex;
  gap: 4px;
  padding: 10px 20px;
  background: rgba(0, 0, 0, 0.15);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  flex-shrink: 0;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: #8b8b95;
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
  color: #ababb5;
  background: rgba(255, 255, 255, 0.07);
}

.tab-btn.active {
  color: #a855f7;
  background: rgba(168, 85, 247, 0.12);
}

/* Tab Content — scrollable */
.tab-content {
  padding: 16px 20px;
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.tab-content::-webkit-scrollbar {
  width: 4px;
}

.tab-content::-webkit-scrollbar-track {
  background: transparent;
}

.tab-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.13);
  border-radius: 4px;
}

.tab-content::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.22);
}

.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Form Sections */
.form-section {
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 12px;
  padding: 14px 16px;
}

.form-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.form-section-header i {
  font-size: 14px;
  color: #a855f7;
}

.form-section-header span {
  font-size: 13px;
  font-weight: 600;
  color: #e4e4e7;
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
  color: #ababb5;
}

.form-label i {
  font-size: 12px;
  color: #8b8b95;
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
  color: #6e6e78;
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
  color: #8b8b95;
  pointer-events: none;
}

.input-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #6e6e78;
  margin-top: 4px;
}

.input-hint i {
  font-size: 11px;
}

/* Templates */
.template-actions-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
}

.create-template-btn {
  flex: 1;
}

.templates-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 12px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.template-card:hover {
  border-color: rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.07);
}

.template-card.selected {
  border-color: rgba(168, 85, 247, 0.5);
  background: rgba(168, 85, 247, 0.08);
}

.template-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.template-checkbox {
  color: #6e6e78;
  font-size: 16px;
}

.template-card.selected .template-checkbox {
  color: #a855f7;
}

.template-name {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: #e4e4e7;
}

.template-delete-btn {
  opacity: 0;
  transition: opacity 0.15s ease;
}

.template-card:hover .template-delete-btn {
  opacity: 1;
}

.template-content {
  font-size: 12px;
  color: #8b8b95;
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.empty-templates {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 20px;
  text-align: center;
}

.empty-templates i {
  font-size: 36px;
  color: #55555e;
  margin-bottom: 10px;
}

.empty-templates p {
  font-size: 13px;
  font-weight: 500;
  color: #8b8b95;
  margin: 0 0 4px 0;
}

.empty-templates span {
  font-size: 12px;
  color: #6e6e78;
}

/* Create Action — sticky at bottom */
.create-action {
  padding: 16px 20px;
  flex-shrink: 0;
}

/* Launch Button */
.launch-btn {
  width: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 16px 24px 14px;
  border: 1px solid rgba(168, 85, 247, 0.25);
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(168, 85, 247, 0.08) 0%, rgba(59, 130, 246, 0.06) 100%);
  cursor: not-allowed;
  opacity: 0.5;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.launch-btn.ready {
  cursor: pointer;
  opacity: 1;
  border-color: rgba(168, 85, 247, 0.4);
  background: linear-gradient(145deg, rgba(168, 85, 247, 0.12) 0%, rgba(59, 130, 246, 0.08) 100%);
}

.launch-btn.ready:hover {
  border-color: rgba(168, 85, 247, 0.6);
  background: linear-gradient(145deg, rgba(168, 85, 247, 0.18) 0%, rgba(59, 130, 246, 0.12) 100%);
  transform: translateY(-1px);
  box-shadow: 0 8px 32px rgba(168, 85, 247, 0.2), 0 0 0 1px rgba(168, 85, 247, 0.1);
}

.launch-btn.ready:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(168, 85, 247, 0.15);
}

.launch-btn-glow {
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle at center, rgba(168, 85, 247, 0.06) 0%, transparent 70%);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s;
}

.launch-btn.ready:hover .launch-btn-glow {
  opacity: 1;
}

.launch-btn-content {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 700;
  color: #a855f7;
  letter-spacing: 0.02em;
  position: relative;
  z-index: 1;
}

.launch-btn-content i {
  font-size: 16px;
}

.launch-btn.ready .launch-btn-content {
  color: #c084fc;
}

.launch-btn-badges {
  display: flex;
  gap: 8px;
  position: relative;
  z-index: 1;
}

.badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  color: #6e6e78;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.07);
  transition: all 0.2s;
}

.badge i {
  font-size: 9px;
}

.badge.ok {
  color: #4ade80;
  background: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.15);
}

/* Tasks Card */
.tasks-card {
  min-height: 0;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 24px;
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.tasks-list::-webkit-scrollbar {
  width: 4px;
}

.tasks-list::-webkit-scrollbar-track {
  background: transparent;
}

.tasks-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.13);
  border-radius: 4px;
}

.task-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 14px;
  padding: 14px 16px;
  transition: all 0.2s ease;
  overflow: hidden;
}

.task-item:hover {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.06);
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

.task-channels {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #8b8b95;
}

.task-channels i {
  font-size: 11px;
}

.channel-name {
  color: #ababb5;
}

.task-channels .more {
  color: #6e6e78;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  color: #6e6e78;
}

.task-accounts-count {
  display: flex;
  align-items: center;
  gap: 4px;
}

.task-time {
  color: #5a5a64;
}

/* Task Progress */
.task-progress-section {
  width: 100%;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.progress-label {
  font-size: 11px;
  color: #6e6e78;
}

.progress-value {
  font-size: 11px;
  font-weight: 600;
  color: #ababb5;
}

.progress-bar-container {
  height: 6px;
  background: rgba(255, 255, 255, 0.13);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #a855f7 0%, #7c3aed 100%);
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
  flex-wrap: wrap;
}

.action-btn {
  width: 34px;
  height: 34px;
  border: 1px solid rgba(255, 255, 255, 0.13);
  background: rgba(255, 255, 255, 0.04);
  color: #8b8b95;
  transition: all 0.15s ease;
}

.action-btn:hover {
  border-color: rgba(255, 255, 255, 0.22);
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

.action-btn.restart:hover {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.5);
  color: #3b82f6;
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
  flex: 1;
  padding: 40px;
  text-align: center;
}

.empty-visual {
  position: relative;
  width: 96px;
  height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.empty-visual > i {
  font-size: 28px;
  color: rgba(168, 85, 247, 0.25);
  position: relative;
  z-index: 1;
}

.empty-rings {
  position: absolute;
  inset: 0;
}

.ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(168, 85, 247, 0.08);
}

.ring-1 {
  inset: 0;
  animation: ring-breathe 4s ease-in-out infinite;
}

.ring-2 {
  inset: 12px;
  border-color: rgba(168, 85, 247, 0.12);
  animation: ring-breathe 4s ease-in-out infinite 0.5s;
}

.ring-3 {
  inset: 24px;
  border-color: rgba(168, 85, 247, 0.06);
  animation: ring-breathe 4s ease-in-out infinite 1s;
}

@keyframes ring-breathe {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.08); opacity: 1; }
}

.empty-tasks h3 {
  font-size: 15px;
  font-weight: 600;
  color: #8b8b95;
  margin: 0 0 6px 0;
}

.empty-tasks p {
  font-size: 12px;
  color: #6e6e78;
  margin: 0;
}

/* Template Dialog */
.template-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.spintax-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 8px;
  padding: 10px 12px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: 8px;
  font-size: 11px;
  color: #fbbf24;
}

.spintax-hint i {
  font-size: 14px;
  margin-top: 1px;
}

.preview-section {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 12px;
  padding: 16px;
}

.preview-section .preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.preview-section .preview-header i {
  color: #a855f7;
  font-size: 14px;
}

.preview-section .preview-header span {
  font-size: 13px;
  font-weight: 500;
  color: #e4e4e7;
  flex: 1;
}

.preview-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(168, 85, 247, 0.08);
  border-radius: 8px;
}

.preview-number {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  background: rgba(168, 85, 247, 0.2);
  color: #a855f7;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.preview-text {
  font-size: 12px;
  color: #d4d4d8;
  line-height: 1.5;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* Override PrimeVue styles */
:deep(.p-dialog) {
  background: #161619;
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 20px;
}

:deep(.p-dialog .p-dialog-header) {
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
  padding: 20px 24px;
}

:deep(.p-dialog .p-dialog-content) {
  background: transparent;
  padding: 24px;
}

:deep(.p-dialog .p-dialog-footer) {
  background: transparent;
  border-top: 1px solid rgba(255, 255, 255, 0.10);
  padding: 16px 24px;
}

:deep(.p-inputnumber-buttons-horizontal .p-button) {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.13);
  color: #8b8b95;
}

:deep(.p-inputnumber-buttons-horizontal .p-button:hover) {
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
}

:deep(.custom-chips .p-chips-token) {
  background: rgba(168, 85, 247, 0.15);
  color: #c4b5fd;
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
