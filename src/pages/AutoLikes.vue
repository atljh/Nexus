<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import Panel from 'primevue/panel'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ProgressBar from 'primevue/progressbar'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
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
const reaction = ref('👍')
const mode = ref<'single' | 'monitoring'>('single')
const totalActions = ref(10)
const minDelay = ref(30)
const maxDelay = ref(120)
const maxConcurrent = ref(1)
const selectedAccountIds = ref<number[]>([])
const selectedGroupId = ref<number | null>(null)

// UI state
const showTaskDetails = ref(false)
const selectedTask = ref<Task | null>(null)
const isCreating = ref(false)

// Mode options
const modeOptions = [
  { value: 'single', label: t('autoLikes.modes.single') },
  { value: 'monitoring', label: t('autoLikes.modes.monitoring') }
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
        post_id: mode.value === 'single' ? postId.value : null,
        reaction: reaction.value,
        mode: mode.value
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
      // Auto-start if you want
      // await taskStore.startTask(task.id)
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

// Format date
function formatDate(date: string | null): string {
  if (!date) return '-'
  return new Date(date).toLocaleString()
}

// Load test data for demo
function loadTestData() {
  const testTasks = [
    {
      id: 1,
      task_type: 'likes',
      status: 'completed',
      config: { channel: '@durov', reaction: '👍', mode: 'single' },
      total_actions: 100,
      completed_actions: 100,
      failed_actions: 2,
      progress: 100,
      created_at: new Date(Date.now() - 86400000).toISOString(),
      started_at: new Date(Date.now() - 86400000).toISOString(),
      completed_at: new Date(Date.now() - 82800000).toISOString(),
      last_error: null
    },
    {
      id: 2,
      task_type: 'likes',
      status: 'running',
      config: { channel: '@telegram', reaction: '❤️', mode: 'monitoring' },
      total_actions: 50,
      completed_actions: 23,
      failed_actions: 1,
      progress: 46,
      created_at: new Date(Date.now() - 3600000).toISOString(),
      started_at: new Date(Date.now() - 3600000).toISOString(),
      completed_at: null,
      last_error: null
    },
    {
      id: 3,
      task_type: 'likes',
      status: 'pending',
      config: { channel: '@tech_news', reaction: '🔥', mode: 'single', post_id: 1234 },
      total_actions: 25,
      completed_actions: 0,
      failed_actions: 0,
      progress: 0,
      created_at: new Date().toISOString(),
      started_at: null,
      completed_at: null,
      last_error: null
    },
    {
      id: 4,
      task_type: 'likes',
      status: 'failed',
      config: { channel: '@private_channel', reaction: '👎', mode: 'single' },
      total_actions: 30,
      completed_actions: 5,
      failed_actions: 10,
      progress: 17,
      created_at: new Date(Date.now() - 172800000).toISOString(),
      started_at: new Date(Date.now() - 172800000).toISOString(),
      completed_at: new Date(Date.now() - 172000000).toISOString(),
      last_error: 'Channel not accessible'
    }
  ]

  const testAccounts = [
    { id: 1, phone: '+380991234567', username: 'test_user1', status: 'valid', group_id: null },
    { id: 2, phone: '+380997654321', username: 'test_user2', status: 'valid', group_id: null },
    { id: 3, phone: '+380501112233', username: 'test_user3', status: 'valid', group_id: null },
    { id: 4, phone: '+380672223344', username: null, status: 'valid', group_id: null }
  ]

  // @ts-ignore - Setting test data directly
  taskStore.tasks = testTasks
  // @ts-ignore - Setting test data directly
  accountStore.accounts = testAccounts
}

// Initialize
onMounted(async () => {
  await Promise.all([
    taskStore.fetchTasks('likes'),
    accountStore.fetchAccounts(),
    groupStore.fetchGroups()
  ])

  // Load test data if no tasks exist
  if (taskStore.tasks.length === 0) {
    loadTestData()
  }

  // Start polling if there are running tasks
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
      <h1 class="page-title">{{ t('nav.autoLikes') }}</h1>

      <div class="page-grid">
        <!-- Create Task Panel -->
        <Panel class="create-panel">
          <template #header>
            <div class="panel-header">
              <i class="pi pi-plus-circle"></i>
              <span>{{ t('autoLikes.createTask') }}</span>
            </div>
          </template>

          <div class="form-grid">
            <!-- Channel input -->
            <div class="form-group">
              <label>{{ t('autoLikes.channel') }}</label>
              <InputText
                v-model="channel"
                :placeholder="t('autoLikes.channelPlaceholder')"
                class="w-full"
              />
            </div>

            <!-- Mode selection -->
            <div class="form-group">
              <label>{{ t('autoLikes.mode') }}</label>
              <Dropdown
                v-model="mode"
                :options="modeOptions"
                option-label="label"
                option-value="value"
                class="w-full"
              />
            </div>

            <!-- Post ID (for single mode) -->
            <div v-if="mode === 'single'" class="form-group">
              <label>{{ t('autoLikes.postId') }} ({{ t('common.optional') }})</label>
              <InputNumber
                v-model="postId"
                :placeholder="t('autoLikes.postIdPlaceholder')"
                class="w-full"
                :use-grouping="false"
              />
            </div>

            <!-- Reaction selection -->
            <div class="form-group">
              <label>{{ t('autoLikes.reaction') }}</label>
              <Dropdown
                v-model="reaction"
                :options="reactionOptions"
                option-label="label"
                option-value="value"
                class="w-full"
              />
            </div>

            <!-- Total actions -->
            <div class="form-group">
              <label>{{ t('autoLikes.totalReactions') }}</label>
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
                <label>{{ t('autoLikes.minDelay') }}</label>
                <InputNumber
                  v-model="minDelay"
                  :min="1"
                  :max="3600"
                  suffix=" sec"
                  class="w-full"
                />
              </div>
              <div class="form-group">
                <label>{{ t('autoLikes.maxDelay') }}</label>
                <InputNumber
                  v-model="maxDelay"
                  :min="1"
                  :max="3600"
                  suffix=" sec"
                  class="w-full"
                />
              </div>
            </div>

            <!-- Account selection -->
            <div class="form-group">
              <label>{{ t('autoLikes.filterByGroup') }}</label>
              <Dropdown
                v-model="selectedGroupId"
                :options="[{ id: null, name: t('groups.allAccounts') }, ...groupStore.groups]"
                option-label="name"
                option-value="id"
                class="w-full"
              />
            </div>

            <div class="form-group">
              <label>{{ t('autoLikes.selectAccounts') }} ({{ availableAccounts.length }} {{ t('autoLikes.available') }})</label>
              <MultiSelect
                v-model="selectedAccountIds"
                :options="accountOptions"
                option-label="label"
                option-value="value"
                :placeholder="t('autoLikes.selectAccountsPlaceholder')"
                :max-selected-labels="3"
                class="w-full"
              />
            </div>

            <Button
              :label="t('autoLikes.startTask')"
              icon="pi pi-play"
              :loading="isCreating"
              :disabled="!channel || selectedAccountIds.length === 0"
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
              <span>{{ t('autoLikes.tasks') }}</span>
            </div>
          </template>

          <DataTable
            :value="taskStore.tasks"
            :loading="taskStore.loading"
            :rows="10"
            :paginator="taskStore.tasks.length > 10"
            :rowsPerPageOptions="[10, 25, 50]"
            class="tasks-table"
            :empty-message="t('autoLikes.noTasks')"
          >
            <Column field="id" header="ID" :sortable="true" style="width: 60px" />

            <Column field="config.channel" :header="t('autoLikes.channel')" :sortable="true">
              <template #body="{ data }">
                <span class="channel-name">{{ data.config?.channel }}</span>
              </template>
            </Column>

            <Column field="config.reaction" :header="t('autoLikes.reaction')" style="width: 80px">
              <template #body="{ data }">
                <span class="reaction-emoji">{{ data.config?.reaction }}</span>
              </template>
            </Column>

            <Column :header="t('autoLikes.progress')" style="width: 180px">
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
                  :value="t(`autoLikes.status.${data.status}`)"
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

      <!-- Task Details Dialog -->
      <Dialog
        v-model:visible="showTaskDetails"
        :header="t('autoLikes.taskDetails')"
        :style="{ width: '700px' }"
        modal
      >
        <div v-if="selectedTask" class="task-details">
          <div class="detail-row">
            <span class="label">{{ t('autoLikes.channel') }}:</span>
            <span class="value">{{ selectedTask.config?.channel }}</span>
          </div>
          <div class="detail-row">
            <span class="label">{{ t('autoLikes.reaction') }}:</span>
            <span class="value reaction-emoji">{{ selectedTask.config?.reaction }}</span>
          </div>
          <div class="detail-row">
            <span class="label">{{ t('common.status') }}:</span>
            <Tag
              :value="t(`autoLikes.status.${selectedTask.status}`)"
              :severity="getStatusSeverity(selectedTask.status)"
            />
          </div>
          <div class="detail-row">
            <span class="label">{{ t('autoLikes.progress') }}:</span>
            <div class="progress-detail">
              <ProgressBar :value="selectedTask.progress" style="height: 10px; flex: 1" />
              <span>{{ selectedTask.completed_actions }}/{{ selectedTask.total_actions }}</span>
            </div>
          </div>
          <div v-if="selectedTask.failed_actions > 0" class="detail-row">
            <span class="label">{{ t('autoLikes.failed') }}:</span>
            <span class="value error-text">{{ selectedTask.failed_actions }}</span>
          </div>
          <div v-if="selectedTask.last_error" class="detail-row">
            <span class="label">{{ t('autoLikes.lastError') }}:</span>
            <span class="value error-text">{{ selectedTask.last_error }}</span>
          </div>
          <div class="detail-row">
            <span class="label">{{ t('autoLikes.startedAt') }}:</span>
            <span class="value">{{ formatDate(selectedTask.started_at) }}</span>
          </div>
          <div class="detail-row">
            <span class="label">{{ t('autoLikes.completedAt') }}:</span>
            <span class="value">{{ formatDate(selectedTask.completed_at) }}</span>
          </div>

          <!-- Task Logs -->
          <div class="logs-section">
            <h4>{{ t('autoLikes.logs') }}</h4>
            <DataTable
              :value="taskStore.taskLogs"
              :rows="5"
              :paginator="taskStore.taskLogs.length > 5"
              class="logs-table"
              :empty-message="t('autoLikes.noLogs')"
            >
              <Column :header="t('autoLikes.time')" style="width: 150px">
                <template #body="{ data }">
                  {{ formatDate(data.created_at) }}
                </template>
              </Column>
              <Column field="target" :header="t('autoLikes.target')" />
              <Column :header="t('autoLikes.result')" style="width: 80px">
                <template #body="{ data }">
                  <i
                    :class="data.success ? 'pi pi-check-circle success-icon' : 'pi pi-times-circle error-icon'"
                  />
                </template>
              </Column>
              <Column field="message" :header="t('autoLikes.message')">
                <template #body="{ data }">
                  <span :class="{ 'error-text': !data.success }">
                    {{ data.message || data.error || '-' }}
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
.autolikes-page {
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
  grid-template-columns: 480px 1fr;
  gap: 24px;
}

@media (max-width: 1280px) {
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
  color: #a855f7;
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

.create-btn {
  margin-top: 8px;
}

.tasks-table {
  font-size: 14px;
}

.channel-name {
  font-weight: 500;
  color: #e5e7eb;
}

.reaction-emoji {
  font-size: 20px;
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
  min-width: 120px;
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

.logs-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.logs-section h4 {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 12px;
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
  overflow: hidden;
}

:deep(.p-panel-header) {
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding: 16px 20px;
}

:deep(.p-panel-content) {
  background: transparent;
  padding: 20px;
  overflow: hidden;
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

/* Fix input overflow */
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
