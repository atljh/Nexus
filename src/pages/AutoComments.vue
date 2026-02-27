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
import InputChips from 'primevue/inputchips'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'

import { useTaskStore } from '@/stores/useTaskStore'
import { useAccountStore } from '@/stores/useAccountStore'
import { useGroupStore } from '@/stores/useGroupStore'
import type { Task, CommentTemplate } from '@/types'
import { DEFAULT_COMMENT_TEMPLATES } from '@/types'

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const taskStore = useTaskStore()
const accountStore = useAccountStore()
const groupStore = useGroupStore()

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
const selectedGroupId = ref<number | null>(null)

// Template management
const showTemplateDialog = ref(false)
const newTemplateName = ref('')
const newTemplateContent = ref('')
const templatePreview = ref<string[]>([])

// UI state
const showTaskDetails = ref(false)
const selectedTask = ref<Task | null>(null)
const isCreating = ref(false)
const activeTab = ref(0)

// Tabs configuration
const tabs = computed(() => [
  { label: t('autoComments.settings'), icon: 'pi pi-cog' },
  { label: t('autoComments.templates'), icon: 'pi pi-file-edit' },
  { label: t('autoComments.accounts'), icon: 'pi pi-users' }
])

// Rotation mode options
const rotationOptions = computed(() => [
  { value: 'random', label: t('autoComments.rotation.random') },
  { value: 'round_robin', label: t('autoComments.rotation.roundRobin') }
])

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

// Channel status badge
function getChannelStatusSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
  switch (status) {
    case 'joined': return 'success'
    case 'pending': return 'info'
    case 'error': return 'danger'
    case 'cannot_comment': return 'warn'
    default: return 'secondary'
  }
}

// Create task
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
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('autoComments.messages.taskCreated'),
        life: 3000
      })
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

function loadDefaultTemplates() {
  for (const template of DEFAULT_COMMENT_TEMPLATES) {
    taskStore.createTemplate(template.name, template.content)
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
  await taskStore.startTask(task.id)
  toast.add({
    severity: 'info',
    summary: t('autoComments.messages.taskStarted'),
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
    summary: t('autoComments.messages.taskDeleted'),
    life: 2000
  })
}

function viewTaskDetails(task: Task) {
  router.push(`/task/${task.id}`)
}

// Format date
function formatDate(date: string | null): string {
  if (!date) return '-'
  return new Date(date).toLocaleString()
}

// Initialize
onMounted(async () => {
  await Promise.all([
    taskStore.fetchTasks('comments'),
    taskStore.fetchTemplates(),
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
        <div class="header-stats">
          <div class="stat-card">
            <span class="stat-value">{{ taskStore.tasks.filter(t => t.status === 'running').length }}</span>
            <span class="stat-label">Активні</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">{{ taskStore.tasks.filter(t => t.status === 'completed').length }}</span>
            <span class="stat-label">Завершені</span>
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
              <span class="card-header-hint">Налаштуйте параметри та запустіть завдання</span>
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
                  <span>Цільові канали</span>
                </div>
                <div class="form-group">
                  <InputChips
                    v-model="channels"
                    :placeholder="t('autoComments.channelsPlaceholder')"
                    class="w-full custom-chips"
                    separator=","
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
                  <span>Режим роботи</span>
                </div>
                <div class="form-grid-2">
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
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-chart-bar"></i>
                  <span>Ліміти</span>
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
                  <span>Затримка між діями</span>
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
                      <span class="input-suffix">сек</span>
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
                      <span class="input-suffix">сек</span>
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
                  <span>Вибір шаблонів</span>
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
                  <span>Власні коментарі</span>
                </div>
                <div class="form-group">
                  <InputChips
                    v-model="customTemplates"
                    :placeholder="t('autoComments.customTemplatesPlaceholder')"
                    class="w-full custom-chips"
                  />
                  <small class="input-hint">
                    <i class="pi pi-info-circle"></i>
                    Введіть текст коментаря і натисніть Enter
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
                <p>Шаблони не створені</p>
                <span>Створіть перший шаблон або завантажте стандартні</span>
              </div>
            </div>

            <!-- Accounts Tab -->
            <div v-if="activeTab === 2" class="tab-panel">
              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-filter"></i>
                  <span>Фільтр акаунтів</span>
                </div>
                <div class="form-group">
                  <label class="form-label">{{ t('autoComments.filterByGroup') }}</label>
                  <Select
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
                  <span>Вибір акаунтів</span>
                  <span class="accounts-count">{{ availableAccounts.length }} доступно</span>
                </div>
                <div class="form-group">
                  <MultiSelect
                    v-model="selectedAccountIds"
                    :options="accountOptions"
                    option-label="label"
                    option-value="value"
                    :placeholder="t('autoComments.selectAccountsPlaceholder')"
                    :maxSelectedLabels="5"
                    class="w-full"
                    display="chip"
                    filter
                    filterPlaceholder="Пошук акаунту..."
                  />
                </div>
              </div>

              <div v-if="selectedAccountIds.length > 0" class="selected-accounts-preview">
                <div class="preview-header">
                  <span>Вибрано акаунтів: {{ selectedAccountIds.length }}</span>
                  <Button
                    label="Скинути"
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
                    +{{ selectedAccountIds.length - 8 }} ще
                  </span>
                </div>
              </div>

              <div v-else class="no-accounts-selected">
                <i class="pi pi-user-plus"></i>
                <p>Акаунти не вибрані</p>
                <span>Виберіть хоча б один акаунт для запуску завдання</span>
              </div>
            </div>
          </div>

          <!-- Create Button -->
          <div class="create-action">
            <div class="validation-summary">
              <div :class="['validation-item', { valid: channels.length > 0 }]">
                <i :class="channels.length > 0 ? 'pi pi-check' : 'pi pi-times'"></i>
                <span>Канали</span>
              </div>
              <div :class="['validation-item', { valid: selectedTemplates.length > 0 }]">
                <i :class="selectedTemplates.length > 0 ? 'pi pi-check' : 'pi pi-times'"></i>
                <span>Шаблони</span>
              </div>
              <div :class="['validation-item', { valid: selectedAccountIds.length > 0 }]">
                <i :class="selectedAccountIds.length > 0 ? 'pi pi-check' : 'pi pi-times'"></i>
                <span>Акаунти</span>
              </div>
            </div>
            <Button
              :label="t('autoComments.startTask')"
              icon="pi pi-play"
              :loading="isCreating"
              :disabled="channels.length === 0 || selectedTemplates.length === 0 || selectedAccountIds.length === 0"
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
              <h2>{{ t('autoComments.tasks') }}</h2>
              <span class="card-header-hint">{{ taskStore.tasks.length }} завдань</span>
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

              <div class="task-progress-section">
                <div class="progress-info">
                  <span class="progress-label">Прогрес</span>
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
                  v-tooltip.top="'Запустити'"
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
                  v-tooltip.top="'Зупинити'"
                  @click="cancelTask(task)"
                />
                <Button
                  icon="pi pi-eye"
                  rounded
                  class="action-btn view"
                  v-tooltip.top="'Деталі'"
                  @click="viewTaskDetails(task)"
                />
                <Button
                  v-if="task.status !== 'running'"
                  icon="pi pi-trash"
                  rounded
                  class="action-btn delete"
                  v-tooltip.top="'Видалити'"
                  @click="deleteTask(task)"
                />
              </div>
            </div>
          </div>

          <div v-else class="empty-tasks">
            <div class="empty-icon">
              <i class="pi pi-inbox"></i>
            </div>
            <h3>Немає завдань</h3>
            <p>Створіть перше завдання, заповнивши форму зліва</p>
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

      <!-- Task Details Dialog -->
      <Dialog
        v-model:visible="showTaskDetails"
        :header="`Завдання #${selectedTask?.id}`"
        :style="{ width: '900px', maxHeight: '90vh' }"
        modal
        class="task-details-dialog"
      >
        <div v-if="selectedTask" class="task-details">
          <!-- Overview Section -->
          <div class="details-section overview">
            <div class="overview-grid">
              <div class="overview-item">
                <span class="overview-label">Статус</span>
                <Tag
                  :value="t(`autoComments.status.${selectedTask.status}`)"
                  :severity="getStatusSeverity(selectedTask.status)"
                  class="overview-tag"
                />
              </div>
              <div class="overview-item">
                <span class="overview-label">Ротація</span>
                <span class="overview-value">{{ t(`autoComments.rotation.${selectedTask.config?.rotation_mode}`) }}</span>
              </div>
              <div class="overview-item">
                <span class="overview-label">Прогрес</span>
                <span class="overview-value progress-val">{{ selectedTask.completed_actions }}/{{ selectedTask.total_actions }}</span>
              </div>
            </div>

            <div class="progress-section">
              <div class="big-progress-bar">
                <div
                  class="big-progress-fill"
                  :style="{ width: `${selectedTask.progress}%` }"
                ></div>
              </div>
              <span class="progress-percent">{{ selectedTask.progress }}%</span>
            </div>

            <div v-if="selectedTask.failed_actions > 0 || selectedTask.last_error" class="error-section">
              <div v-if="selectedTask.failed_actions > 0" class="error-stat">
                <i class="pi pi-exclamation-triangle"></i>
                <span>Помилок: {{ selectedTask.failed_actions }}</span>
              </div>
              <div v-if="selectedTask.last_error" class="error-message">
                <span class="error-label">Остання помилка:</span>
                <span class="error-text">{{ selectedTask.last_error }}</span>
              </div>
            </div>
          </div>

          <!-- Channels Section -->
          <div class="details-section">
            <div class="section-header">
              <i class="pi pi-hashtag"></i>
              <h3>{{ t('autoComments.targetChannels') }}</h3>
            </div>
            <div class="channels-grid">
              <Tag
                v-for="(channel, idx) in selectedTask.config?.channels || []"
                :key="idx"
                :value="channel"
                severity="info"
                class="channel-tag-large"
              />
            </div>
          </div>

          <!-- Target Channels Table -->
          <div class="details-section">
            <div class="section-header">
              <i class="pi pi-chart-bar"></i>
              <h3>Статистика каналів</h3>
            </div>
            <DataTable
              :value="taskStore.targetChannels"
              class="details-table"
              :rows="5"
              :paginator="taskStore.targetChannels.length > 5"
            >
              <template #empty>
                <div class="table-empty">
                  <i class="pi pi-info-circle"></i>
                  <span>{{ t('autoComments.noChannels') }}</span>
                </div>
              </template>
              <Column field="channel_username" :header="t('autoComments.channel')">
                <template #body="{ data }">
                  <span class="channel-cell">@{{ data.channel_username }}</span>
                </template>
              </Column>
              <Column field="channel_title" :header="t('autoComments.title')" />
              <Column field="status" :header="t('common.status')">
                <template #body="{ data }">
                  <Tag
                    :value="data.status"
                    :severity="getChannelStatusSeverity(data.status)"
                  />
                </template>
              </Column>
              <Column field="comments_sent" :header="t('autoComments.sent')">
                <template #body="{ data }">
                  <span class="sent-count">{{ data.comments_sent || 0 }}</span>
                </template>
              </Column>
              <Column field="error_message" :header="t('autoComments.error')">
                <template #body="{ data }">
                  <span v-if="data.error_message" class="error-cell">
                    {{ data.error_message }}
                  </span>
                  <span v-else class="no-error">—</span>
                </template>
              </Column>
            </DataTable>
          </div>

          <!-- Task Logs -->
          <div class="details-section">
            <div class="section-header">
              <i class="pi pi-history"></i>
              <h3>{{ t('autoComments.logs') }}</h3>
            </div>
            <DataTable
              :value="taskStore.taskLogs"
              :rows="5"
              :paginator="taskStore.taskLogs.length > 5"
              class="details-table logs-table"
            >
              <template #empty>
                <div class="table-empty">
                  <i class="pi pi-info-circle"></i>
                  <span>{{ t('autoComments.noLogs') }}</span>
                </div>
              </template>
              <Column :header="t('autoComments.time')" style="width: 160px">
                <template #body="{ data }">
                  <span class="time-cell">{{ formatDate(data.created_at) }}</span>
                </template>
              </Column>
              <Column field="target" :header="t('autoComments.target')">
                <template #body="{ data }">
                  <span class="target-cell">{{ data.target }}</span>
                </template>
              </Column>
              <Column :header="t('autoComments.result')" style="width: 100px">
                <template #body="{ data }">
                  <div :class="['result-badge', data.success ? 'success' : 'error']">
                    <i :class="data.success ? 'pi pi-check' : 'pi pi-times'"></i>
                    <span>{{ data.success ? 'OK' : 'Fail' }}</span>
                  </div>
                </template>
              </Column>
              <Column :header="t('autoComments.comment')">
                <template #body="{ data }">
                  <span class="comment-cell">
                    {{ data.extra_data?.comment || '—' }}
                  </span>
                </template>
              </Column>
            </DataTable>
          </div>
        </div>
      </Dialog>
    </div>
  </MainLayout>
</template>

<style scoped>
/* Page Layout */
.autocomments-page {
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
  color: #a855f7;
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
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(168, 85, 247, 0.05) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-header-icon i {
  font-size: 18px;
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
  color: #a855f7;
  background: rgba(168, 85, 247, 0.12);
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
  color: #a855f7;
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
  color: #a855f7;
  background: rgba(168, 85, 247, 0.1);
  padding: 4px 10px;
  border-radius: 20px;
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

.input-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #52525b;
  margin-top: 4px;
}

.input-hint i {
  font-size: 11px;
}

/* Templates */
.template-actions-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.create-template-btn {
  flex: 1;
}

.templates-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 280px;
  overflow-y: auto;
  padding-right: 8px;
}

.template-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.template-card:hover {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
}

.template-card.selected {
  border-color: rgba(168, 85, 247, 0.5);
  background: rgba(168, 85, 247, 0.08);
}

.template-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.template-checkbox {
  color: #52525b;
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
  color: #71717a;
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.empty-templates,
.no-accounts-selected {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.empty-templates i,
.no-accounts-selected i {
  font-size: 40px;
  color: #3f3f46;
  margin-bottom: 12px;
}

.empty-templates p,
.no-accounts-selected p {
  font-size: 14px;
  font-weight: 500;
  color: #71717a;
  margin: 0 0 4px 0;
}

.empty-templates span,
.no-accounts-selected span {
  font-size: 12px;
  color: #52525b;
}

/* Selected Accounts Preview */
.selected-accounts-preview {
  background: rgba(168, 85, 247, 0.05);
  border: 1px solid rgba(168, 85, 247, 0.2);
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
  color: #a855f7;
}

.accounts-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.account-chip {
  background: rgba(168, 85, 247, 0.15);
  color: #c4b5fd;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
}

.more-accounts {
  color: #a855f7;
  font-size: 11px;
  font-weight: 500;
  padding: 4px 8px;
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

.task-channels {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #71717a;
}

.task-channels i {
  font-size: 11px;
}

.channel-name {
  color: #a1a1aa;
}

.task-channels .more {
  color: #52525b;
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
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 16px;
}

.preview-section .preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
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

/* Task Details Dialog */
.task-details {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.details-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  padding: 20px;
}

.details-section.overview {
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.08) 0%, rgba(59, 130, 246, 0.05) 100%);
  border-color: rgba(168, 85, 247, 0.2);
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.overview-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.overview-label {
  font-size: 11px;
  font-weight: 500;
  color: #71717a;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.overview-value {
  font-size: 14px;
  font-weight: 600;
  color: #fafafa;
}

.overview-value.progress-val {
  color: #a855f7;
}

.overview-tag {
  width: fit-content;
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.big-progress-bar {
  flex: 1;
  height: 10px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 5px;
  overflow: hidden;
}

.big-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #a855f7 0%, #7c3aed 100%);
  border-radius: 5px;
  transition: width 0.3s ease;
}

.progress-percent {
  font-size: 16px;
  font-weight: 700;
  color: #a855f7;
  min-width: 50px;
  text-align: right;
}

.error-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(239, 68, 68, 0.2);
}

.error-stat {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #f87171;
  font-size: 13px;
  font-weight: 500;
}

.error-stat i {
  font-size: 14px;
}

.error-message {
  margin-top: 8px;
  padding: 10px 12px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 8px;
}

.error-label {
  font-size: 11px;
  color: #f87171;
  display: block;
  margin-bottom: 4px;
}

.error-text {
  font-size: 12px;
  color: #fca5a5;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.section-header i {
  font-size: 16px;
  color: #a855f7;
}

.section-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #fafafa;
  margin: 0;
}

.channels-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.channel-tag-large {
  padding: 6px 14px;
  font-size: 12px;
}

/* Details Tables */
.details-table {
  background: transparent;
}

.table-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 30px;
  color: #52525b;
  font-size: 13px;
}

.table-empty i {
  font-size: 16px;
}

.channel-cell {
  font-weight: 500;
  color: #a855f7;
}

.sent-count {
  font-weight: 600;
  color: #22c55e;
}

.error-cell {
  font-size: 12px;
  color: #f87171;
}

.no-error {
  color: #52525b;
}

.time-cell {
  font-size: 12px;
  color: #71717a;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.target-cell {
  font-weight: 500;
  color: #e4e4e7;
}

.result-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}

.result-badge.success {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.result-badge.error {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.comment-cell {
  font-size: 12px;
  color: #a1a1aa;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  max-width: 250px;
}

/* Override PrimeVue styles */
:deep(.p-dialog) {
  background: #141417;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
}

:deep(.p-dialog .p-dialog-header) {
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding: 20px 24px;
}

:deep(.p-dialog .p-dialog-content) {
  background: transparent;
  padding: 24px;
}

:deep(.p-dialog .p-dialog-footer) {
  background: transparent;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding: 16px 24px;
}

:deep(.p-datatable) {
  background: transparent;
}

:deep(.p-datatable .p-datatable-thead > tr > th) {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.06);
}

:deep(.p-datatable .p-datatable-tbody > tr) {
  background: transparent;
}

:deep(.p-datatable .p-datatable-tbody > tr > td) {
  border-color: rgba(255, 255, 255, 0.04);
}

:deep(.p-datatable .p-datatable-tbody > tr:hover) {
  background: rgba(255, 255, 255, 0.02);
}

:deep(.p-inputnumber-buttons-horizontal .p-button) {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
  color: #71717a;
}

:deep(.p-inputnumber-buttons-horizontal .p-button:hover) {
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
}

:deep(.custom-chips .p-chips-token) {
  background: rgba(168, 85, 247, 0.15);
  color: #c4b5fd;
}

:deep(.p-tooltip) {
  background: #1f1f23;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.p-tooltip .p-tooltip-text) {
  background: transparent;
  color: #e4e4e7;
  font-size: 11px;
  padding: 6px 10px;
}
</style>
