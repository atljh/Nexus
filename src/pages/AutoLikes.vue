<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import MultiSelect from 'primevue/multiselect'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { AccountPicker } from '@/components/shared'

import { useTaskStore } from '@/stores/useTaskStore'
import { useAccountStore } from '@/stores/useAccountStore'
import { useChannelStore } from '@/stores/useChannelStore'
import type { Task, SavedChannel } from '@/types'
import { REACTION_EMOJIS } from '@/types'

// Convert readonly array to mutable for Dropdown
const reactionOptions = [...REACTION_EMOJIS]

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const taskStore = useTaskStore()
const accountStore = useAccountStore()
const channelStore = useChannelStore()

// Form state
const channel = ref('')
const postId = ref<number | null>(null)
const inviteLink = ref('')
const selectedSavedChannelId = ref<number | null>(null)
const selectedReactions = ref<string[]>(['👍'])
const emojiMode = ref<'single' | 'random' | 'all'>('single')
const minDelay = ref(30)
const maxDelay = ref(120)
const maxConcurrent = ref(1)
const selectedAccountIds = ref<number[]>([])
const parsedFromLink = ref(false)
const isPrivateChannel = computed(() => channel.value.startsWith('-100'))
const FORM_SAVE_DELAY_MS = 250
let formSaveTimer: number | null = null

// UI state
const isCreating = ref(false)

const savedChannelOptions = computed(() =>
  channelStore.channels.map((savedChannel) => ({
    value: savedChannel.id,
    label: savedChannel.title
      ? `${savedChannel.title} · ${savedChannel.normalized_target || savedChannel.invite_link || ''}`
      : savedChannel.display_name
  }))
)

function getSavedChannelTaskTarget(savedChannel: SavedChannel): string {
  if (savedChannel.normalized_target) return savedChannel.normalized_target
  return (savedChannel.invite_link || '').replace(/^https?:\/\//, '')
}

function applySavedChannel(savedChannel: SavedChannel): void {
  skipWatch = true
  channel.value = getSavedChannelTaskTarget(savedChannel)
  inviteLink.value = savedChannel.is_private ? (savedChannel.invite_link || '') : ''
  parsedFromLink.value = false
}

watch(selectedSavedChannelId, (channelId) => {
  if (!channelId) return
  const savedChannel = channelStore.channels.find((item) => item.id === channelId)
  if (!savedChannel) return
  applySavedChannel(savedChannel)
})

// Parse t.me links:
//   https://t.me/channel/12345 → @channel + postId
//   https://t.me/c/3548071275/129 → -1003548071275 + postId (private channel)
//   https://t.me/+XXXXX → invite link (kept as-is)
function parseTelegramLink(input: string): { channel: string; postId: number | null } | null {
  // Private channel format: t.me/c/CHANNEL_ID/POST_ID
  const privateMatch = input.match(/(?:https?:\/\/)?t\.me\/c\/(\d+)(?:\/(\d+))?/)
  if (privateMatch) {
    return {
      channel: '-100' + privateMatch[1],
      postId: privateMatch[2] ? parseInt(privateMatch[2], 10) : null
    }
  }
  // Invite link format: t.me/+HASH or t.me/joinchat/HASH
  const inviteMatch = input.match(/(?:https?:\/\/)?t\.me\/(\+[a-zA-Z0-9_-]+|joinchat\/[a-zA-Z0-9_-]+)/)
  if (inviteMatch) {
    return {
      channel: inviteMatch[0].replace(/^https?:\/\//, ''),
      postId: null
    }
  }
  // Public channel: t.me/username/POST_ID
  const match = input.match(/(?:https?:\/\/)?t\.me\/([a-zA-Z0-9_]+)(?:\/(\d+))?/)
  if (match) {
    return {
      channel: match[1],
      postId: match[2] ? parseInt(match[2], 10) : null
    }
  }
  return null
}

// Watch channel input for link pasting
let skipWatch = false
watch(channel, (val) => {
  if (skipWatch) {
    skipWatch = false
    return
  }
  const parsed = parseTelegramLink(val)
  if (parsed) {
    skipWatch = true
    // Don't prefix with @ for numeric IDs (private channels) or invite links
    if (parsed.channel.startsWith('-100') || parsed.channel.includes('t.me/')) {
      channel.value = parsed.channel
    } else {
      channel.value = '@' + parsed.channel
    }
    if (parsed.postId) {
      postId.value = parsed.postId
    }
    parsedFromLink.value = true
  }
})

// Form persistence
const FORM_KEY = 'nexus_autolikes_form'

function saveForm() {
  localStorage.setItem(FORM_KEY, JSON.stringify({
    channel: channel.value,
    postId: postId.value,
    inviteLink: inviteLink.value,
    selectedReactions: selectedReactions.value,
    emojiMode: emojiMode.value,
    minDelay: minDelay.value,
    maxDelay: maxDelay.value,
    maxConcurrent: maxConcurrent.value,
    selectedAccountIds: selectedAccountIds.value,
    parsedFromLink: parsedFromLink.value
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
    if (data.channel) { skipWatch = true; channel.value = data.channel }
    if (data.postId) postId.value = data.postId
    if (data.inviteLink) inviteLink.value = data.inviteLink
    if (data.selectedReactions?.length) selectedReactions.value = data.selectedReactions
    if (data.emojiMode) emojiMode.value = data.emojiMode
    if (data.minDelay != null) minDelay.value = data.minDelay
    if (data.maxDelay != null) maxDelay.value = data.maxDelay
    if (data.maxConcurrent != null) maxConcurrent.value = data.maxConcurrent
    if (data.selectedAccountIds?.length) selectedAccountIds.value = data.selectedAccountIds
    if (data.parsedFromLink) parsedFromLink.value = data.parsedFromLink
  } catch { /* ignore */ }
}

watch(
  [channel, postId, inviteLink, selectedReactions, emojiMode, minDelay, maxDelay, maxConcurrent, selectedAccountIds, parsedFromLink],
  scheduleFormSave,
  { deep: true }
)

// Emoji mode options
const emojiModeOptions = computed(() => [
  { value: 'single', label: t('autoLikes.emojiModes.single') },
  { value: 'random', label: t('autoLikes.emojiModes.random') },
  { value: 'all', label: t('autoLikes.emojiModes.all') }
])

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
  const ch = channel.value.trim()
  if (!ch) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoLikes.errors.channelRequired'),
      life: 3000
    })
    return
  }

  // Validate channel format: @username or username (alphanumeric + underscore, 5-32 chars)
  const cleanChannel = ch.startsWith('@') ? ch.slice(1) : ch
  const isValidChannel = /^-?\d+$/.test(ch)
    || ch.startsWith('t.me/+')
    || ch.startsWith('t.me/joinchat/')
    || /^[a-zA-Z0-9_]{5,32}$/.test(cleanChannel)
  if (!isValidChannel) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoLikes.errors.invalidChannel'),
      life: 3000
    })
    return
  }

  if (selectedReactions.value.length === 0) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoLikes.errors.reactionsRequired'),
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
        invite_link: inviteLink.value.trim() || undefined,
        reactions: selectedReactions.value,
        emoji_mode: emojiMode.value
      },
      account_ids: selectedAccountIds.value,
      min_delay: minDelay.value,
      max_delay: maxDelay.value,
      max_concurrent: maxConcurrent.value
    })

    if (task) {
      clearPendingFormSave()
      localStorage.removeItem(FORM_KEY)
      // Warn if some accounts were skipped
      if ((task as any).skipped_accounts) {
        toast.add({
          severity: 'warn',
          summary: t('common.warning'),
          detail: t('autoLikes.messages.accountsSkipped', { count: (task as any).skipped_accounts }),
          life: 5000
        })
      }
      // Auto-start the created task
      const started = await taskStore.startTask(task.id)
      if (started) {
        toast.add({
          severity: 'success',
          summary: t('common.success'),
          detail: t('autoLikes.messages.taskStarted'),
          life: 3000
        })
      } else {
        toast.add({
          severity: 'warn',
          summary: t('common.warning'),
          detail: t('autoLikes.messages.taskCreated'),
          life: 3000
        })
      }
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

// Computed task counts
const runningTasks = computed(() => taskStore.tasks.filter(t => t.status === 'running'))
const pendingTasks = computed(() => taskStore.tasks.filter(t => t.status === 'pending' || t.status === 'paused'))
// Batch actions
async function startAllPending() {
  const tasks = [...pendingTasks.value]
  const results = await Promise.allSettled(tasks.map(task => taskStore.startTask(task.id)))
  const started = results.filter(result => result.status === 'fulfilled' && result.value).length
  if (started > 0) {
    toast.add({
      severity: 'info',
      summary: t('autoLikes.tasksStarted', { count: started }),
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
  const results = await Promise.allSettled(tasks.map(task => taskStore.cancelTask(task.id)))
  const stopped = results.filter(result => result.status === 'fulfilled' && result.value).length
  if (stopped > 0) {
    toast.add({
      severity: 'info',
      summary: t('autoLikes.tasksStopped'),
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

// Task actions
async function startTask(task: Task) {
  if (task.status === 'running') return
  const ok = await taskStore.startTask(task.id)
  if (ok) {
    toast.add({
      severity: 'info',
      summary: t('autoLikes.messages.taskStarted'),
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
    summary: t('autoLikes.messages.taskDeleted'),
    life: 2000
  })
}

function viewTaskDetails(task: Task) {
  router.push(`/task/${task.id}`)
}

async function refreshTasks() {
  await taskStore.fetchTasks('likes', undefined, true)
  if (taskStore.hasRunningTasks) {
    taskStore.startPolling()
  } else {
    taskStore.stopPolling()
  }
}

// Initialize
onMounted(async () => {
  loadForm()
  await Promise.all([
    taskStore.fetchTasks('likes'),
    accountStore.fetchAccounts(),
    channelStore.fetchChannels()
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
    <div class="autolikes-page">
      <!-- Page Header -->
      <div class="page-header">
        <div class="header-content">
          <div class="header-icon">
            <i class="pi pi-heart"></i>
          </div>
          <div class="header-text">
            <h1>{{ t('nav.autoLikes') }}</h1>
            <p class="header-subtitle">{{ t('autoLikes.subtitle') }}</p>
          </div>
        </div>
        <div class="header-right">
          <!-- Control panel -->
          <div v-if="taskStore.tasks.length > 0" class="control-panel">
            <div class="control-status" :class="{ active: runningTasks.length > 0 }">
              <span class="status-dot"></span>
              <span class="status-text">
                <template v-if="runningTasks.length > 0">{{ t('autoLikes.controlStatus.running', { count: runningTasks.length }) }}</template>
                <template v-else-if="pendingTasks.length > 0">{{ t('autoLikes.controlStatus.pending', { count: pendingTasks.length }) }}</template>
                <template v-else>{{ t('autoLikes.controlStatus.none') }}</template>
              </span>
            </div>
            <div class="control-buttons">
              <button
                v-if="pendingTasks.length > 0 && runningTasks.length === 0"
                class="ctrl-btn ctrl-start"
                @click="startAllPending"
              >
                <i class="pi pi-play"></i>
                <span>{{ t('autoLikes.controlStart') }}</span>
              </button>
              <button
                v-if="runningTasks.length > 0"
                class="ctrl-btn ctrl-stop"
                @click="stopAllRunning"
              >
                <i class="pi pi-stop-circle"></i>
                <span>{{ t('autoLikes.controlStop') }}</span>
              </button>
            </div>
          </div>
          <div class="header-stats">
            <div class="stat-card">
              <span class="stat-value">{{ runningTasks.length }}</span>
              <span class="stat-label">{{ t('autoLikes.statsActive') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ taskStore.tasks.filter(t => t.status === 'completed').length }}</span>
              <span class="stat-label">{{ t('autoLikes.statsCompleted') }}</span>
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
              <h2>{{ t('autoLikes.createTask') }}</h2>
              <span class="card-header-hint">{{ t('autoLikes.createTaskHint') }}</span>
            </div>
          </div>

          <!-- Form Content -->
          <div class="tab-content">
            <div class="tab-panel">
              <!-- Account Picker -->
              <AccountPicker
                v-model="selectedAccountIds"
                accent-color="#ec4899"
              />
              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-hashtag"></i>
                  <span>{{ t('autoLikes.targetChannel') }}</span>
                </div>
                <div class="form-group">
                  <label class="form-label">{{ t('autoLikes.savedChannel') }}</label>
                  <Select
                    v-model="selectedSavedChannelId"
                    :options="savedChannelOptions"
                    option-label="label"
                    option-value="value"
                    :placeholder="t('autoLikes.savedChannelPlaceholder')"
                    class="w-full"
                    showClear
                  />
                  <small class="input-hint">
                    <i class="pi pi-bookmark"></i>
                    {{ t('autoLikes.savedChannelHint') }}
                  </small>
                  <InputText
                    v-model="channel"
                    :placeholder="t('autoLikes.channelPlaceholder')"
                    class="w-full"
                  />
                  <small v-if="parsedFromLink" class="parsed-link-hint">
                    <i class="pi pi-check-circle"></i>
                    {{ postId ? t('autoLikes.linkParsedWithPost', { channel, postId }) : t('autoLikes.linkParsed', { channel }) }}
                  </small>
                  <div v-if="isPrivateChannel" class="invite-link-field">
                    <label class="form-label">
                      <i class="pi pi-link"></i>
                      {{ t('autoLikes.inviteLink') }}
                    </label>
                    <InputText
                      v-model="inviteLink"
                      :placeholder="t('autoLikes.inviteLinkPlaceholder')"
                      class="w-full"
                    />
                    <small class="input-hint">
                      <i class="pi pi-info-circle"></i>
                      {{ t('autoLikes.inviteLinkHint') }}
                    </small>
                  </div>
                </div>
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-cog"></i>
                  <span>{{ t('autoLikes.reactions') }}</span>
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
                    :placeholder="t('autoLikes.selectReactions')"
                    :maxSelectedLabels="5"
                    class="w-full"
                    display="chip"
                  />
                </div>
                <div class="form-group" style="margin-top: 14px">
                  <label class="form-label">
                    <i class="pi pi-sliders-h"></i>
                    {{ t('autoLikes.emojiMode') }}
                  </label>
                  <Select
                    v-model="emojiMode"
                    :options="emojiModeOptions"
                    option-label="label"
                    option-value="value"
                    class="w-full"
                  />
                  <small class="emoji-mode-hint">
                    {{ t(`autoLikes.emojiModeHints.${emojiMode}`) }}
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
                  <span>{{ t('autoLikes.limits') }}</span>
                </div>
                <div class="form-grid-2">
                  <div class="form-group">
                    <label class="form-label">{{ t('autoLikes.concurrent') }}</label>
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
                  <span>{{ t('autoLikes.delay') }}</span>
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
                      <span class="input-suffix">{{ t('autoLikes.sec') }}</span>
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
                      <span class="input-suffix">{{ t('autoLikes.sec') }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Create Button -->
          <div class="create-action">
            <button
              class="launch-btn"
              :class="{ ready: channel.trim() && selectedAccountIds.length > 0, loading: isCreating }"
              :disabled="!channel.trim() || selectedAccountIds.length === 0 || isCreating"
              @click="createTask"
            >
              <span class="launch-btn-glow"></span>
              <span class="launch-btn-content">
                <i v-if="isCreating" class="pi pi-spin pi-spinner"></i>
                <i v-else class="pi pi-play"></i>
                <span>{{ t('autoLikes.startTask') }}</span>
              </span>
              <span class="launch-btn-badges">
                <span :class="['badge', { ok: channel.trim().length > 0 }]">
                  <i :class="channel.trim().length > 0 ? 'pi pi-check' : 'pi pi-minus'"></i>
                  {{ t('autoLikes.badgeChannel') }}
                </span>
                <span :class="['badge', { ok: selectedAccountIds.length > 0 }]">
                  <i :class="selectedAccountIds.length > 0 ? 'pi pi-check' : 'pi pi-minus'"></i>
                  {{ t('autoLikes.badgeAccounts', { count: selectedAccountIds.length }) }}
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
              <h2>{{ t('autoLikes.tasks') }}</h2>
              <span class="card-header-hint">{{ t('autoLikes.tasksCount', { count: taskStore.tasks.length }) }}</span>
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

              <div class="task-meta">
                <span class="task-accounts-count">
                  <i class="pi pi-users"></i> {{ task.accounts_count }}
                </span>
                <span class="task-time">{{ timeAgo(task.created_at) }}</span>
              </div>

              <div class="task-progress-section">
                <div class="progress-info">
                  <span class="progress-label">{{ t('autoLikes.progress') }}</span>
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
                  v-tooltip.top="t('autoLikes.tooltipStart')"
                  @click="startTask(task)"
                />
                <Button
                  v-if="task.status === 'running'"
                  icon="pi pi-pause"
                  rounded
                  class="action-btn pause"
                  v-tooltip.top="t('autoLikes.tooltipPause')"
                  @click="pauseTask(task)"
                />
                <Button
                  v-if="task.status === 'running' || task.status === 'paused'"
                  icon="pi pi-stop"
                  rounded
                  class="action-btn stop"
                  v-tooltip.top="t('autoLikes.tooltipStop')"
                  @click="cancelTask(task)"
                />
                <Button
                  v-if="task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled'"
                  icon="pi pi-refresh"
                  rounded
                  class="action-btn restart"
                  v-tooltip.top="t('autoLikes.tooltipRestart')"
                  @click="restartTask(task)"
                />
                <Button
                  icon="pi pi-eye"
                  rounded
                  class="action-btn view"
                  v-tooltip.top="t('autoLikes.tooltipDetails')"
                  @click="viewTaskDetails(task)"
                />
                <Button
                  v-if="task.status !== 'running' && task.status !== 'paused'"
                  icon="pi pi-trash"
                  rounded
                  class="action-btn delete"
                  v-tooltip.top="t('autoLikes.tooltipDelete')"
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
              <i class="pi pi-heart"></i>
            </div>
            <h3>{{ t('autoLikes.noTasks') }}</h3>
            <p>{{ t('autoLikes.noTasksHint') }}</p>
          </div>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
/* Page Layout — viewport-constrained, no page scroll */
.autolikes-page {
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
  background: rgba(255, 255, 255, 0.10);
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
  background: rgba(255, 255, 255, 0.10);
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
  color: #ec4899;
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
  background: linear-gradient(135deg, rgba(236, 72, 153, 0.15) 0%, rgba(236, 72, 153, 0.05) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-header-icon i {
  font-size: 15px;
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
  color: #8b8b95;
}

/* Form Content — scrollable */
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
  background: rgba(255, 255, 255, 0.15);
}

.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Form Sections */
.form-section {
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 12px;
  padding: 14px 16px;
}

.form-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
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


.emoji-mode-hint {
  font-size: 11px;
  color: #8b8b95;
  margin-top: 4px;
}

.parsed-link-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #22c55e;
  margin-top: 4px;
}

.parsed-link-hint i {
  font-size: 12px;
}

.invite-link-field {
  margin-top: 12px;
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
  border: 1px solid rgba(236, 72, 153, 0.25);
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(236, 72, 153, 0.08) 0%, rgba(168, 85, 247, 0.06) 100%);
  cursor: not-allowed;
  opacity: 0.5;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.launch-btn.ready {
  cursor: pointer;
  opacity: 1;
  border-color: rgba(236, 72, 153, 0.4);
  background: linear-gradient(145deg, rgba(236, 72, 153, 0.12) 0%, rgba(168, 85, 247, 0.08) 100%);
}

.launch-btn.ready:hover {
  border-color: rgba(236, 72, 153, 0.6);
  background: linear-gradient(145deg, rgba(236, 72, 153, 0.18) 0%, rgba(168, 85, 247, 0.12) 100%);
  transform: translateY(-1px);
  box-shadow: 0 8px 32px rgba(236, 72, 153, 0.2), 0 0 0 1px rgba(236, 72, 153, 0.1);
}

.launch-btn.ready:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(236, 72, 153, 0.15);
}

.launch-btn-glow {
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle at center, rgba(236, 72, 153, 0.06) 0%, transparent 70%);
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
  color: #ec4899;
  letter-spacing: 0.02em;
  position: relative;
  z-index: 1;
}

.launch-btn-content i {
  font-size: 16px;
}

.launch-btn.ready .launch-btn-content {
  color: #f472b6;
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
  background: rgba(255, 255, 255, 0.10);
  border: 1px solid rgba(255, 255, 255, 0.04);
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
  background: rgba(255, 255, 255, 0.10);
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
  color: #8b8b95;
}

.task-channel i {
  font-size: 11px;
}

.channel-name {
  color: #ababb5;
}

.reaction-emoji {
  font-size: 16px;
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
  color: rgba(236, 72, 153, 0.25);
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
  border: 1px solid rgba(236, 72, 153, 0.08);
}

.ring-1 {
  inset: 0;
  animation: ring-breathe 4s ease-in-out infinite;
}

.ring-2 {
  inset: 12px;
  border-color: rgba(236, 72, 153, 0.12);
  animation: ring-breathe 4s ease-in-out infinite 0.5s;
}

.ring-3 {
  inset: 24px;
  border-color: rgba(236, 72, 153, 0.06);
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

/* Override PrimeVue styles */
:deep(.p-inputnumber-buttons-horizontal .p-button) {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.13);
  color: #8b8b95;
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
