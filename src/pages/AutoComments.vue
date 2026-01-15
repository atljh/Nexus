<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import Panel from 'primevue/panel'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import Chips from 'primevue/chips'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ProgressBar from 'primevue/progressbar'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import { useToast } from 'primevue/usetoast'

import { useTaskStore } from '@/stores/useTaskStore'
import { useAccountStore } from '@/stores/useAccountStore'
import { useGroupStore } from '@/stores/useGroupStore'
import type { Task, CommentTemplate } from '@/types'
import { DEFAULT_COMMENT_TEMPLATES } from '@/types'

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
const mode = ref<'single' | 'monitoring'>('single')
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

// Mode options
const modeOptions = computed(() => [
  { value: 'single', label: t('autoComments.modes.single') },
  { value: 'monitoring', label: t('autoComments.modes.monitoring') }
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
        mode: mode.value
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

async function viewTaskDetails(task: Task) {
  selectedTask.value = task
  taskStore.setCurrentTask(task)
  await taskStore.fetchTargetChannels(task.id)
  showTaskDetails.value = true
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
      <h1 class="page-title">{{ t('nav.autoComments') }}</h1>

      <div class="page-grid">
        <!-- Create Task Panel -->
        <Panel class="create-panel">
          <template #header>
            <div class="panel-header">
              <i class="pi pi-comments"></i>
              <span>{{ t('autoComments.createTask') }}</span>
            </div>
          </template>

          <TabView v-model:activeIndex="activeTab">
            <!-- Task Settings Tab -->
            <TabPanel :header="t('autoComments.settings')" value="0">
              <div class="form-grid">
                <!-- Channels input -->
                <div class="form-group">
                  <label>{{ t('autoComments.channels') }}</label>
                  <Chips
                    v-model="channels"
                    :placeholder="t('autoComments.channelsPlaceholder')"
                    class="w-full"
                    separator=","
                  />
                  <small class="hint">{{ t('autoComments.channelsHint') }}</small>
                </div>

                <!-- Mode selection -->
                <div class="form-group">
                  <label>{{ t('autoComments.mode') }}</label>
                  <Dropdown
                    v-model="mode"
                    :options="modeOptions"
                    option-label="label"
                    option-value="value"
                    class="w-full"
                  />
                </div>

                <!-- Rotation mode -->
                <div class="form-group">
                  <label>{{ t('autoComments.rotationMode') }}</label>
                  <Dropdown
                    v-model="rotationMode"
                    :options="rotationOptions"
                    option-label="label"
                    option-value="value"
                    class="w-full"
                  />
                </div>

                <!-- Comments per account -->
                <div class="form-group">
                  <label>{{ t('autoComments.commentsPerAccount') }}</label>
                  <InputNumber
                    v-model="commentsPerAccount"
                    :min="1"
                    :max="100"
                    class="w-full"
                  />
                </div>

                <!-- Total actions -->
                <div class="form-group">
                  <label>{{ t('autoComments.totalComments') }}</label>
                  <InputNumber
                    v-model="totalActions"
                    :min="1"
                    :max="10000"
                    class="w-full"
                  />
                </div>

                <!-- Delay settings -->
                <div class="form-row">
                  <div class="form-group">
                    <label>{{ t('autoComments.minDelay') }}</label>
                    <InputNumber
                      v-model="minDelay"
                      :min="1"
                      :max="3600"
                      suffix=" sec"
                      class="w-full"
                    />
                  </div>
                  <div class="form-group">
                    <label>{{ t('autoComments.maxDelay') }}</label>
                    <InputNumber
                      v-model="maxDelay"
                      :min="1"
                      :max="3600"
                      suffix=" sec"
                      class="w-full"
                    />
                  </div>
                </div>
              </div>
            </TabPanel>

            <!-- Templates Tab -->
            <TabPanel :header="t('autoComments.templates')" value="1">
              <div class="form-grid">
                <!-- Template selection -->
                <div class="form-group">
                  <label>{{ t('autoComments.selectTemplates') }}</label>
                  <MultiSelect
                    v-model="selectedTemplateIds"
                    :options="templateOptions"
                    option-label="label"
                    option-value="value"
                    :placeholder="t('autoComments.selectTemplatesPlaceholder')"
                    class="w-full"
                  />
                </div>

                <!-- Custom templates -->
                <div class="form-group">
                  <label>{{ t('autoComments.customTemplates') }}</label>
                  <Chips
                    v-model="customTemplates"
                    :placeholder="t('autoComments.customTemplatesPlaceholder')"
                    class="w-full"
                  />
                </div>

                <div class="template-actions">
                  <Button
                    :label="t('autoComments.createTemplate')"
                    icon="pi pi-plus"
                    size="small"
                    @click="showTemplateDialog = true"
                  />
                  <Button
                    v-if="taskStore.templates.length === 0"
                    :label="t('autoComments.loadDefaults')"
                    icon="pi pi-download"
                    size="small"
                    severity="secondary"
                    @click="loadDefaultTemplates"
                  />
                </div>

                <!-- Template list -->
                <div v-if="taskStore.templates.length > 0" class="templates-list">
                  <div
                    v-for="tmpl in taskStore.templates"
                    :key="tmpl.id"
                    class="template-item"
                  >
                    <div class="template-info">
                      <span class="template-name">{{ tmpl.name }}</span>
                      <span class="template-preview">{{ tmpl.content.slice(0, 50) }}...</span>
                    </div>
                    <Button
                      icon="pi pi-trash"
                      text
                      rounded
                      severity="danger"
                      size="small"
                      @click="deleteTemplate(tmpl)"
                    />
                  </div>
                </div>
              </div>
            </TabPanel>

            <!-- Accounts Tab -->
            <TabPanel :header="t('autoComments.accounts')" value="2">
              <div class="form-grid">
                <!-- Account selection -->
                <div class="form-group">
                  <label>{{ t('autoComments.filterByGroup') }}</label>
                  <Dropdown
                    v-model="selectedGroupId"
                    :options="[{ id: null, name: t('groups.allAccounts') }, ...groupStore.groups]"
                    option-label="name"
                    option-value="id"
                    class="w-full"
                  />
                </div>

                <div class="form-group">
                  <label>{{ t('autoComments.selectAccounts') }} ({{ availableAccounts.length }} {{ t('autoComments.available') }})</label>
                  <MultiSelect
                    v-model="selectedAccountIds"
                    :options="accountOptions"
                    option-label="label"
                    option-value="value"
                    :placeholder="t('autoComments.selectAccountsPlaceholder')"
                    :max-selected-labels="3"
                    class="w-full"
                  />
                </div>
              </div>
            </TabPanel>
          </TabView>

          <div class="form-footer">
            <Button
              :label="t('autoComments.startTask')"
              icon="pi pi-play"
              :loading="isCreating"
              :disabled="channels.length === 0 || selectedTemplates.length === 0 || selectedAccountIds.length === 0"
              class="w-full create-btn"
              @click="createTask"
            />
          </div>
        </Panel>

        <!-- Tasks List Panel -->
        <Panel class="tasks-panel">
          <template #header>
            <div class="panel-header">
              <i class="pi pi-list"></i>
              <span>{{ t('autoComments.tasks') }}</span>
            </div>
          </template>

          <DataTable
            :value="taskStore.tasks"
            :loading="taskStore.loading"
            :rows="10"
            :paginator="taskStore.tasks.length > 10"
            :rowsPerPageOptions="[10, 25, 50]"
            class="tasks-table"
            :empty-message="t('autoComments.noTasks')"
          >
            <Column field="id" header="ID" :sortable="true" style="width: 60px" />

            <Column :header="t('autoComments.channels')" :sortable="true">
              <template #body="{ data }">
                <div class="channels-list">
                  <Tag
                    v-for="(channel, idx) in (data.config?.channels || []).slice(0, 2)"
                    :key="idx"
                    :value="channel"
                    severity="info"
                    class="channel-tag"
                  />
                  <span v-if="(data.config?.channels || []).length > 2" class="more-channels">
                    +{{ data.config.channels.length - 2 }}
                  </span>
                </div>
              </template>
            </Column>

            <Column :header="t('autoComments.progress')" style="width: 180px">
              <template #body="{ data }">
                <div class="progress-cell">
                  <ProgressBar
                    :value="data.progress"
                    :showValue="false"
                    style="height: 8px"
                  />
                  <span class="progress-text">
                    {{ data.completed_actions }}/{{ data.total_actions }}
                  </span>
                </div>
              </template>
            </Column>

            <Column field="status" :header="t('common.status')" style="width: 120px">
              <template #body="{ data }">
                <Tag
                  :value="t(`autoComments.status.${data.status}`)"
                  :severity="getStatusSeverity(data.status)"
                />
              </template>
            </Column>

            <Column :header="t('common.actions')" style="width: 140px">
              <template #body="{ data }">
                <div class="action-buttons">
                  <Button
                    v-if="data.status === 'pending' || data.status === 'paused'"
                    icon="pi pi-play"
                    text
                    rounded
                    severity="success"
                    size="small"
                    @click="startTask(data)"
                  />
                  <Button
                    v-if="data.status === 'running'"
                    icon="pi pi-pause"
                    text
                    rounded
                    severity="warn"
                    size="small"
                    @click="pauseTask(data)"
                  />
                  <Button
                    v-if="data.status === 'running' || data.status === 'paused'"
                    icon="pi pi-times"
                    text
                    rounded
                    severity="danger"
                    size="small"
                    @click="cancelTask(data)"
                  />
                  <Button
                    icon="pi pi-eye"
                    text
                    rounded
                    severity="info"
                    size="small"
                    @click="viewTaskDetails(data)"
                  />
                  <Button
                    v-if="data.status !== 'running'"
                    icon="pi pi-trash"
                    text
                    rounded
                    severity="danger"
                    size="small"
                    @click="deleteTask(data)"
                  />
                </div>
              </template>
            </Column>
          </DataTable>
        </Panel>
      </div>

      <!-- Create Template Dialog -->
      <Dialog
        v-model:visible="showTemplateDialog"
        :header="t('autoComments.createTemplate')"
        :style="{ width: '500px' }"
        modal
      >
        <div class="template-form">
          <div class="form-group">
            <label>{{ t('autoComments.templateName') }}</label>
            <InputText
              v-model="newTemplateName"
              :placeholder="t('autoComments.templateNamePlaceholder')"
              class="w-full"
            />
          </div>

          <div class="form-group">
            <label>{{ t('autoComments.templateContent') }}</label>
            <Textarea
              v-model="newTemplateContent"
              :placeholder="t('autoComments.templateContentPlaceholder')"
              class="w-full"
              rows="4"
            />
            <small class="hint">{{ t('autoComments.spintaxHint') }}</small>
          </div>

          <div v-if="templatePreview.length > 0" class="preview-section">
            <label>{{ t('autoComments.preview') }}</label>
            <div class="preview-list">
              <div v-for="(preview, idx) in templatePreview" :key="idx" class="preview-item">
                {{ preview }}
              </div>
            </div>
          </div>
        </div>

        <template #footer>
          <Button
            :label="t('common.cancel')"
            severity="secondary"
            @click="showTemplateDialog = false"
          />
          <Button
            :label="t('common.save')"
            icon="pi pi-check"
            @click="createTemplate"
          />
        </template>
      </Dialog>

      <!-- Task Details Dialog -->
      <Dialog
        v-model:visible="showTaskDetails"
        :header="t('autoComments.taskDetails')"
        :style="{ width: '800px' }"
        modal
      >
        <div v-if="selectedTask" class="task-details">
          <div class="detail-row">
            <span class="label">{{ t('autoComments.channels') }}:</span>
            <div class="channels-list">
              <Tag
                v-for="(channel, idx) in selectedTask.config?.channels || []"
                :key="idx"
                :value="channel"
                severity="info"
              />
            </div>
          </div>
          <div class="detail-row">
            <span class="label">{{ t('autoComments.rotationMode') }}:</span>
            <span class="value">{{ t(`autoComments.rotation.${selectedTask.config?.rotation_mode}`) }}</span>
          </div>
          <div class="detail-row">
            <span class="label">{{ t('common.status') }}:</span>
            <Tag
              :value="t(`autoComments.status.${selectedTask.status}`)"
              :severity="getStatusSeverity(selectedTask.status)"
            />
          </div>
          <div class="detail-row">
            <span class="label">{{ t('autoComments.progress') }}:</span>
            <div class="progress-detail">
              <ProgressBar :value="selectedTask.progress" style="height: 10px; flex: 1" />
              <span>{{ selectedTask.completed_actions }}/{{ selectedTask.total_actions }}</span>
            </div>
          </div>
          <div v-if="selectedTask.failed_actions > 0" class="detail-row">
            <span class="label">{{ t('autoComments.failed') }}:</span>
            <span class="value error-text">{{ selectedTask.failed_actions }}</span>
          </div>
          <div v-if="selectedTask.last_error" class="detail-row">
            <span class="label">{{ t('autoComments.lastError') }}:</span>
            <span class="value error-text">{{ selectedTask.last_error }}</span>
          </div>

          <!-- Target Channels -->
          <div class="channels-section">
            <h4>{{ t('autoComments.targetChannels') }}</h4>
            <DataTable
              :value="taskStore.targetChannels"
              class="channels-table"
              :empty-message="t('autoComments.noChannels')"
            >
              <Column field="channel_username" :header="t('autoComments.channel')" />
              <Column field="channel_title" :header="t('autoComments.title')" />
              <Column field="status" :header="t('common.status')">
                <template #body="{ data }">
                  <Tag
                    :value="data.status"
                    :severity="getChannelStatusSeverity(data.status)"
                  />
                </template>
              </Column>
              <Column field="comments_sent" :header="t('autoComments.sent')" />
              <Column field="error_message" :header="t('autoComments.error')">
                <template #body="{ data }">
                  <span v-if="data.error_message" class="error-text">
                    {{ data.error_message }}
                  </span>
                  <span v-else>-</span>
                </template>
              </Column>
            </DataTable>
          </div>

          <!-- Task Logs -->
          <div class="logs-section">
            <h4>{{ t('autoComments.logs') }}</h4>
            <DataTable
              :value="taskStore.taskLogs"
              :rows="5"
              :paginator="taskStore.taskLogs.length > 5"
              class="logs-table"
              :empty-message="t('autoComments.noLogs')"
            >
              <Column :header="t('autoComments.time')" style="width: 150px">
                <template #body="{ data }">
                  {{ formatDate(data.created_at) }}
                </template>
              </Column>
              <Column field="target" :header="t('autoComments.target')" />
              <Column :header="t('autoComments.result')" style="width: 80px">
                <template #body="{ data }">
                  <i
                    :class="data.success ? 'pi pi-check-circle success-icon' : 'pi pi-times-circle error-icon'"
                  />
                </template>
              </Column>
              <Column :header="t('autoComments.comment')" style="width: 200px">
                <template #body="{ data }">
                  <span class="comment-preview">
                    {{ data.extra_data?.comment || '-' }}
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
.autocomments-page {
  width: 100%;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #f3f4f6;
  margin-bottom: 24px;
  letter-spacing: -0.5px;
}

.page-grid {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 24px;
}

@media (max-width: 1200px) {
  .page-grid {
    grid-template-columns: 1fr;
  }
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}

.panel-header i {
  font-size: 18px;
  color: #f59e0b;
}

.form-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: #9ca3af;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.hint {
  font-size: 11px;
  color: #6b7280;
}

.form-footer {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.create-btn {
  margin-top: 8px;
}

.template-actions {
  display: flex;
  gap: 8px;
}

.templates-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.template-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}

.template-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.template-name {
  font-weight: 500;
  color: #e5e7eb;
  font-size: 13px;
}

.template-preview {
  font-size: 11px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.preview-section {
  margin-top: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}

.preview-section label {
  font-size: 12px;
  font-weight: 500;
  color: #9ca3af;
  margin-bottom: 8px;
  display: block;
}

.preview-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-item {
  font-size: 12px;
  color: #d1d5db;
  padding: 6px 10px;
  background: rgba(245, 158, 11, 0.1);
  border-radius: 4px;
}

.tasks-table {
  font-size: 14px;
}

.channels-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.channel-tag {
  font-size: 11px;
}

.more-channels {
  font-size: 11px;
  color: #6b7280;
}

.progress-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.progress-text {
  font-size: 12px;
  color: #9ca3af;
}

.action-buttons {
  display: flex;
  gap: 4px;
}

.task-details {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-row .label {
  min-width: 140px;
  font-weight: 500;
  color: #9ca3af;
}

.detail-row .value {
  color: #e5e7eb;
}

.progress-detail {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.error-text {
  color: #ef4444;
}

.channels-section,
.logs-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.channels-section h4,
.logs-section h4 {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 12px;
}

.comment-preview {
  font-size: 11px;
  color: #9ca3af;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
  display: block;
}

.success-icon {
  color: #22c55e;
}

.error-icon {
  color: #ef4444;
}

:deep(.p-panel) {
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
}

:deep(.p-panel-header) {
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding: 16px 20px;
}

:deep(.p-panel-content) {
  background: transparent;
  padding: 20px;
}

:deep(.p-tabview) {
  background: transparent;
}

:deep(.p-tabview-nav) {
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.p-tabview-panels) {
  background: transparent;
  padding: 16px 0;
}

:deep(.p-datatable) {
  background: transparent;
}

:deep(.p-datatable .p-datatable-tbody > tr) {
  background: transparent;
}

:deep(.p-datatable .p-datatable-tbody > tr:hover) {
  background: rgba(255, 255, 255, 0.02);
}

:deep(.p-chips-token) {
  background: rgba(245, 158, 11, 0.2);
  color: #fcd34d;
}
</style>
