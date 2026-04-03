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
import { AccountPicker, DropZone } from '@/components/shared'

import { useTaskStore } from '@/stores/useTaskStore'
import { useAccountStore } from '@/stores/useAccountStore'
import { useChannelStore } from '@/stores/useChannelStore'
import type { Task, CommentTemplate, SavedChannel } from '@/types'
import { DEFAULT_COMMENT_TEMPLATES } from '@/types'

const router = useRouter()
const { t, locale } = useI18n()

// Spintax examples — cannot go through vue-i18n (curly braces conflict)
const spintaxPlaceholder = computed(() =>
  locale.value === 'uk'
    ? '{Чудово|Круто|Клас}! {Дуже|Супер} {корисно|цікаво}!'
    : '{Great|Awesome|Nice}! {Very|Super} {useful|interesting}!'
)
const spintaxHintText = computed(() =>
  locale.value === 'uk'
    ? 'Використовуйте {варіант1|варіант2|варіант3} для випадкових варіацій'
    : 'Use {option1|option2|option3} for random variations'
)
const toast = useToast()
const taskStore = useTaskStore()
const accountStore = useAccountStore()
const channelStore = useChannelStore()

// Form state
const channelInput = ref('')
const inviteLinkInput = ref('')
const selectedSavedChannelId = ref<number | null>(null)
const parsedFromLink = ref(false)
const selectedTemplateIds = ref<number[]>([])
const customTemplates = ref<string[]>([])
const rotationMode = ref<'random' | 'round_robin'>('random')
const commentsPerAccount = ref(1)
const totalActions = ref(1)
const minDelay = ref(60)
const maxDelay = ref(300)
const maxConcurrent = ref(1)
const selectedAccountIds = ref<number[]>([])
const templateCategoryFilter = ref<'all' | string>('all')
const templateSearchQuery = ref('')
const importTemplateCategory = ref('')
const isImportingTemplates = ref(false)
const isPrivateChannel = computed(() => channelInput.value.startsWith('-100'))

// Parse t.me links:
//   t.me/channel/123 → @channel + postId 123
//   t.me/c/3548071275/129 → -1003548071275 + postId 129
//   t.me/+HASH or t.me/joinchat/HASH → kept as invite link
const detectedPostId = ref<number | null>(null)
const FORM_SAVE_DELAY_MS = 250
let formSaveTimer: number | null = null

function parseTelegramLink(input: string): { channel: string; postId?: number } | null {
  // Private channel: t.me/c/CHANNEL_ID/POST_ID
  const privateMatch = input.match(/(?:https?:\/\/)?t\.me\/c\/(\d+)(?:\/(\d+))?/)
  if (privateMatch) {
    return {
      channel: '-100' + privateMatch[1],
      postId: privateMatch[2] ? parseInt(privateMatch[2], 10) : undefined
    }
  }
  // Invite link: t.me/+HASH or t.me/joinchat/HASH — keep full link for backend
  const inviteMatch = input.match(/(?:https?:\/\/)?t\.me\/(\+[a-zA-Z0-9_-]+|joinchat\/[a-zA-Z0-9_-]+)/)
  if (inviteMatch) {
    return { channel: 't.me/' + inviteMatch[1] }
  }
  // Public channel: t.me/username/POST_ID
  const match = input.match(/(?:https?:\/\/)?t\.me\/([a-zA-Z0-9_]+)(?:\/(\d+))?/)
  if (match) {
    return {
      channel: match[1],
      postId: match[2] ? parseInt(match[2], 10) : undefined
    }
  }
  return null
}

// Watch channel input for link pasting (mirrors AutoLikes pattern)
let skipWatch = false
watch(channelInput, (val) => {
  if (skipWatch) {
    skipWatch = false
    return
  }
  const parsed = parseTelegramLink(val)
  if (parsed) {
    skipWatch = true
    if (parsed.channel.startsWith('-100') || parsed.channel.includes('t.me/')) {
      channelInput.value = parsed.channel
    } else {
      channelInput.value = '@' + parsed.channel
    }
    if (parsed.postId) {
      detectedPostId.value = parsed.postId
    }
    parsedFromLink.value = true
  }
})

// Sync defaults: commentsPerAccount=1, totalActions = accounts count
watch(selectedAccountIds, (ids) => {
  const count = ids.length || 1
  if (commentsPerAccount.value === 1) {
    totalActions.value = count
  }
})
watch(commentsPerAccount, (perAcc) => {
  totalActions.value = perAcc * (selectedAccountIds.value.length || 1)
})

// Form persistence
const FORM_KEY = 'nexus_autocomments_form'

function saveForm() {
  localStorage.setItem(FORM_KEY, JSON.stringify({
    channelInput: channelInput.value,
    inviteLinkInput: inviteLinkInput.value,
    parsedFromLink: parsedFromLink.value,
    detectedPostId: detectedPostId.value,
    selectedTemplateIds: selectedTemplateIds.value,
    customTemplates: customTemplates.value,
    rotationMode: rotationMode.value,
    commentsPerAccount: commentsPerAccount.value,
    totalActions: totalActions.value,
    minDelay: minDelay.value,
    maxDelay: maxDelay.value,
    maxConcurrent: maxConcurrent.value,
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
    if (data.channelInput) channelInput.value = data.channelInput
    if (data.inviteLinkInput) inviteLinkInput.value = data.inviteLinkInput
    if (data.parsedFromLink) parsedFromLink.value = data.parsedFromLink
    if (data.detectedPostId != null) detectedPostId.value = data.detectedPostId
    if (data.selectedTemplateIds?.length) selectedTemplateIds.value = data.selectedTemplateIds
    if (data.customTemplates?.length) customTemplates.value = data.customTemplates
    if (data.rotationMode) rotationMode.value = data.rotationMode
    if (data.commentsPerAccount != null) commentsPerAccount.value = data.commentsPerAccount
    if (data.totalActions != null) totalActions.value = data.totalActions
    if (data.minDelay != null) minDelay.value = data.minDelay
    if (data.maxDelay != null) maxDelay.value = data.maxDelay
    if (data.maxConcurrent != null) maxConcurrent.value = data.maxConcurrent
    if (data.selectedAccountIds?.length) selectedAccountIds.value = data.selectedAccountIds
  } catch { /* ignore */ }
}

watch(
  [channelInput, inviteLinkInput, parsedFromLink, detectedPostId, selectedTemplateIds, customTemplates, rotationMode, commentsPerAccount, totalActions, minDelay, maxDelay, maxConcurrent, selectedAccountIds],
  scheduleFormSave,
  { deep: true }
)

// Template management
const showTemplateDialog = ref(false)
const editingTemplateId = ref<number | null>(null)
const newTemplateName = ref('')
const newTemplateContent = ref('')
const newTemplateCategory = ref('General')
const templatePreview = ref<string[]>([])

// UI state
const isCreating = ref(false)
const activeTab = ref(0)

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
  channelInput.value = getSavedChannelTaskTarget(savedChannel)
  inviteLinkInput.value = savedChannel.is_private ? (savedChannel.invite_link || '') : ''
  parsedFromLink.value = false
}

watch(selectedSavedChannelId, (channelId) => {
  if (!channelId) return
  const savedChannel = channelStore.channels.find((item) => item.id === channelId)
  if (!savedChannel) return
  applySavedChannel(savedChannel)
})

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

const templateCategories = computed(() => {
  const counts = new Map<string, number>()
  for (const template of taskStore.templates) {
    const category = template.category?.trim() || 'General'
    counts.set(category, (counts.get(category) || 0) + 1)
  }

  return Array.from(counts.entries())
    .sort((a, b) => a[0].localeCompare(b[0], locale.value))
    .map(([value, count]) => ({
      value,
      count
    }))
})

// Template options for multiselect
const templateOptions = computed(() =>
  taskStore.templates.map(tmpl => ({
    value: tmpl.id,
    label: `${tmpl.name} · ${tmpl.category || 'General'}`
  }))
)

const filteredTemplateLibrary = computed(() => {
  const query = templateSearchQuery.value.trim().toLowerCase()
  return taskStore.templates.filter((template) => {
    const matchesCategory = templateCategoryFilter.value === 'all'
      || (template.category || 'General') === templateCategoryFilter.value
    if (!matchesCategory) return false

    if (!query) return true
    return [
      template.name,
      template.content,
      template.category
    ].some(value => value?.toLowerCase().includes(query))
  })
})

const groupedTemplates = computed(() => {
  const groups = new Map<string, CommentTemplate[]>()
  for (const template of filteredTemplateLibrary.value) {
    const category = template.category || 'General'
    const existing = groups.get(category) || []
    existing.push(template)
    groups.set(category, existing)
  }

  return Array.from(groups.entries())
    .sort((a, b) => a[0].localeCompare(b[0], locale.value))
    .map(([category, templates]) => ({
      category,
      templates: [...templates].sort((a, b) => a.name.localeCompare(b.name, locale.value))
    }))
})

// Combined templates for task
const selectedTemplates = computed(() => {
  const values = [
    ...taskStore.templates
      .filter(tmpl => selectedTemplateIds.value.includes(tmpl.id))
      .map(tmpl => tmpl.content),
    ...customTemplates.value
  ]

  const seen = new Set<string>()
  return values
    .map(value => value.trim())
    .filter((value) => {
      if (!value) return false
      const key = value.toLowerCase()
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
})

watch(templateCategories, (categories) => {
  if (templateCategoryFilter.value === 'all') return
  const exists = categories.some(category => category.value === templateCategoryFilter.value)
  if (!exists) {
    templateCategoryFilter.value = 'all'
  }
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
  const channelVal = channelInput.value.trim()
  if (!channelVal) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoComments.errors.channelsRequired'),
      life: 3000
    })
    return
  }

  // Validate channel format (allow @username, numeric IDs, invite links)
  const isValidChannel = (() => {
    if (/^-?\d+$/.test(channelVal)) return true
    if (channelVal.startsWith('t.me/+') || channelVal.startsWith('t.me/joinchat/')) return true
    const clean = channelVal.startsWith('@') ? channelVal.slice(1) : channelVal
    return /^[a-zA-Z0-9_]{5,32}$/.test(clean)
  })()
  if (!isValidChannel) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoComments.errors.invalidChannel', { channel: channelVal }),
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
    const cleanChannel = channelVal.startsWith('@') ? channelVal.slice(1) : channelVal
    const task = await taskStore.createCommentsTask({
      config: {
        channels: [cleanChannel],
        invite_links: inviteLinkInput.value.trim() ? [inviteLinkInput.value.trim()] : undefined,
        post_id: detectedPostId.value || undefined,
        templates: selectedTemplates.value,
        rotation_mode: rotationMode.value,
        comments_per_account: commentsPerAccount.value,
        mode: 'single'
      },
      account_ids: selectedAccountIds.value,
      total_actions: totalActions.value,
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
  const results = await Promise.allSettled(tasks.map(task => taskStore.startTask(task.id)))
  const started = results.filter(result => result.status === 'fulfilled' && result.value).length
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
  const results = await Promise.allSettled(tasks.map(task => taskStore.cancelTask(task.id)))
  const stopped = results.filter(result => result.status === 'fulfilled' && result.value).length
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
function resetTemplateDialog() {
  editingTemplateId.value = null
  newTemplateName.value = ''
  newTemplateContent.value = ''
  newTemplateCategory.value = templateCategoryFilter.value === 'all'
    ? 'General'
    : templateCategoryFilter.value
  templatePreview.value = []
}

function openCreateTemplateDialog() {
  resetTemplateDialog()
  showTemplateDialog.value = true
}

function openEditTemplateDialog(template: CommentTemplate) {
  editingTemplateId.value = template.id
  newTemplateName.value = template.name
  newTemplateContent.value = template.content
  newTemplateCategory.value = template.category || 'General'
  showTemplateDialog.value = true
  generatePreview()
}

async function saveTemplate() {
  if (!newTemplateName.value.trim() || !newTemplateContent.value.trim()) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('autoComments.errors.templateRequired'),
      life: 3000
    })
    return
  }

  const payload = {
    name: newTemplateName.value.trim(),
    content: newTemplateContent.value.trim(),
    category: newTemplateCategory.value.trim() || 'General'
  }

  const template = editingTemplateId.value == null
    ? await taskStore.createTemplate(payload.name, payload.content, payload.category)
    : await taskStore.updateTemplate(editingTemplateId.value, payload)

  if (template) {
    await taskStore.fetchTemplates(true)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: editingTemplateId.value == null
        ? t('autoComments.messages.templateCreated')
        : t('autoComments.messages.templateUpdated'),
      life: 3000
    })
    resetTemplateDialog()
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
  await Promise.all(DEFAULT_COMMENT_TEMPLATES.map(template =>
    taskStore.createTemplate(template.name, template.content, 'General')
  ))
  await taskStore.fetchTemplates(true)
  toast.add({
    severity: 'success',
    summary: t('autoComments.messages.defaultsLoaded'),
    life: 2000
  })
}

function selectTemplateCategory(category: string) {
  const next = new Set(selectedTemplateIds.value)
  taskStore.templates
    .filter(template => (template.category || 'General') === category)
    .forEach(template => next.add(template.id))
  selectedTemplateIds.value = Array.from(next)
}

function clearTemplateCategory(category: string) {
  const categoryIds = new Set(
    taskStore.templates
      .filter(template => (template.category || 'General') === category)
      .map(template => template.id)
  )
  selectedTemplateIds.value = selectedTemplateIds.value.filter(id => !categoryIds.has(id))
}

function isTemplateCategorySelected(category: string) {
  const categoryIds = taskStore.templates
    .filter(template => (template.category || 'General') === category)
    .map(template => template.id)
  return categoryIds.length > 0 && categoryIds.every(id => selectedTemplateIds.value.includes(id))
}

async function handleTemplateImport(files: File[]) {
  const [file] = files
  if (!file) return

  isImportingTemplates.value = true
  try {
    const result = await taskStore.importTemplates(file, importTemplateCategory.value)
    if (!result) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('autoComments.messages.importFailed'),
        life: 3000
      })
      return
    }

    if (result.detected_categories.length > 0) {
      templateCategoryFilter.value = result.detected_categories[0]
      if (!importTemplateCategory.value.trim()) {
        importTemplateCategory.value = result.detected_categories[0]
      }
    }

    const severity = result.imported > 0 ? 'success' : 'warn'
    toast.add({
      severity,
      summary: result.imported > 0 ? t('common.success') : t('common.warning'),
      detail: t('autoComments.messages.importSummary', {
        imported: result.imported,
        duplicates: result.skipped_duplicates,
        invalid: result.skipped_invalid
      }),
      life: 4000
    })
  } finally {
    isImportingTemplates.value = false
  }
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
  loadForm()
  await Promise.all([
    taskStore.fetchTasks('comments'),
    taskStore.fetchTemplates(),
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
                  <span>{{ t('autoComments.targetPost') }}</span>
                </div>
                <div class="form-group">
                  <label class="form-label">{{ t('autoComments.savedChannel') }}</label>
                  <Select
                    v-model="selectedSavedChannelId"
                    :options="savedChannelOptions"
                    option-label="label"
                    option-value="value"
                    :placeholder="t('autoComments.savedChannelPlaceholder')"
                    class="w-full"
                    showClear
                  />
                  <small class="input-hint">
                    <i class="pi pi-bookmark"></i>
                    {{ t('autoComments.savedChannelHint') }}
                  </small>
                  <InputText
                    v-model="channelInput"
                    :placeholder="t('autoComments.channelPlaceholder')"
                    class="w-full"
                  />
                  <small v-if="parsedFromLink" class="parsed-link-hint">
                    <i class="pi pi-check-circle"></i>
                    {{ detectedPostId
                      ? t('autoComments.linkParsedWithPost', { channel: channelInput, postId: detectedPostId })
                      : t('autoComments.linkParsed', { channel: channelInput })
                    }}
                  </small>
                  <div v-if="isPrivateChannel" class="invite-link-field">
                    <label class="form-label">
                      <i class="pi pi-link"></i>
                      {{ t('autoComments.inviteLink') }}
                    </label>
                    <InputText
                      v-model="inviteLinkInput"
                      :placeholder="t('autoComments.inviteLinkPlaceholder')"
                      class="w-full"
                    />
                    <small class="input-hint">
                      <i class="pi pi-info-circle"></i>
                      {{ t('autoComments.inviteLinkHint') }}
                    </small>
                  </div>
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
                <div class="form-grid-2" style="margin-top: 12px;">
                  <div class="form-group">
                    <label class="form-label">{{ t('autoComments.concurrent') }}</label>
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
                  <div class="form-group">
                    <label class="form-label">{{ t('autoComments.rotationMode') }}</label>
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
                  <i class="pi pi-folder-open"></i>
                  <span>{{ t('autoComments.libraryTitle') }}</span>
                </div>
                <div class="template-toolbar">
                  <InputText
                    v-model="templateSearchQuery"
                    :placeholder="t('autoComments.searchTemplatesPlaceholder')"
                    class="template-search-input"
                  />
                  <Button
                    :label="t('autoComments.createTemplate')"
                    icon="pi pi-plus"
                    class="create-template-btn"
                    @click="openCreateTemplateDialog"
                  />
                </div>
                <div class="template-filter-row">
                  <button
                    :class="['template-filter-chip', { active: templateCategoryFilter === 'all' }]"
                    @click="templateCategoryFilter = 'all'"
                  >
                    <span>{{ t('autoComments.allGroups') }}</span>
                    <strong>{{ taskStore.templates.length }}</strong>
                  </button>
                  <button
                    v-for="category in templateCategories"
                    :key="category.value"
                    :class="['template-filter-chip', { active: templateCategoryFilter === category.value }]"
                    @click="templateCategoryFilter = category.value"
                  >
                    <span>{{ category.value }}</span>
                    <strong>{{ category.count }}</strong>
                  </button>
                </div>
                <div class="template-import-panel">
                  <div class="template-import-copy">
                    <strong>{{ t('autoComments.importTitle') }}</strong>
                    <span>{{ t('autoComments.importHint') }}</span>
                  </div>
                  <div class="template-import-controls">
                    <InputText
                      v-model="importTemplateCategory"
                      :placeholder="t('autoComments.importCategoryPlaceholder')"
                      class="w-full"
                    />
                    <small class="input-hint">
                      <i class="pi pi-info-circle"></i>
                      {{ t('autoComments.importCategoryHint') }}
                    </small>
                  </div>
                  <DropZone
                    accept=".xlsx"
                    :multiple="false"
                    :disabled="isImportingTemplates"
                    :title="t('autoComments.importDropTitle')"
                    :hint="t('autoComments.importDropHint')"
                    :formats="['.xlsx']"
                    class="template-import-dropzone"
                    @files-selected="handleTemplateImport"
                  >
                    <template #icon>
                      <i :class="['pi', isImportingTemplates ? 'pi-spin pi-spinner' : 'pi-file-excel', 'drop-zone-icon']"></i>
                    </template>
                  </DropZone>
                </div>
                <div v-if="taskStore.templates.length === 0" class="template-actions-bar">
                  <Button
                    :label="t('autoComments.loadDefaults')"
                    icon="pi pi-download"
                    severity="secondary"
                    outlined
                    @click="loadDefaultTemplates"
                  />
                </div>
              </div>

              <div class="form-section">
                <div class="form-section-header">
                  <i class="pi pi-check-square"></i>
                  <span>{{ t('autoComments.selectTemplates') }}</span>
                </div>
                <div class="template-selection-row">
                  <MultiSelect
                    v-model="selectedTemplateIds"
                    :options="templateOptions"
                    option-label="label"
                    option-value="value"
                    :placeholder="t('autoComments.selectTemplatesPlaceholder')"
                    class="w-full"
                    display="chip"
                  />
                  <span class="template-selection-counter">
                    {{ t('autoComments.selectedTemplatesCount', { count: selectedTemplateIds.length }) }}
                  </span>
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

              <div v-if="groupedTemplates.length > 0" class="template-groups">
                <div
                  v-for="group in groupedTemplates"
                  :key="group.category"
                  class="template-group-section"
                >
                  <div class="template-group-header">
                    <div class="template-group-meta">
                      <h3>{{ group.category }}</h3>
                      <span>{{ t('autoComments.groupTemplatesCount', { count: group.templates.length }) }}</span>
                    </div>
                    <div class="template-group-actions">
                      <Button
                        :label="isTemplateCategorySelected(group.category) ? t('autoComments.clearGroup') : t('autoComments.selectGroup')"
                        :severity="isTemplateCategorySelected(group.category) ? 'secondary' : 'info'"
                        size="small"
                        outlined
                        @click="isTemplateCategorySelected(group.category) ? clearTemplateCategory(group.category) : selectTemplateCategory(group.category)"
                      />
                    </div>
                  </div>

                  <div class="templates-grid">
                    <div
                      v-for="tmpl in group.templates"
                      :key="tmpl.id"
                      :class="['template-card', { selected: selectedTemplateIds.includes(tmpl.id) }]"
                      @click="toggleTemplate(tmpl.id)"
                    >
                      <div class="template-card-header">
                        <div class="template-checkbox">
                          <i :class="selectedTemplateIds.includes(tmpl.id) ? 'pi pi-check-circle' : 'pi pi-circle'"></i>
                        </div>
                        <div class="template-card-title">
                          <span class="template-name">{{ tmpl.name }}</span>
                          <Tag :value="tmpl.category" severity="secondary" />
                        </div>
                        <div class="template-card-actions">
                          <Button
                            icon="pi pi-pencil"
                            text
                            rounded
                            size="small"
                            class="template-edit-btn"
                            @click.stop="openEditTemplateDialog(tmpl)"
                          />
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
                      </div>
                      <p class="template-content">{{ tmpl.content }}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div v-else class="empty-templates">
                <i class="pi pi-file-edit"></i>
                <p>{{ taskStore.templates.length === 0 ? t('autoComments.noTemplates') : t('autoComments.noTemplatesMatch') }}</p>
                <span>{{ taskStore.templates.length === 0 ? t('autoComments.noTemplatesHint') : t('autoComments.noTemplatesMatchHint') }}</span>
              </div>
            </div>
          </div>

          <!-- Create Button -->
          <div class="create-action">
            <button
              class="launch-btn"
              :class="{ ready: channelInput.trim() && selectedTemplates.length > 0 && selectedAccountIds.length > 0, loading: isCreating }"
              :disabled="!channelInput.trim() || selectedTemplates.length === 0 || selectedAccountIds.length === 0 || isCreating"
              @click="createTask"
            >
              <span class="launch-btn-glow"></span>
              <span class="launch-btn-content">
                <i v-if="isCreating" class="pi pi-spin pi-spinner"></i>
                <i v-else class="pi pi-play"></i>
                <span>{{ t('autoComments.startTask') }}</span>
              </span>
              <span class="launch-btn-badges">
                <span :class="['badge', { ok: channelInput.trim() }]">
                  <i :class="channelInput.trim() ? 'pi pi-check' : 'pi pi-minus'"></i>
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
        :header="editingTemplateId == null ? t('autoComments.createTemplate') : t('autoComments.editTemplate')"
        :style="{ width: '550px' }"
        modal
        class="template-dialog"
        @hide="resetTemplateDialog"
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
              <i class="pi pi-folder"></i>
              {{ t('autoComments.templateGroup') }}
            </label>
            <InputText
              v-model="newTemplateCategory"
              :placeholder="t('autoComments.templateGroupPlaceholder')"
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
              :placeholder="spintaxPlaceholder"
              class="w-full"
              rows="5"
              autoResize
            />
            <div class="spintax-hint">
              <i class="pi pi-lightbulb"></i>
              <span>{{ spintaxHintText }}</span>
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
              @click="saveTemplate"
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

.invite-link-field {
  margin-top: 12px;
}

/* Templates */
.template-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.template-search-input {
  flex: 1;
}

.template-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.template-filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #d1d1d7;
  cursor: pointer;
  transition: all 0.2s ease;
}

.template-filter-chip strong {
  font-size: 11px;
  color: #8b8b95;
}

.template-filter-chip:hover {
  border-color: rgba(168, 85, 247, 0.35);
  background: rgba(168, 85, 247, 0.07);
}

.template-filter-chip.active {
  border-color: rgba(168, 85, 247, 0.45);
  background: rgba(168, 85, 247, 0.16);
  color: #f4ecff;
}

.template-import-panel {
  display: grid;
  gap: 12px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
}

.template-import-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-import-copy strong {
  font-size: 13px;
  color: #f4f4f5;
}

.template-import-copy span {
  font-size: 12px;
  color: #8b8b95;
}

.template-import-controls {
  display: grid;
  gap: 6px;
}

.template-import-dropzone {
  padding: 1.2rem;
}

.template-actions-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
}

.create-template-btn {
  flex-shrink: 0;
}

.template-selection-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-selection-counter {
  font-size: 12px;
  color: #8b8b95;
}

.template-groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.template-group-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
}

.template-group-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.template-group-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-group-meta h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #f4f4f5;
}

.template-group-meta span {
  font-size: 12px;
  color: #8b8b95;
}

.template-group-actions {
  display: flex;
  gap: 8px;
}

.templates-grid {
  display: grid;
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
  align-items: flex-start;
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

.template-card-title {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.template-name {
  font-size: 13px;
  font-weight: 600;
  color: #e4e4e7;
}

.template-card-actions {
  display: flex;
  gap: 2px;
  opacity: 1;
}

.template-delete-btn,
.template-edit-btn {
  opacity: 1;
}

.template-card:hover .template-card-actions,
.template-card:hover .template-delete-btn,
.template-card:hover .template-edit-btn {
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
