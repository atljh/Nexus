<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, onActivated, onDeactivated, watch, nextTick } from 'vue'
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
const { t, locale } = useI18n()
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
const dateLocale = computed(() => (locale.value === 'uk' ? 'uk-UA' : 'en-US'))
const logsContainer = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const showAccountsCard = ref(true)
let loadTaskPromise: Promise<void> | null = null
let isPollingTickRunning = false

// Get task ID from route
const taskId = computed(() => Number(route.params.id))

// Filtered logs
const filteredLogs = computed(() => {
  let logs = taskStore.taskLogs

  if (logsFilter.value === 'success') {
    logs = logs.filter(log => log.success && log.action_type !== 'connect')
  } else if (logsFilter.value === 'failed') {
    logs = logs.filter(log => !log.success && log.action_type !== 'connect')
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
  return new Date(date).toLocaleString(dateLocale.value, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// Format log timestamp (HH:MM:SS)
function formatLogTime(date: string | null): string {
  if (!date) return '--:--:--'
  return new Date(date).toLocaleTimeString(dateLocale.value, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function formatDelayRange(currentTask: Task): string {
  const formatDelayValue = (value: number): string => {
    if (value >= 3600) {
      return `${(value / 3600).toFixed(value % 3600 === 0 ? 0 : 1)} ${t('taskResults.time.hours')}`
    }
    if (value >= 60) {
      return `${(value / 60).toFixed(value % 60 === 0 ? 0 : 1)} ${t('taskResults.time.minutes')}`
    }
    return `${value} ${t('taskResults.time.seconds')}`
  }
  return `${formatDelayValue(currentTask.min_delay)} — ${formatDelayValue(currentTask.max_delay)}`
}

function translateLogText(text?: string | null): string {
  if (!text) return ''

  const value = text.trim()

  const exactMap: Record<string, string> = {
    'Action was not executed': 'taskResults.logs.translate.actionNotExecuted',
    'Task auto-closed as stale before this account was processed': 'taskResults.logs.translate.staleAutoClosed',
    'Session is not authorized': 'taskResults.logs.translate.sessionNotAuthorized',
    'No session string': 'taskResults.logs.translate.noSessionString',
    'Reaction already set': 'taskResults.logs.translate.reactionAlreadySet',
    'Invalid reaction emoji': 'taskResults.logs.translate.invalidReactionEmoji',
    'Account cannot react in this channel': 'taskResults.logs.translate.accountCannotReactInChannel',
    'Channel is private': 'taskResults.logs.translate.channelPrivate',
    'Invalid message ID': 'taskResults.logs.translate.invalidMessageId',
    'Entity not resolved': 'taskResults.logs.translate.entityNotResolved',
    'Client not connected': 'taskResults.logs.translate.clientNotConnected',
    'No posts in channel': 'taskResults.logs.translate.noPostsInChannel',
    'Cannot comment in this channel': 'taskResults.logs.translate.cannotCommentInChannel',
    'Account banned in channel': 'taskResults.logs.translate.accountBannedInChannel',
    'Message ID invalid — post may not support comments': 'taskResults.logs.translate.messageIdInvalidPost',
    'No accounts assigned to task': 'taskResults.logs.translate.noAccountsAssigned',
    'No target channels specified': 'taskResults.logs.translate.noTargetChannelsSpecified',
    'No commentable channels found (no discussion groups linked)': 'taskResults.logs.translate.noCommentableChannelsFound',
    'All accounts failed to connect': 'taskResults.logs.translate.allAccountsFailedToConnect',
    'All accounts failed during channel resolution': 'taskResults.logs.translate.allAccountsFailedDuringResolution',
    'All accounts failed during channel setup': 'taskResults.logs.translate.allAccountsFailedDuringSetup',
    'No valid accounts for monitoring': 'taskResults.logs.translate.noValidAccountsForMonitoring',
    'Reactions are disabled in this channel': 'taskResults.logs.translate.reactionsDisabledInChannel',
    'No messages found in channel': 'taskResults.logs.translate.noMessagesFoundInChannel',
    'All eligible accounts exhausted before reaching total actions': 'taskResults.logs.translate.allEligibleAccountsExhausted',
    'Task stopped before reaching total actions': 'taskResults.logs.translate.taskStoppedBeforeTotal',
    'Connected': 'taskResults.logs.translate.connected',
    'Proxy test failed': 'taskResults.logs.translate.proxyTestFailed',
    'No discussion group linked': 'taskResults.logs.translate.noDiscussionGroupLinked',
    'Chat write forbidden': 'taskResults.logs.translate.chatWriteForbidden',
    'Account joined too many channels': 'taskResults.logs.translate.accountJoinedTooManyChannels',
    'Channel is private, cannot join': 'taskResults.logs.translate.channelPrivateCannotJoin',
    'No valid target channels remaining': 'taskResults.logs.translate.noValidTargetChannelsRemaining',
    'All accounts exhausted or blacklisted': 'taskResults.logs.translate.allAccountsExhaustedOrBlacklisted',
    'Failed to resolve any channels for monitoring': 'taskResults.logs.translate.failedToResolveChannels',
    'Joined via invite link': 'taskResults.logs.translate.joinedViaInviteLink',
    'Already subscribed': 'taskResults.logs.translate.alreadySubscribed',
    'Joined channel': 'taskResults.logs.translate.joinedChannel',
    'Private channel requires invite link': 'taskResults.logs.translate.privateChannelInviteRequired',
    'Invalid warming target': 'taskResults.logs.translate.invalidWarmingTarget',
    'Account unavailable before warming started': 'taskResults.logs.translate.accountUnavailableBeforeWarming',
    'All warming actions failed': 'taskResults.logs.translate.allWarmingActionsFailed',
    'No warming targets specified': 'taskResults.logs.translate.noWarmingTargetsSpecified',
    'No valid warming targets found': 'taskResults.logs.translate.noValidWarmingTargetsFound',
    'Setup failed': 'taskResults.logs.translate.setupFailed',
    'Channel blacklisted from a previous run': 'taskResults.logs.translate.channelBlacklistedFromPrevRun',
    'GetFullChannel returned no linked_chat_id': 'taskResults.logs.translate.getFullChannelNoLinked',
  }

  const mappedKey = exactMap[value]
  if (mappedKey) return t(mappedKey)

  const reactionMatch = value.match(/^Reaction\s+(.+)\s+sent$/i)
  if (reactionMatch) {
    return t('taskResults.logs.translate.reactionSent', { emoji: reactionMatch[1] })
  }

  const commentSentMatch = value.match(/^Comment sent to (.+)$/i)
  if (commentSentMatch) {
    return t('taskResults.logs.translate.commentSentTo', { target: commentSentMatch[1] })
  }

  const floodWaitMatch = value.match(/^FloodWait:\s*(\d+)s/i)
  if (floodWaitMatch) {
    return t('taskResults.logs.translate.floodWait', { seconds: floodWaitMatch[1] })
  }

  const slowModeMatch = value.match(/^SlowMode:\s*(\d+)s/i)
  if (slowModeMatch) {
    return t('taskResults.logs.translate.slowMode', { seconds: slowModeMatch[1] })
  }

  const skippedByStatusMatch = value.match(/^Account skipped by status:\s*(.+)$/i)
  if (skippedByStatusMatch) {
    return t('taskResults.logs.translate.accountSkippedByStatus', { status: skippedByStatusMatch[1] })
  }

  const joinFailedMatch = value.match(/^Join failed:\s*(.+)$/i)
  if (joinFailedMatch) {
    return t('taskResults.logs.translate.joinFailed', { reason: joinFailedMatch[1] })
  }

  const spamblockMatch = value.match(/^Spamblock:\s*(.+)$/i)
  if (spamblockMatch) {
    return t('taskResults.logs.translate.spamblock', { detail: spamblockMatch[1] })
  }

  const reactionsUnavailableMatch = value.match(/^Requested reactions not available in channel\. Available: (.+)$/i)
  if (reactionsUnavailableMatch) {
    return t('taskResults.logs.translate.reactionsNotAvailable', { available: reactionsUnavailableMatch[1] })
  }

  const discussionGroupReadyMatch = value.match(/^Discussion group (\d+) ready$/i)
  if (discussionGroupReadyMatch) {
    return t('taskResults.logs.translate.discussionGroupReady', { id: discussionGroupReadyMatch[1] })
  }

  const discussionGroupJoinFailedMatch = value.match(/^Discussion group join failed:\s*(.+)$/i)
  if (discussionGroupJoinFailedMatch) {
    return t('taskResults.logs.translate.discussionGroupJoinFailed', { reason: discussionGroupJoinFailedMatch[1] })
  }

  const discussionGroupIdMatch = value.match(/^discussion_group_id=(\d+)$/i)
  if (discussionGroupIdMatch) {
    return t('taskResults.logs.translate.discussionGroupId', { id: discussionGroupIdMatch[1] })
  }

  return value
}

const confirmHeader = computed(() => {
  if (confirmAction.value === 'delete') return t('taskResults.confirm.deleteHeader')
  if (confirmAction.value === 'restart') return t('taskResults.confirm.restartHeader')
  return t('taskResults.confirm.cancelHeader')
})

const confirmBody = computed(() => {
  if (confirmAction.value === 'delete') return t('taskResults.confirm.deleteBody')
  if (confirmAction.value === 'restart') return t('taskResults.confirm.restartBody')
  return t('taskResults.confirm.cancelBody')
})

const confirmButtonLabel = computed(() => {
  if (confirmAction.value === 'delete') return t('taskResults.actions.delete')
  if (confirmAction.value === 'restart') return t('taskResults.actions.restart')
  return t('taskResults.actions.stop')
})

function taskTypeRoute(taskType: string): string {
  if (taskType === 'likes') return '/autolikes'
  if (taskType === 'comments') return '/autocomments'
  if (taskType === 'warming') return '/warming'
  return '/'
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
  const started = await taskStore.startTask(task.value.id)
  if (!started) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('taskResults.loadError'), life: 2500 })
    return
  }
  toast.add({ severity: 'info', summary: t('taskResults.messages.started'), life: 2000 })
  taskStore.stopPolling()
  await loadTask()
  startPolling()
}

async function pauseTask() {
  if (!task.value) return
  const paused = await taskStore.pauseTask(task.value.id)
  if (!paused) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('taskResults.loadError'), life: 2500 })
    return
  }
  toast.add({ severity: 'info', summary: t('taskResults.messages.paused'), life: 2000 })
  await loadTask()
}

async function cancelTask() {
  if (!task.value) return
  const cancelled = await taskStore.cancelTask(task.value.id)
  if (!cancelled) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('taskResults.loadError'), life: 2500 })
    return
  }
  toast.add({ severity: 'info', summary: t('taskResults.messages.cancelled'), life: 2000 })
  showConfirmDialog.value = false
  confirmAction.value = null
  await loadTask()
  stopPolling()
}

async function deleteTask() {
  if (!task.value) return
  const taskType = task.value.task_type
  const deleted = await taskStore.deleteTask(task.value.id)
  if (!deleted) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('taskResults.loadError'), life: 2500 })
    return
  }
  toast.add({ severity: 'info', summary: t('taskResults.messages.deleted'), life: 2000 })
  showConfirmDialog.value = false
  confirmAction.value = null
  router.push(taskTypeRoute(taskType))
}

async function duplicateTask() {
  if (!task.value) return
  const dup = await taskStore.duplicateTask(task.value.id)
  if (dup) {
    toast.add({ severity: 'success', summary: t('taskResults.actions.duplicated'), detail: `#${dup.id}`, life: 2000 })
    router.push(`/task/${dup.id}`)
  }
}

function scrollLogsToBottom() {
  if (!autoScroll.value || !logsContainer.value) return
  logsContainer.value.scrollTop = logsContainer.value.scrollHeight
}

function onLogsScroll() {
  if (!logsContainer.value) return
  const el = logsContainer.value
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  autoScroll.value = atBottom
}

function showConfirm(action: 'cancel' | 'delete' | 'restart') {
  confirmAction.value = action
  showConfirmDialog.value = true
}

async function restartTask() {
  if (!task.value) return
  const result = await taskStore.restartTask(task.value.id)
  if (result) {
    toast.add({ severity: 'success', summary: t('taskResults.messages.restarted'), life: 2000 })
    showConfirmDialog.value = false
    confirmAction.value = null
    await loadTask()
  }
}

async function executeConfirmAction() {
  if (confirmAction.value === 'cancel') {
    await cancelTask()
  } else if (confirmAction.value === 'delete') {
    await deleteTask()
  } else if (confirmAction.value === 'restart') {
    await restartTask()
  }
}

// Load task data
async function loadTask() {
  if (loadTaskPromise) {
    await loadTaskPromise
    return
  }

  loading.value = true
  loadTaskPromise = (async () => {
    try {
      const result = await taskStore.fetchTask(taskId.value)
      if (result) {
        task.value = result
        const logsRequest = task.value.status === 'running'
          ? taskStore.fetchTaskLogs(taskId.value)
          : taskStore.fetchAllTaskLogs(taskId.value)
        await Promise.all([
          logsRequest,
          taskStore.fetchAccountStats(taskId.value),
          task.value.task_type === 'comments' ? taskStore.fetchTargetChannels(taskId.value) : Promise.resolve()
        ])
        nextTick(() => scrollLogsToBottom())
      }
    } catch (e: any) {
      console.error('Failed to load task:', e)
      toast.add({ severity: 'error', summary: t('taskResults.loadError'), detail: e?.message || '', life: 3000 })
    } finally {
      loading.value = false
      loadTaskPromise = null
    }
  })()

  await loadTaskPromise
}

// Polling for running tasks
async function runPollingTick() {
  if (isPollingTickRunning) return
  isPollingTickRunning = true

  try {
    if (task.value?.status === 'running') {
      await loadTask()
    } else {
      stopPolling()
    }
  } finally {
    isPollingTickRunning = false
  }
}

function startPolling() {
  if (pollingInterval.value) return
  pollingInterval.value = window.setInterval(() => {
    void runPollingTick()
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
  taskStore.stopPolling()
  await loadTask()

  // Redirect if task not found
  if (!task.value) {
    toast.add({ severity: 'warn', summary: t('taskResults.notFound'), life: 3000 })
    router.replace('/')
    return
  }

  if (task.value?.status === 'running') {
    startPolling()
  }
})

onActivated(() => {
  taskStore.stopPolling()
  if (task.value?.status === 'running') {
    startPolling()
  }
})

onDeactivated(() => {
  stopPolling()
})

onUnmounted(() => {
  stopPolling()
  isPollingTickRunning = false
})

// Watch for status changes + completion notifications
watch(() => task.value?.status, async (newStatus, oldStatus) => {
  if (newStatus === 'running') {
    startPolling()
  } else {
    stopPolling()
    }

    // Notify on task completion/failure
    if (oldStatus === 'running' && newStatus && newStatus !== 'running') {
    if (newStatus === 'completed') {
      toast.add({ severity: 'success', summary: t('taskResults.messages.completed'), detail: `${task.value?.completed_actions}/${task.value?.total_actions}`, life: 4000 })
    } else if (newStatus === 'failed') {
      toast.add({ severity: 'error', summary: t('taskResults.messages.failed'), detail: translateLogText(task.value?.last_error) || '', life: 5000 })
    } else if (newStatus === 'cancelled') {
      toast.add({ severity: 'warn', summary: t('taskResults.messages.cancelled'), life: 3000 })
      }
      // Final fetch to get complete stats and logs
      await Promise.all([
        taskStore.fetchAllTaskLogs(taskId.value),
        taskStore.fetchAccountStats(taskId.value)
      ])
      nextTick(() => scrollLogsToBottom())
  }
})
</script>

<template>
  <MainLayout>
    <div class="task-results-page">
      <!-- Loading State -->
      <div v-if="loading && !task" class="loading-state">
        <i class="pi pi-spin pi-spinner"></i>
        <span>{{ t('common.loading') }}</span>
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
              v-if="task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled'"
              icon="pi pi-refresh"
              :label="t('taskResults.actions.restart')"
              class="action-btn restart"
              @click="showConfirm('restart')"
            />
            <Button
              icon="pi pi-copy"
              :label="t('taskResults.actions.duplicate')"
              class="action-btn duplicate"
              @click="duplicateTask"
            />
            <Button
              v-if="task.status !== 'running' && task.status !== 'paused'"
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
                {{ translateLogText(task.last_error) }}
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
            <i class="pi pi-gauge stat-icon primary"></i>
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
                  <div v-if="task.config?.invite_link" class="config-row">
                    <span class="config-label">{{ t('taskResults.config.inviteLink') }}</span>
                    <span class="config-value">{{ task.config.invite_link }}</span>
                  </div>
                </template>

                <!-- For Comments -->
                <template v-if="task.task_type === 'comments'">
                  <div class="config-row">
                    <span class="config-label">{{ t('taskResults.config.channels') }}</span>
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
                  <div v-if="task.config?.invite_links?.length" class="config-row">
                    <span class="config-label">{{ t('taskResults.config.inviteLink') }}</span>
                    <span class="config-value">{{ task.config.invite_links[0] }}</span>
                  </div>
                  <div v-if="task.config?.post_id" class="config-row">
                    <span class="config-label">{{ t('taskResults.config.postId') }}</span>
                    <span class="config-value">#{{ task.config.post_id }}</span>
                  </div>
                  <div class="config-row">
                    <span class="config-label">{{ t('taskResults.config.templates') }}</span>
                    <span class="config-value">
                      {{ t('taskResults.config.templatesCount', { count: task.config?.templates?.length || 0 }) }}
                    </span>
                  </div>
                  <div class="config-row">
                    <span class="config-label">{{ t('taskResults.config.rotation') }}</span>
                    <span class="config-value">
                      {{ task.config?.rotation_mode === 'random' ? t('taskResults.rotation.random') : t('taskResults.rotation.roundRobin') }}
                    </span>
                  </div>
                  <div class="config-row">
                    <span class="config-label">{{ t('taskResults.config.commentsPerAccount') }}</span>
                    <span class="config-value">{{ task.config?.comments_per_account }}</span>
                  </div>
                </template>

                <template v-if="task.task_type === 'warming'">
                  <div class="config-row">
                    <span class="config-label">{{ t('taskResults.config.targets') }}</span>
                    <div class="config-tags">
                      <span
                        v-for="(target, idx) in task.config?.targets"
                        :key="idx"
                        class="config-tag channel"
                      >
                        {{ target }}
                      </span>
                    </div>
                  </div>
                  <div v-if="task.config?.speed_preset" class="config-row">
                    <span class="config-label">{{ t('taskResults.config.speedPreset') }}</span>
                    <span class="config-value">
                      {{ t(`taskResults.speedPreset.${task.config.speed_preset}`) }}
                    </span>
                  </div>
                </template>

                <div class="config-divider"></div>

                <div class="config-row">
                  <span class="config-label">{{ t('taskResults.config.delay') }}</span>
                  <span class="config-value">{{ formatDelayRange(task) }}</span>
                </div>
                <div v-if="task.max_concurrent > 1" class="config-row">
                  <span class="config-label">{{ t('taskResults.config.concurrent') }}</span>
                  <span class="config-value">{{ task.max_concurrent }}</span>
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
                <h3>{{ t('taskResults.channelsTitle') }}</h3>
              </div>
              <div class="channels-list">
                <div
                  v-for="channel in taskStore.targetChannels"
                  :key="channel.id"
                  class="channel-item"
                >
                  <div class="channel-main">
                    <span class="channel-name">{{ channel.channel_username }}</span>
                    <span v-if="channel.channel_title" class="channel-title">{{ channel.channel_title }}</span>
                  </div>
                  <div class="channel-stats">
                    <Tag
                      :value="channel.status"
                      :severity="getChannelStatusSeverity(channel.status)"
                      class="channel-status"
                    />
                    <span class="channel-sent">
                      {{ t('taskResults.commentsSent', { count: channel.comments_sent }) }}
                    </span>
                  </div>
                  <span v-if="channel.error_message" class="channel-error">
                    {{ channel.error_message }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Accounts Card -->
            <div v-if="taskStore.accountStats.length > 0 && showAccountsCard" class="accounts-card">
              <div class="card-header">
                <i class="pi pi-users"></i>
                <h3>{{ t('taskResults.stats.accounts') }} ({{ taskStore.accountStats.length }})</h3>
                <button class="toggle-card-btn" @click="showAccountsCard = !showAccountsCard">
                  <i :class="showAccountsCard ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"></i>
                </button>
              </div>
              <div class="accounts-list">
                <div
                  v-for="acc in taskStore.accountStats"
                  :key="acc.account_id"
                  class="account-stat-item"
                >
                  <div class="account-stat-info">
                    <span class="account-stat-name">{{ acc.phone || acc.username || `#${acc.account_id}` }}</span>
                    <span v-if="acc.status" :class="['account-stat-status', `status--${acc.status}`]">{{ acc.status }}</span>
                  </div>
                  <div class="account-stat-counts">
                    <span class="account-stat-ok">{{ acc.success }}</span>
                    <span class="account-stat-sep">/</span>
                    <span class="account-stat-err">{{ acc.failed }}</span>
                  </div>
                  <div class="account-stat-bar">
                    <div
                      class="account-stat-bar-fill"
                      :style="{ width: acc.total > 0 ? `${(acc.success / acc.total) * 100}%` : '0%' }"
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Templates Card (for comments) -->
            <div v-if="task.task_type === 'comments' && task.config?.templates" class="templates-card">
              <div class="card-header">
                <i class="pi pi-file-edit"></i>
                <h3>{{ t('taskResults.templatesTitle') }}</h3>
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
                <button
                  v-if="taskStore.logsHasMore"
                  class="show-all-logs-btn"
                  @click="taskStore.fetchAllTaskLogs(taskId)"
                  :title="t('taskResults.logs.showAll')"
                >
                  <i class="pi pi-list"></i>
                  {{ t('taskResults.logs.showAll') }}
                </button>
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
                    <span class="filter-count success">{{ taskStore.taskLogs.filter(l => l.success && l.action_type !== 'connect').length }}</span>
                  </button>
                  <button
                    :class="['filter-tab', { active: logsFilter === 'failed' }]"
                    @click="logsFilter = 'failed'"
                  >
                    {{ t('taskResults.logs.failed') }}
                    <span class="filter-count danger">{{ taskStore.taskLogs.filter(l => !l.success && l.action_type !== 'connect').length }}</span>
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

              <div ref="logsContainer" class="logs-list" @scroll="onLogsScroll">
                <div
                  v-for="log in filteredLogs"
                  :key="log.id"
                  :class="['log-line', { success: log.success, error: !log.success }]"
                >
                  <span class="log-ts">{{ formatLogTime(log.created_at) }}</span>
                  <span :class="log.success ? 'log-ok' : 'log-fail'">{{ log.success ? 'OK' : 'ERR' }}</span>
                  <span v-if="log.target" class="log-target">{{ log.target }}</span>
                  <span v-if="log.message" class="log-msg">{{ translateLogText(log.message) }}</span>
                  <span v-if="log.error" class="log-err">{{ translateLogText(log.error) }}</span>
                  <span v-if="log.extra_data?.comment" class="log-comment">"{{ log.extra_data.comment }}"</span>
                </div>

                <div v-if="taskStore.logsHasMore && logsFilter === 'all' && !logsSearch" class="logs-load-more">
                  <button class="load-more-btn" @click="taskStore.fetchTaskLogs(taskId, undefined, true)">
                    {{ t('taskResults.logs.loadMore') }}
                  </button>
                </div>

                <div v-if="filteredLogs.length === 0" class="logs-empty">
                  <i class="pi pi-inbox"></i>
                  <span>{{ t('taskResults.noLogs') }}</span>
                </div>
              </div>

              <!-- Auto-scroll indicator -->
              <div v-if="task?.status === 'running' && !autoScroll" class="autoscroll-hint" @click="autoScroll = true; scrollLogsToBottom()">
                <i class="pi pi-arrow-down"></i>
                {{ t('taskResults.logs.newEntries') }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Not Found State -->
      <div v-else class="not-found-state">
        <i class="pi pi-exclamation-triangle"></i>
        <h2>{{ t('taskResults.notFound') }}</h2>
        <p>{{ t('taskResults.notFoundDescription', { id: taskId }) }}</p>
        <Button
          :label="t('common.back')"
          icon="pi pi-arrow-left"
          @click="router.back()"
        />
      </div>

      <!-- Confirm Dialog -->
      <Dialog
        v-model:visible="showConfirmDialog"
        :header="confirmHeader"
        :style="{ width: '400px' }"
        modal
        class="confirm-dialog"
      >
        <div class="confirm-content">
          <i :class="['confirm-icon', 'pi', confirmAction === 'delete' ? 'pi-trash' : confirmAction === 'restart' ? 'pi-refresh' : 'pi-stop-circle']"></i>
          <p>{{ confirmBody }}</p>
        </div>
        <template #footer>
          <Button
            :label="t('common.cancel')"
            severity="secondary"
            outlined
            @click="showConfirmDialog = false"
          />
          <Button
            :label="confirmButtonLabel"
            :severity="confirmAction === 'delete' ? 'danger' : confirmAction === 'restart' ? 'info' : 'warn'"
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
  color: #8b8b95;
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
  color: #8b8b95;
}

.back-btn:hover {
  color: #fafafa;
  background: rgba(255, 255, 255, 0.08);
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
  color: #ababb5;
  background: rgba(255, 255, 255, 0.08);
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

.action-btn.restart {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #60a5fa;
}

.action-btn.restart:hover {
  background: rgba(59, 130, 246, 0.25);
}

.action-btn.delete {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #8b8b95;
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
.status-banner.status-cancelled .status-icon { color: #8b8f9a; }

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
  color: #ababb5;
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
  background: linear-gradient(90deg, #8b8f9a 0%, #4b5563 100%);
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
.status-banner.status-cancelled .progress-percent { color: #8b8f9a; }

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
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.10);
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
  color: #ababb5;
  background: rgba(255, 255, 255, 0.08);
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
  color: #8b8b95;
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
  background: linear-gradient(180deg, #161619 0%, #111114 100%);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 16px;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
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
  color: #8b8b95;
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
  color: #ababb5;
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
  background: rgba(255, 255, 255, 0.13);
  margin: 12px 0;
}

/* Channels Card */
.channels-list {
  padding: 12px 16px;
}

.channel-item {
  padding: 14px;
  background: rgba(255, 255, 255, 0.04);
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
  color: #8b8b95;
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
  color: #ababb5;
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
  color: #ababb5;
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
  color: #8b8b95;
  margin-left: auto;
}

.show-all-logs-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  font-size: 11px;
  color: #a855f7;
  background: rgba(168, 85, 247, 0.1);
  border: 1px solid rgba(168, 85, 247, 0.3);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.show-all-logs-btn:hover {
  background: rgba(168, 85, 247, 0.2);
  border-color: rgba(168, 85, 247, 0.5);
}

.show-all-logs-btn i {
  font-size: 11px;
  color: #a855f7;
}

.logs-filters {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
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
  color: #8b8b95;
  font-size: 12px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-tab:hover {
  color: #ababb5;
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
  color: #6e6e78;
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
  padding: 12px 16px;
  overflow-y: auto;
  max-height: 600px;
  font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.log-line {
  display: flex;
  gap: 8px;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-line:hover {
  background: rgba(255, 255, 255, 0.04);
}

.log-line.error {
  background: rgba(239, 68, 68, 0.06);
}

.log-ts {
  color: #6e6e78;
  flex-shrink: 0;
}

.log-ok {
  color: #4ade80;
  font-weight: 600;
  flex-shrink: 0;
  min-width: 26px;
}

.log-fail {
  color: #f87171;
  font-weight: 600;
  flex-shrink: 0;
  min-width: 26px;
}

.log-target {
  color: #e4e4e7;
  flex-shrink: 0;
}

.log-msg {
  color: #ababb5;
}

.log-err {
  color: #f87171;
}

.log-comment {
  color: #a855f7;
  font-style: italic;
}

.logs-load-more {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

.load-more-btn {
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  color: #9ca3af;
  font-size: 12px;
  padding: 6px 16px;
  cursor: pointer;
  transition: all 0.15s;
}

.load-more-btn:hover {
  border-color: rgba(168, 85, 247, 0.3);
  color: #a855f7;
}

.logs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px;
  color: #6e6e78;
}

.logs-empty i {
  font-size: 40px;
}

/* Auto-scroll hint */
.autoscroll-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background: rgba(168, 85, 247, 0.15);
  border-top: 1px solid rgba(168, 85, 247, 0.3);
  color: #c4b5fd;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.autoscroll-hint:hover {
  background: rgba(168, 85, 247, 0.25);
}

/* Duplicate button */
.action-btn.duplicate {
  background: rgba(168, 85, 247, 0.15);
  border: 1px solid rgba(168, 85, 247, 0.3);
  color: #c4b5fd;
}

.action-btn.duplicate:hover {
  background: rgba(168, 85, 247, 0.25);
}

/* Accounts Card */
.accounts-card {
  background: linear-gradient(180deg, #161619 0%, #111114 100%);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 16px;
  overflow: hidden;
}

.toggle-card-btn {
  background: none;
  border: none;
  color: #6e6e78;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: all 0.15s;
}

.toggle-card-btn:hover {
  color: #ababb5;
  background: rgba(255, 255, 255, 0.06);
}

.accounts-list {
  padding: 12px 16px;
  max-height: 400px;
  overflow-y: auto;
}

.account-stat-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  margin-bottom: 6px;
}

.account-stat-item:last-child {
  margin-bottom: 0;
}

.account-stat-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.account-stat-name {
  font-size: 13px;
  font-weight: 500;
  color: #e4e4e7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-stat-status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  color: #8b8b95;
  flex-shrink: 0;
}

.account-stat-status.status--valid { color: #4ade80; background: rgba(34, 197, 94, 0.15); }
.account-stat-status.status--banned { color: #f87171; background: rgba(239, 68, 68, 0.15); }
.account-stat-status.status--spamblock { color: #fbbf24; background: rgba(245, 158, 11, 0.15); }
.account-stat-status.status--session_expired { color: #f87171; background: rgba(239, 68, 68, 0.15); }

.account-stat-counts {
  display: flex;
  align-items: center;
  gap: 2px;
  font-family: 'SF Mono', monospace;
  font-size: 12px;
  flex-shrink: 0;
}

.account-stat-ok {
  color: #4ade80;
  font-weight: 600;
}

.account-stat-sep {
  color: #4b4b55;
}

.account-stat-err {
  color: #f87171;
  font-weight: 600;
}

.account-stat-bar {
  width: 60px;
  height: 4px;
  background: rgba(239, 68, 68, 0.3);
  border-radius: 2px;
  overflow: hidden;
  flex-shrink: 0;
}

.account-stat-bar-fill {
  height: 100%;
  background: #4ade80;
  border-radius: 2px;
  transition: width 0.3s ease;
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
  color: #8b8b95;
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
  color: #ababb5;
  margin: 0;
  max-width: 300px;
}

/* Dialog overrides */
:deep(.p-dialog) {
  background: #161619;
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 16px;
}

:deep(.p-dialog .p-dialog-header) {
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
}

:deep(.p-dialog .p-dialog-content) {
  background: transparent;
}

:deep(.p-dialog .p-dialog-footer) {
  background: transparent;
  border-top: 1px solid rgba(255, 255, 255, 0.10);
}
</style>
