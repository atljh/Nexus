<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import { countryFlag } from '@/utils/formatters'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import Checkbox from 'primevue/checkbox'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import { useProxyStore } from '@/stores/useProxyStore'
import type { Proxy } from '@/types'

const { t, locale } = useI18n()

interface ProxyPreview {
  type: string
  host: string
  port: number
  username?: string
  password?: string
  status: 'pending' | 'checking' | 'working' | 'slow' | 'very_slow' | 'not_working' | 'timeout' | 'duplicate'
  ping_ms?: number | null
  geo?: string | null
  external_ip?: string | null
  selected: boolean
}

const toast = useToast()
const confirm = useConfirm()
const proxyStore = useProxyStore()
const proxies = computed(() => proxyStore.proxies)
const loading = computed(() => proxyStore.loading)
const showAddDialog = ref(false)
const showEditDialog = ref(false)
const checking = ref(false)
const selectedProxies = ref<Proxy[]>([])

// Filters
const statusFilter = ref<string | null>(null)
const typeFilter = ref<string | null>(null)
const searchQuery = ref('')

// Preview state
const proxyPreviews = ref<ProxyPreview[]>([])
const isCheckingPreviews = ref(false)
const checkProgress = ref(0)
const showPreview = ref(false)

const proxyTypes = [
  { label: 'SOCKS5', value: 'socks5' },
  { label: 'SOCKS4', value: 'socks4' },
  { label: 'HTTP', value: 'http' },
  { label: 'HTTPS', value: 'https' }
]

const statusOptions = computed(() => [
  { label: t('proxy.status.working'), value: 'working' },
  { label: t('proxy.status.slow'), value: 'slow' },
  { label: t('proxy.status.very_slow'), value: 'very_slow' },
  { label: t('proxy.status.not_working'), value: 'not_working' },
  { label: t('proxy.status.timeout'), value: 'timeout' },
  { label: t('proxy.status.unchecked'), value: 'unchecked' }
])

const typeFilterOptions = [
  { label: 'SOCKS5', value: 'socks5' },
  { label: 'SOCKS4', value: 'socks4' },
  { label: 'HTTP', value: 'http' },
  { label: 'HTTPS', value: 'https' }
]

const newProxy = ref({
  type: 'socks5',
  host: '',
  port: '',
  username: '',
  password: ''
})

const editProxy = ref<Proxy | null>(null)
const bulkProxies = ref('')
const inputMode = ref<'form' | 'string'>('string')
const proxyString = ref('')

// Edit dialog state
const editInputMode = ref<'form' | 'string'>('form')
const editProxyString = ref('')
const editCheckStatus = ref<'idle' | 'checking' | 'success' | 'error'>('idle')
const editCheckResult = ref<{ status: string; ping_ms?: number; geo?: string } | null>(null)

// Stats
const totalProxies = computed(() => proxies.value.length)
const workingProxies = computed(() => proxyStore.statusCounts.working)
const slowProxies = computed(() => proxyStore.statusCounts.slow + proxyStore.statusCounts.very_slow)
const notWorkingProxies = computed(() => proxyStore.statusCounts.not_working + proxyStore.statusCounts.timeout)
const uncheckedProxies = computed(() => proxyStore.statusCounts.unchecked)

// Filtered proxies
const filteredProxies = computed(() => {
  let result = proxies.value

  if (statusFilter.value) {
    result = result.filter(p => p.status === statusFilter.value)
  }

  if (typeFilter.value) {
    result = result.filter(p => p.type === typeFilter.value)
  }

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(p =>
      `${p.host}:${p.port}`.toLowerCase().includes(q) ||
      (p.external_ip && p.external_ip.toLowerCase().includes(q)) ||
      (p.geo && p.geo.toLowerCase().includes(q))
    )
  }

  return result
})

const hasSelection = computed(() => selectedProxies.value.length > 0)

// Computed
const workingPreviews = computed(() =>
  proxyPreviews.value.filter(p => ['working', 'slow', 'very_slow'].includes(p.status))
)

const selectedPreviews = computed(() =>
  proxyPreviews.value.filter(p => p.selected)
)

onMounted(() => {
  proxyStore.fetchProxies()
})

function getStatusSeverity(status: string): "success" | "danger" | "warn" | "secondary" {
  switch (status) {
    case 'working': return 'success'
    case 'slow': return 'warn'
    case 'very_slow': return 'warn'
    case 'not_working': return 'danger'
    case 'timeout': return 'danger'
    default: return 'secondary'
  }
}


function formatLastChecked(dateStr: string | null): string {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMin < 1) return t('common.time.justNow')
  if (diffMin < 60) return t('common.time.minutesShort', { count: diffMin })
  if (diffHours < 24) return t('common.time.hoursShort', { count: diffHours })
  if (diffDays < 7) return t('common.time.daysShort', { count: diffDays })
  return date.toLocaleDateString(locale.value === 'uk' ? 'uk-UA' : 'en-US', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

function setStatusFilter(val: string | null) {
  statusFilter.value = val
}

function parseProxyString(str: string): { type: 'socks5' | 'socks4' | 'http' | 'https'; host: string; port: number; username?: string; password?: string } | null {
  const trimmed = str.trim()
  if (!trimmed) return null

  let type: 'socks5' | 'socks4' | 'http' | 'https' = 'socks5'
  let host = ''
  let port = 0
  let username: string | undefined
  let password: string | undefined

  // Try URL format: type://[user:pass@]host:port
  const urlMatch = trimmed.match(/^(socks5|socks4|http|https):\/\/(?:([^:]+):([^@]+)@)?([^:]+):(\d+)$/i)
  if (urlMatch) {
    type = urlMatch[1].toLowerCase() as typeof type
    username = urlMatch[2] || undefined
    password = urlMatch[3] || undefined
    host = urlMatch[4]
    port = parseInt(urlMatch[5])
  } else {
    // Try format: [user:pass@]host:port
    const authMatch = trimmed.match(/^([^:]+):([^@]+)@([^:]+):(\d+)$/)
    if (authMatch) {
      username = authMatch[1]
      password = authMatch[2]
      host = authMatch[3]
      port = parseInt(authMatch[4])
    } else {
      // Try simple format: host:port or host:port:user:pass
      const parts = trimmed.split(':')
      if (parts.length < 2) return null

      host = parts[0]
      port = parseInt(parts[1])

      if (parts.length >= 4) {
        username = parts[2]
        password = parts.slice(3).join(':')
      }
    }
  }

  if (!host || !port || isNaN(port)) return null

  return { type, host, port, username, password }
}

async function checkProxy(proxy: Proxy) {
  try {
    const result = await proxyStore.checkProxy(proxy.id)

    const isWorking = ['working', 'slow', 'very_slow'].includes(result.status)
    toast.add({
      severity: isWorking ? 'success' : 'error',
      summary: isWorking ? t('proxy.messages.proxyValid') : t('proxy.messages.proxyInvalid'),
      detail: `${proxy.host}:${proxy.port}`,
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('proxy.messages.checkFailed'),
      detail: error.message || t('proxy.messages.checkFailed'),
      life: 3000
    })
  }
}

async function checkAllProxies() {
  checking.value = true
  toast.add({
    severity: 'info',
    summary: t('common.info'),
    detail: t('proxy.messages.checking'),
    life: 2000
  })

  try {
    const result = await proxyStore.checkAllProxies()

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('proxy.messages.checkComplete', { count: result.results.length }),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.checkFailed'),
      life: 3000
    })
  } finally {
    checking.value = false
  }
}

interface CheckPreviewResult {
  results: Array<{
    index: number
    type: string
    host: string
    port: number
    username?: string
    status: string
    ping_ms?: number
    external_ip?: string
    geo?: string
    error?: string
  }>
}

function isDuplicate(host: string, port: number): boolean {
  return proxies.value.some(p => p.host === host && p.port === port)
}

function getProxiesToCheck(): Array<{ type: string; host: string; port: number; username?: string; password?: string }> {
  const result: Array<{ type: string; host: string; port: number; username?: string; password?: string }> = []

  // Bulk import
  if (bulkProxies.value.trim()) {
    const lines = bulkProxies.value.trim().split('\n').filter(l => l.trim())
    for (const line of lines) {
      const parsed = parseProxyString(line)
      if (parsed) {
        result.push(parsed)
      }
    }
  }

  // String input mode
  if (inputMode.value === 'string' && proxyString.value.trim()) {
    const parsed = parseProxyString(proxyString.value)
    if (parsed) {
      result.push(parsed)
    }
  }

  // Form input mode
  if (inputMode.value === 'form' && newProxy.value.host && newProxy.value.port) {
    result.push({
      type: newProxy.value.type,
      host: newProxy.value.host,
      port: parseInt(newProxy.value.port),
      username: newProxy.value.username || undefined,
      password: newProxy.value.password || undefined
    })
  }

  return result
}

async function checkAndPreview() {
  const proxiesToCheck = getProxiesToCheck()

  if (proxiesToCheck.length === 0) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('proxy.messages.enterHostPort'),
      life: 3000
    })
    return
  }

  // Mark duplicates and prepare previews
  proxyPreviews.value = proxiesToCheck.map(p => ({
    ...p,
    status: isDuplicate(p.host, p.port) ? 'duplicate' : 'pending',
    selected: !isDuplicate(p.host, p.port)
  }))

  showPreview.value = true

  // Check non-duplicate proxies
  const toCheck = proxyPreviews.value
    .map((p, i) => ({ ...p, index: i }))
    .filter(p => p.status !== 'duplicate')

  if (toCheck.length === 0) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('proxy.messages.allDuplicates'),
      life: 3000
    })
    return
  }

  isCheckingPreviews.value = true
  checkProgress.value = 0

  // Mark as checking
  for (const p of toCheck) {
    proxyPreviews.value[p.index].status = 'checking'
  }

  try {
    const response = await window.api.post('/api/proxy/check-preview', {
      proxies: toCheck.map(p => ({
        type: p.type,
        host: p.host,
        port: p.port,
        username: p.username,
        password: p.password
      })),
      lookup_geo: true
    }) as CheckPreviewResult

    // Update previews with results
    for (let i = 0; i < response.results.length; i++) {
      const result = response.results[i]
      const originalIndex = toCheck[i].index
      proxyPreviews.value[originalIndex].status = result.status as ProxyPreview['status']
      proxyPreviews.value[originalIndex].ping_ms = result.ping_ms
      proxyPreviews.value[originalIndex].geo = result.geo
      proxyPreviews.value[originalIndex].external_ip = result.external_ip

      // Auto-select only working proxies
      proxyPreviews.value[originalIndex].selected = ['working', 'slow', 'very_slow'].includes(result.status)
    }

    checkProgress.value = 100
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.checkFailed'),
      life: 3000
    })

    // Mark all as failed
    for (const p of toCheck) {
      if (proxyPreviews.value[p.index]) {
        proxyPreviews.value[p.index].status = 'not_working'
      }
    }
  } finally {
    isCheckingPreviews.value = false
  }
}

async function addSelectedProxies() {
  const selected = proxyPreviews.value.filter(p => p.selected && p.status !== 'duplicate')

  if (selected.length === 0) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('proxy.messages.selectProxies'),
      life: 3000
    })
    return
  }

  try {
    let addedCount = 0

    for (const proxy of selected) {
      await proxyStore.createProxy({
        type: proxy.type as Proxy['type'],
        host: proxy.host,
        port: proxy.port,
        username: proxy.username || undefined,
        password: proxy.password || undefined,
      })
      addedCount++
    }

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('proxy.messages.addedCount', { count: addedCount }),
      life: 3000
    })

    resetForm()
    showAddDialog.value = false
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.addFailed'),
      life: 3000
    })
  }
}

function toggleSelectAll(checked: boolean) {
  for (const p of proxyPreviews.value) {
    if (p.status !== 'duplicate') {
      p.selected = checked
    }
  }
}

function selectWorkingOnly() {
  for (const p of proxyPreviews.value) {
    p.selected = ['working', 'slow', 'very_slow'].includes(p.status)
  }
}

function openEditDialog(proxy: Proxy) {
  editProxy.value = { ...proxy }
  editInputMode.value = 'form'
  editProxyString.value = ''
  editCheckStatus.value = 'idle'
  editCheckResult.value = null
  showEditDialog.value = true
}

function resetEditDialog() {
  editProxy.value = null
  editInputMode.value = 'form'
  editProxyString.value = ''
  editCheckStatus.value = 'idle'
  editCheckResult.value = null
}

function applyEditProxyString() {
  if (!editProxy.value || !editProxyString.value.trim()) return

  const parsed = parseProxyString(editProxyString.value)
  if (!parsed) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('proxy.messages.invalidProxyFormat'),
      life: 3000
    })
    return
  }

  editProxy.value.type = parsed.type
  editProxy.value.host = parsed.host
  editProxy.value.port = parsed.port
  editProxy.value.username = parsed.username || null
  editProxy.value.password = parsed.password || undefined

  editCheckStatus.value = 'idle'
  editCheckResult.value = null

  toast.add({
    severity: 'info',
    summary: t('common.info'),
    detail: t('proxy.messages.proxyParsed'),
    life: 2000
  })
}

async function checkEditProxy() {
  if (!editProxy.value) return

  editCheckStatus.value = 'checking'
  editCheckResult.value = null

  try {
    const response = await window.api.post('/api/proxy/check-preview', {
      proxies: [{
        type: editProxy.value.type,
        host: editProxy.value.host,
        port: editProxy.value.port,
        username: editProxy.value.username,
        password: editProxy.value.password
      }],
      lookup_geo: true
    }) as CheckPreviewResult

    if (response.results.length > 0) {
      const result = response.results[0]
      editCheckResult.value = {
        status: result.status,
        ping_ms: result.ping_ms || undefined,
        geo: result.geo || undefined
      }
      editCheckStatus.value = ['working', 'slow', 'very_slow'].includes(result.status) ? 'success' : 'error'
    }
  } catch (error: any) {
    editCheckStatus.value = 'error'
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.checkFailed'),
      life: 3000
    })
  }
}

async function saveEditProxy() {
  if (!editProxy.value) return

  try {
    await proxyStore.updateProxy(editProxy.value.id, {
      type: editProxy.value.type as Proxy['type'],
      host: editProxy.value.host,
      port: editProxy.value.port,
      username: editProxy.value.username || undefined,
      password: editProxy.value.password || undefined
    })

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('proxy.messages.updated'),
      life: 3000
    })

    showEditDialog.value = false
    resetEditDialog()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.updateFailed'),
      life: 3000
    })
  }
}

function deleteProxy(proxy: Proxy) {
  confirm.require({
    message: t('proxy.deleteConfirm', { host: proxy.host, port: proxy.port }),
    header: t('common.confirm'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      try {
        await proxyStore.deleteProxy(proxy.id)
        toast.add({
          severity: 'success',
          summary: t('common.success'),
          detail: t('proxy.messages.deleted'),
          life: 3000
        })
      } catch (error: any) {
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.message || t('proxy.messages.deleteFailed'),
          life: 3000
        })
      }
    }
  })
}

function deleteSelectedProxies() {
  if (selectedProxies.value.length === 0) return

  confirm.require({
    message: t('proxy.bulkDeleteConfirm', { count: selectedProxies.value.length }),
    header: t('common.confirm'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      try {
        for (const proxy of selectedProxies.value) {
          await proxyStore.deleteProxy(proxy.id)
        }
        toast.add({
          severity: 'success',
          summary: t('common.success'),
          detail: t('proxy.messages.bulkDeleted', { count: selectedProxies.value.length }),
          life: 3000
        })
        selectedProxies.value = []
      } catch (error: any) {
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.message || t('proxy.messages.deleteFailed'),
          life: 3000
        })
      }
    }
  })
}

function resetForm() {
  newProxy.value = {
    type: 'socks5',
    host: '',
    port: '',
    username: '',
    password: ''
  }
  bulkProxies.value = ''
  proxyString.value = ''
  inputMode.value = 'string'
  proxyPreviews.value = []
  showPreview.value = false
  isCheckingPreviews.value = false
  checkProgress.value = 0
}

function getPreviewStatusSeverity(status: string): "success" | "danger" | "warn" | "secondary" | "info" {
  switch (status) {
    case 'working': return 'success'
    case 'slow': return 'warn'
    case 'very_slow': return 'warn'
    case 'not_working': return 'danger'
    case 'timeout': return 'danger'
    case 'duplicate': return 'secondary'
    case 'checking': return 'info'
    case 'pending': return 'secondary'
    default: return 'secondary'
  }
}
</script>

<template>
  <MainLayout>
    <Toast />
    <ConfirmDialog />
    <div class="proxy-page">
      <!-- Stats Cards -->
      <div class="stats-row">
        <div class="stat-card" :class="{ active: !statusFilter }" @click="setStatusFilter(null)">
          <div class="stat-value accent">{{ totalProxies }}</div>
          <div class="stat-label">{{ t('proxy.allProxies') }}</div>
        </div>
        <div class="stat-card" :class="{ active: statusFilter === 'working' }" @click="setStatusFilter('working')">
          <div class="stat-value">{{ workingProxies }}</div>
          <div class="stat-label">{{ t('proxy.working') }}</div>
        </div>
        <div class="stat-card" :class="{ active: statusFilter === 'slow' }" @click="setStatusFilter('slow')">
          <div class="stat-value">{{ slowProxies }}</div>
          <div class="stat-label">{{ t('proxy.slow') }}</div>
        </div>
        <div class="stat-card" :class="{ active: statusFilter === 'not_working' }" @click="setStatusFilter('not_working')">
          <div class="stat-value">{{ notWorkingProxies }}</div>
          <div class="stat-label">{{ t('proxy.notWorking') }}</div>
        </div>
        <div class="stat-card" :class="{ active: statusFilter === 'unchecked' }" @click="setStatusFilter('unchecked')">
          <div class="stat-value">{{ uncheckedProxies }}</div>
          <div class="stat-label">{{ t('proxy.uncheckedLabel') }}</div>
        </div>
      </div>

      <!-- Toolbar -->
      <div class="toolbar-row">
        <div class="toolbar-actions">
          <button class="toolbar-btn" @click="showAddDialog = true" v-tooltip.top="t('proxy.addProxy')">
            <i class="pi pi-plus"></i>
          </button>
          <button class="toolbar-btn" :disabled="proxies.length === 0" @click="checkAllProxies" v-tooltip.top="t('proxy.checkAll')">
            <i class="pi pi-refresh"></i>
          </button>
          <button class="toolbar-btn" :disabled="!hasSelection" @click="deleteSelectedProxies" v-tooltip.top="t('proxy.deleteSelected')">
            <i class="pi pi-trash"></i>
          </button>
        </div>
        <span class="shown-count">
          {{ t('proxy.shown', { filtered: filteredProxies.length, total: proxies.length }) }}
        </span>
      </div>

      <ProgressBar v-if="checking" mode="indeterminate" style="height: 4px" class="check-progress" />

      <!-- Filters + Search -->
      <div class="filters-row">
        <div class="filter-chips">
          <Select
            :model-value="statusFilter"
            :options="statusOptions"
            optionLabel="label"
            optionValue="value"
            :placeholder="t('common.status')"
            @update:model-value="setStatusFilter"
            class="filter-chip"
            showClear
          />
          <Select
            :model-value="typeFilter"
            :options="typeFilterOptions"
            optionLabel="label"
            optionValue="value"
            :placeholder="t('common.type')"
            @update:model-value="(val: string | null) => typeFilter = val"
            class="filter-chip"
            showClear
          />
        </div>
        <div class="search-box">
          <div class="search-wrap">
            <i class="pi pi-search search-icon"></i>
            <InputText
              v-model="searchQuery"
              :placeholder="t('proxy.searchPlaceholder')"
              class="search-input"
            />
          </div>
        </div>
      </div>

      <!-- Proxy Table -->
      <div class="table-card">
        <DataTable
          v-model:selection="selectedProxies"
          :value="filteredProxies"
          :loading="loading"
          paginator
          :rows="50"
          dataKey="id"
          class="custom-table"
          scrollable
          scrollHeight="flex"
        >
          <template #empty>
            <div class="empty-state">
              <div class="empty-icon">
                <i class="pi pi-globe"></i>
              </div>
              <p class="empty-text">{{ t('proxy.noProxies') }}</p>
              <Button
                :label="t('proxy.addProxy')"
                icon="pi pi-plus"
                @click="showAddDialog = true"
              />
            </div>
          </template>

          <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>

          <Column header="#" style="width: 50px">
            <template #body="{ index }">
              <span class="row-index">{{ index + 1 }}</span>
            </template>
          </Column>

          <Column :header="t('proxy.proxyColumn')" sortable field="host" style="min-width: 200px">
            <template #body="{ data }">
              <div class="proxy-cell">
                <span class="proxy-address">{{ data.host }}:{{ data.port }}</span>
                <span class="proxy-type-badge">{{ data.type.toUpperCase() }}</span>
              </div>
            </template>
          </Column>

          <Column :header="t('proxy.geoColumn')" style="width: 90px" sortable field="geo">
            <template #body="{ data }">
              <div v-if="data.geo" class="geo-cell">
                <span class="geo-flag">{{ countryFlag(data.geo) }}</span>
                <span class="geo-code">{{ data.geo?.toUpperCase() }}</span>
              </div>
              <span v-else class="no-data">—</span>
            </template>
          </Column>

          <Column field="status" :header="t('common.status')" sortable style="min-width: 120px">
            <template #body="{ data }">
              <div v-if="data.status === 'checking'" class="checking-status">
                <i class="pi pi-spin pi-spinner"></i>
                <span>{{ t('proxy.checking') }}</span>
              </div>
              <Tag v-else :value="t(`proxy.status.${data.status}`)" :severity="getStatusSeverity(data.status)" class="status-pill" />
            </template>
          </Column>

          <Column header="Ping" style="width: 80px" sortable field="ping_ms">
            <template #body="{ data }">
              <span v-if="data.ping_ms" class="ping-text" :class="{ 'ping-good': data.ping_ms < 500, 'ping-slow': data.ping_ms >= 500 && data.ping_ms < 2000, 'ping-bad': data.ping_ms >= 2000 }">{{ data.ping_ms }}ms</span>
              <span v-else class="no-data">—</span>
            </template>
          </Column>

          <Column :header="t('proxy.accountsShort')" style="width: 70px" sortable field="accounts_count">
            <template #body="{ data }">
              <span class="accounts-count">{{ data.accounts_count }}</span>
            </template>
          </Column>

          <Column :header="t('proxy.externalIp')" style="min-width: 130px">
            <template #body="{ data }">
              <span v-if="data.external_ip" class="ip-text">{{ data.external_ip }}</span>
              <span v-else class="no-data">—</span>
            </template>
          </Column>

          <Column :header="t('proxy.lastCheckColumn')" style="min-width: 120px" sortable field="last_checked_at">
            <template #body="{ data }">
              <span class="last-check-text">{{ formatLastChecked(data.last_checked_at) }}</span>
            </template>
          </Column>

          <Column :header="t('proxy.actionsColumn')" style="width: 120px">
            <template #body="{ data }">
              <div class="actions-cell">
                <button class="action-icon" @click="checkProxy(data)" v-tooltip.top="t('common.check')">
                  <i class="pi pi-refresh"></i>
                </button>
                <button class="action-icon" @click="openEditDialog(data)" v-tooltip.top="t('common.edit')">
                  <i class="pi pi-pencil"></i>
                </button>
                <button class="action-icon delete" @click="deleteProxy(data)" v-tooltip.top="t('common.delete')">
                  <i class="pi pi-trash"></i>
                </button>
              </div>
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Add Proxy Dialog -->
      <Dialog
        v-model:visible="showAddDialog"
        :header="t('proxy.addDialog.title')"
        modal
        :style="{ width: showPreview ? '720px' : '520px' }"
        class="custom-dialog"
        @hide="resetForm"
      >
        <div class="dialog-content">
          <!-- Input Section (hidden when showing preview) -->
          <template v-if="!showPreview">
            <!-- Mode Toggle -->
            <div class="mode-toggle">
              <Button
                :label="t('proxy.addDialog.stringMode')"
                :severity="inputMode === 'string' ? 'primary' : 'secondary'"
                :outlined="inputMode !== 'string'"
                size="small"
                @click="inputMode = 'string'"
              />
              <Button
                :label="t('proxy.addDialog.formMode')"
                :severity="inputMode === 'form' ? 'primary' : 'secondary'"
                :outlined="inputMode !== 'form'"
                size="small"
                @click="inputMode = 'form'"
              />
            </div>

            <!-- String Input Mode -->
            <div v-if="inputMode === 'string'" class="string-mode">
              <div class="form-field">
                <label class="form-label">{{ t('proxy.addDialog.proxyString') }}</label>
                <InputText
                  v-model="proxyString"
                  :placeholder="t('proxy.addDialog.proxyStringPlaceholder')"
                  class="w-full font-mono"
                  @keyup.enter="checkAndPreview"
                />
                <small class="format-hint">{{ t('proxy.addDialog.proxyStringFormats') }}</small>
              </div>
            </div>

            <!-- Form Input Mode -->
            <div v-else class="form-mode">
              <div class="form-field">
                <label class="form-label">{{ t('proxy.addDialog.type') }}</label>
                <Select
                  v-model="newProxy.type"
                  :options="proxyTypes"
                  optionLabel="label"
                  optionValue="value"
                  class="w-full"
                />
              </div>

              <div class="form-row">
                <div class="form-field flex-2">
                  <label class="form-label">{{ t('proxy.addDialog.host') }}</label>
                  <InputText v-model="newProxy.host" placeholder="127.0.0.1" class="w-full" />
                </div>
                <div class="form-field flex-1">
                  <label class="form-label">{{ t('proxy.addDialog.port') }}</label>
                  <InputText v-model="newProxy.port" placeholder="1080" class="w-full" />
                </div>
              </div>

              <div class="form-row">
                <div class="form-field flex-1">
                  <label class="form-label">{{ t('proxy.addDialog.username') }} ({{ t('common.optional') }})</label>
                  <InputText v-model="newProxy.username" class="w-full" />
                </div>
                <div class="form-field flex-1">
                  <label class="form-label">{{ t('proxy.addDialog.password') }} ({{ t('common.optional') }})</label>
                  <InputText v-model="newProxy.password" type="password" class="w-full" />
                </div>
              </div>
            </div>

            <div class="divider"></div>

            <div class="form-field">
              <label class="form-label">{{ t('proxy.addDialog.bulkImport') }}</label>
              <p class="hint-text">{{ t('proxy.addDialog.bulkHint') }}</p>
              <Textarea
                v-model="bulkProxies"
                :placeholder="t('proxy.addDialog.bulkPlaceholder')"
                rows="4"
                class="w-full font-mono"
              />
            </div>

            <div class="dialog-actions">
              <Button :label="t('common.cancel')" severity="secondary" @click="showAddDialog = false" />
              <Button
                :label="t('proxy.addDialog.checkAndAdd')"
                icon="pi pi-check-circle"
                @click="checkAndPreview"
              />
            </div>
          </template>

          <!-- Preview Section -->
          <template v-else>
            <div class="preview-header">
              <h3>{{ t('proxy.addDialog.checkResults') }}</h3>
              <div class="preview-stats">
                <Tag :value="`${workingPreviews.length} ${t('proxy.addDialog.working')}`" severity="success" />
                <Tag :value="`${selectedPreviews.length} ${t('proxy.addDialog.selected')}`" severity="info" />
              </div>
            </div>

            <ProgressBar v-if="isCheckingPreviews" mode="indeterminate" style="height: 4px" class="mb-3" />

            <div class="preview-actions">
              <Button
                :label="t('proxy.addDialog.selectWorking')"
                size="small"
                severity="secondary"
                @click="selectWorkingOnly"
              />
              <Button
                :label="t('proxy.addDialog.selectAll')"
                size="small"
                severity="secondary"
                @click="toggleSelectAll(true)"
              />
              <Button
                :label="t('proxy.addDialog.deselectAll')"
                size="small"
                severity="secondary"
                @click="toggleSelectAll(false)"
              />
            </div>

            <div class="preview-list">
              <div
                v-for="(preview, index) in proxyPreviews"
                :key="index"
                class="preview-item"
                :class="{ 'preview-item-disabled': preview.status === 'duplicate' }"
              >
                <Checkbox
                  v-model="preview.selected"
                  :binary="true"
                  :disabled="preview.status === 'duplicate'"
                />
                <div class="preview-info">
                  <span class="preview-address">{{ preview.host }}:{{ preview.port }}</span>
                  <Tag :value="preview.type.toUpperCase()" severity="secondary" class="preview-type" />
                </div>
                <div class="preview-status">
                  <Tag
                    :value="t(`proxy.status.${preview.status}`)"
                    :severity="getPreviewStatusSeverity(preview.status)"
                  />
                  <span v-if="preview.ping_ms" class="preview-ping">{{ preview.ping_ms }}ms</span>
                  <span v-if="preview.geo" class="preview-geo">{{ preview.geo }}</span>
                </div>
              </div>
            </div>

            <div class="dialog-actions">
              <Button :label="t('common.back')" severity="secondary" icon="pi pi-arrow-left" @click="showPreview = false" />
              <Button
                :label="t('proxy.addDialog.addSelected', { count: selectedPreviews.length })"
                icon="pi pi-plus"
                :disabled="selectedPreviews.length === 0"
                @click="addSelectedProxies"
              />
            </div>
          </template>
        </div>
      </Dialog>

      <!-- Edit Proxy Dialog -->
      <Dialog
        v-model:visible="showEditDialog"
        :header="t('proxy.editDialog.title')"
        modal
        :style="{ width: '520px' }"
        class="custom-dialog"
        @hide="resetEditDialog"
      >
        <div v-if="editProxy" class="dialog-content">
          <!-- Mode Toggle -->
          <div class="mode-toggle">
            <Button
              :label="t('proxy.addDialog.formMode')"
              :severity="editInputMode === 'form' ? 'primary' : 'secondary'"
              :outlined="editInputMode !== 'form'"
              size="small"
              @click="editInputMode = 'form'"
            />
            <Button
              :label="t('proxy.addDialog.stringMode')"
              :severity="editInputMode === 'string' ? 'primary' : 'secondary'"
              :outlined="editInputMode !== 'string'"
              size="small"
              @click="editInputMode = 'string'"
            />
          </div>

          <!-- String Input Mode -->
          <div v-if="editInputMode === 'string'" class="string-mode">
            <div class="form-field">
              <label class="form-label">{{ t('proxy.addDialog.proxyString') }}</label>
              <div class="string-input-row">
                <InputText
                  v-model="editProxyString"
                  :placeholder="t('proxy.addDialog.proxyStringPlaceholder')"
                  class="flex-1 font-mono"
                  @keyup.enter="applyEditProxyString"
                />
                <Button
                  icon="pi pi-check"
                  severity="secondary"
                  v-tooltip.top="t('proxy.editDialog.applyString')"
                  @click="applyEditProxyString"
                />
              </div>
              <small class="format-hint">{{ t('proxy.addDialog.proxyStringFormats') }}</small>
            </div>
          </div>

          <!-- Form Input Mode -->
          <div class="form-mode">
            <div class="form-field">
              <label class="form-label">{{ t('proxy.addDialog.type') }}</label>
              <Select
                v-model="editProxy.type"
                :options="proxyTypes"
                optionLabel="label"
                optionValue="value"
                class="w-full"
              />
            </div>

            <div class="form-row">
              <div class="form-field flex-2">
                <label class="form-label">{{ t('proxy.addDialog.host') }}</label>
                <InputText v-model="editProxy.host" class="w-full" />
              </div>
              <div class="form-field flex-1">
                <label class="form-label">{{ t('proxy.addDialog.port') }}</label>
                <InputText :modelValue="String(editProxy.port)" @update:modelValue="editProxy.port = Number($event)" class="w-full" />
              </div>
            </div>

            <div class="form-row">
              <div class="form-field flex-1">
                <label class="form-label">{{ t('proxy.addDialog.username') }}</label>
                <InputText v-model="editProxy.username" class="w-full" />
              </div>
              <div class="form-field flex-1">
                <label class="form-label">{{ t('proxy.addDialog.password') }}</label>
                <InputText v-model="editProxy.password" type="password" class="w-full" />
              </div>
            </div>
          </div>

          <!-- Check Result -->
          <div v-if="editCheckResult" class="edit-check-result">
            <div class="check-result-content">
              <Tag
                :value="t(`proxy.status.${editCheckResult.status}`)"
                :severity="getPreviewStatusSeverity(editCheckResult.status)"
              />
              <span v-if="editCheckResult.ping_ms" class="check-ping">{{ editCheckResult.ping_ms }}ms</span>
              <span v-if="editCheckResult.geo" class="check-geo">{{ editCheckResult.geo }}</span>
            </div>
          </div>

          <div class="dialog-actions">
            <Button :label="t('common.cancel')" severity="secondary" @click="showEditDialog = false" />
            <Button
              :label="t('common.check')"
              icon="pi pi-refresh"
              severity="secondary"
              :loading="editCheckStatus === 'checking'"
              @click="checkEditProxy"
            />
            <Button :label="t('common.save')" icon="pi pi-check" @click="saveEditProxy" />
          </div>
        </div>
      </Dialog>
    </div>
  </MainLayout>
</template>

<style scoped>
.proxy-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 1400px;
}

/* Stats Row */
.stats-row {
  display: flex;
  gap: 8px;
}

.stat-card {
  flex: 1;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.stat-card:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.1);
}

.stat-card.active {
  border-color: rgba(168, 85, 247, 0.4);
  background: rgba(168, 85, 247, 0.08);
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #e5e7eb;
  line-height: 1.2;
}

.stat-value.accent {
  color: #a855f7;
}

.stat-label {
  font-size: 11px;
  color: #8b8f9a;
  font-weight: 500;
  margin-top: 2px;
}

/* Toolbar */
.toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 10px;
}

.toolbar-actions {
  display: flex;
  gap: 4px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.13);
  background: rgba(255, 255, 255, 0.04);
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 14px;
}

.toolbar-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.13);
  color: #e5e7eb;
  border-color: rgba(255, 255, 255, 0.15);
}

.toolbar-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.shown-count {
  font-size: 12px;
  color: #8b8f9a;
}

.check-progress {
  border-radius: 4px;
  overflow: hidden;
}

/* Filters */
.filters-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-chips {
  display: flex;
  gap: 8px;
  flex: 1;
}

.filter-chip {
  min-width: 140px;
}

:deep(.filter-chip .p-dropdown) {
  border-radius: 20px;
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.06);
  font-size: 13px;
  height: 34px;
}

.search-box {
  flex-shrink: 0;
}

.search-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 12px;
  color: #8b8f9a;
  font-size: 13px;
  pointer-events: none;
}

.search-input {
  padding-left: 34px;
  width: 240px;
  height: 34px;
  font-size: 13px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.06);
}

/* Table */
.table-card {
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 12px;
  padding: 0;
  overflow: hidden;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 24px;
}

.empty-icon {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.1) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.empty-icon i {
  font-size: 32px;
  color: #3b82f6;
}

.empty-text {
  color: #8b8f9a;
  margin-bottom: 20px;
  font-size: 15px;
}

.row-index {
  font-size: 12px;
  color: #8b8f9a;
}

.proxy-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.proxy-address {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px;
  color: #e5e7eb;
}

.proxy-type-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(168, 85, 247, 0.12);
  color: #a855f7;
  letter-spacing: 0.3px;
}

.geo-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}

.geo-flag {
  font-size: 16px;
  line-height: 1;
}

.geo-code {
  font-size: 11px;
  color: #9ca3af;
  font-weight: 600;
}

.no-data {
  color: #4b5563;
}

.checking-status {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #60a5fa;
  font-size: 13px;
}

:deep(.status-pill) {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 20px;
}

.ping-text {
  font-size: 12px;
  font-weight: 500;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.ping-good {
  color: #10b981;
}

.ping-slow {
  color: #f59e0b;
}

.ping-bad {
  color: #ef4444;
}

.accounts-count {
  color: #9ca3af;
  font-size: 13px;
}

.ip-text {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  color: #9ca3af;
}

.last-check-text {
  font-size: 12px;
  color: #8b8f9a;
}

.actions-cell {
  display: flex;
  gap: 2px;
}

.action-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #8b8f9a;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 13px;
}

.action-icon:hover {
  background: rgba(255, 255, 255, 0.10);
  color: #e5e7eb;
}

.action-icon.delete:hover {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

/* DataTable overrides */
:deep(.custom-table .p-datatable) {
  background: transparent;
}

:deep(.custom-table .p-datatable-thead > tr > th) {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.10);
  color: #8b8f9a;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 10px 12px;
}

:deep(.custom-table .p-datatable-tbody > tr) {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.04);
  transition: all 0.15s;
}

:deep(.custom-table .p-datatable-tbody > tr:hover) {
  background: rgba(255, 255, 255, 0.06);
}

:deep(.custom-table .p-datatable-tbody > tr > td) {
  border-color: rgba(255, 255, 255, 0.04);
  padding: 10px 12px;
}

:deep(.custom-table .p-datatable-tbody > tr.p-highlight) {
  background: rgba(168, 85, 247, 0.08);
}

:deep(.custom-table .p-datatable-tbody > tr.p-highlight > td) {
  border-color: rgba(168, 85, 247, 0.1);
}

/* Dialog styles */
:deep(.custom-dialog .p-dialog-header) {
  background: #161616;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
}

:deep(.custom-dialog .p-dialog-content) {
  background: #161616;
  padding: 24px;
}

.dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 13px;
  color: #9ca3af;
  font-weight: 500;
}

.form-row {
  display: flex;
  gap: 12px;
}

.flex-1 {
  flex: 1;
}

.flex-2 {
  flex: 2;
}

.divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.13);
  margin: 8px 0;
}

.hint-text {
  font-size: 12px;
  color: #8b8f9a;
  margin-bottom: 8px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

.mode-toggle {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.mode-toggle :deep(.p-button) {
  flex: 1;
}

.string-mode,
.form-mode {
  margin-bottom: 8px;
}

.format-hint {
  display: block;
  color: #8b8f9a;
  font-size: 11px;
  margin-top: 6px;
}

/* Preview styles */
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.preview-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #f3f4f6;
  margin: 0;
}

.preview-stats {
  display: flex;
  gap: 8px;
}

.preview-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.preview-list {
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 8px;
  margin-bottom: 16px;
}

.preview-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  transition: background 0.2s;
}

.preview-item:last-child {
  border-bottom: none;
}

.preview-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.preview-item-disabled {
  opacity: 0.5;
}

.preview-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.preview-address {
  font-family: monospace;
  font-size: 13px;
  color: #e5e7eb;
}

.preview-type {
  font-size: 9px;
}

.preview-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-ping {
  font-size: 12px;
  color: #9ca3af;
}

.preview-geo {
  font-size: 12px;
  color: #8b8f9a;
  font-weight: 500;
}

/* Edit dialog styles */
.string-input-row {
  display: flex;
  gap: 8px;
}

.edit-check-result {
  padding: 12px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  margin-top: 12px;
}

.check-result-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.check-ping {
  font-size: 13px;
  color: #9ca3af;
}

.check-geo {
  font-size: 13px;
  color: #8b8f9a;
  font-weight: 500;
}
</style>
