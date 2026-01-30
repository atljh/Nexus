<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import Textarea from 'primevue/textarea'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import Checkbox from 'primevue/checkbox'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'

const { t } = useI18n()

interface Proxy {
  id: number
  host: string
  port: number
  type: string
  username: string | null
  password?: string | null
  status: 'unchecked' | 'working' | 'slow' | 'very_slow' | 'not_working' | 'timeout'
  ping_ms?: number | null
  geo?: string | null
  external_ip?: string | null
  accounts_count: number
  last_checked_at: string | null
}

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
const proxies = ref<Proxy[]>([])
const showAddDialog = ref(false)
const showEditDialog = ref(false)
const loading = ref(false)
const checking = ref(false)
const selectedProxies = ref<Proxy[]>([])

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

// Computed
const workingPreviews = computed(() =>
  proxyPreviews.value.filter(p => ['working', 'slow', 'very_slow'].includes(p.status))
)

const selectedPreviews = computed(() =>
  proxyPreviews.value.filter(p => p.selected)
)

onMounted(() => {
  loadProxies()
})

interface ProxiesResponse { data: Proxy[] }

async function loadProxies() {
  loading.value = true
  try {
    const response = await window.api.get('/api/proxy') as ProxiesResponse
    proxies.value = response.data || []
  } catch (error) {
    console.error('Failed to load proxies:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('proxy.messages.loadError'),
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

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

interface CheckResult { status: string; valid?: boolean }
interface CheckAllResult { checked: number }

async function checkProxy(proxy: Proxy) {
  try {
    const response = await window.api.post(`/api/proxy/${proxy.id}/check`, {}) as CheckResult

    toast.add({
      severity: response.status === 'valid' ? 'success' : 'error',
      summary: response.status === 'valid' ? t('proxy.messages.proxyValid') : t('proxy.messages.proxyInvalid'),
      detail: `${proxy.host}:${proxy.port}`,
      life: 3000
    })

    loadProxies()
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
    const response = await window.api.post('/api/proxy/check-all', {}) as CheckAllResult

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('proxy.messages.checkComplete', { count: response.checked }),
      life: 3000
    })

    loadProxies()
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
      proxyPreviews.value[p.index].status = 'not_working'
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
      await window.api.post('/api/proxy', {
        type: proxy.type,
        host: proxy.host,
        port: proxy.port,
        username: proxy.username || null,
        password: proxy.password || null
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
    loadProxies()
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
    await window.api.put(`/api/proxy/${editProxy.value.id}`, {
      type: editProxy.value.type,
      host: editProxy.value.host,
      port: editProxy.value.port,
      username: editProxy.value.username || null,
      password: editProxy.value.password || null
    })

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('proxy.messages.updated'),
      life: 3000
    })

    showEditDialog.value = false
    resetEditDialog()
    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.updateFailed'),
      life: 3000
    })
  }
}

async function deleteProxy(proxy: Proxy) {
  if (!confirm(t('proxy.deleteConfirm', { host: proxy.host, port: proxy.port }))) {
    return
  }

  try {
    await window.api.delete(`/api/proxy/${proxy.id}`)

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('proxy.messages.deleted'),
      life: 3000
    })

    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.deleteFailed'),
      life: 3000
    })
  }
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

function formatDate(dateStr: string | null): string {
  if (!dateStr) return t('common.never')
  return new Date(dateStr).toLocaleString()
}
</script>

<template>
  <MainLayout>
    <Toast />
    <div class="proxy-page">
      <div class="page-header">
        <h1 class="page-title">{{ t('proxy.title') }}</h1>
        <div class="header-actions">
          <Button
            :label="t('proxy.addProxy')"
            icon="pi pi-plus"
            @click="showAddDialog = true"
          />
          <Button
            :label="t('proxy.checkAll')"
            icon="pi pi-refresh"
            severity="secondary"
            :loading="checking"
            @click="checkAllProxies"
            :disabled="proxies.length === 0"
          />
        </div>
      </div>

      <ProgressBar v-if="checking" mode="indeterminate" style="height: 4px" class="mb-4" />

      <!-- Proxy table -->
      <div class="table-card">
        <DataTable
          v-model:selection="selectedProxies"
          :value="proxies"
          :loading="loading"
          paginator
          :rows="20"
          dataKey="id"
          class="custom-table"
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

          <Column field="id" header="ID" sortable style="width: 80px" />
          <Column :header="t('proxy.title')" sortable>
            <template #body="{ data }">
              <div class="proxy-cell">
                <span class="proxy-address">{{ data.host }}:{{ data.port }}</span>
                <Tag :value="data.type.toUpperCase()" severity="secondary" class="proxy-type" />
              </div>
            </template>
          </Column>
          <Column :header="t('proxy.auth')" style="width: 100px">
            <template #body="{ data }">
              <Tag
                :value="data.username ? t('common.yes') : t('common.no')"
                :severity="data.username ? 'success' : 'secondary'"
              />
            </template>
          </Column>
          <Column field="status" :header="t('common.status')" sortable style="width: 120px">
            <template #body="{ data }">
              <Tag :value="t(`proxy.status.${data.status}`)" :severity="getStatusSeverity(data.status)" />
            </template>
          </Column>
          <Column :header="t('proxy.accounts')" style="width: 100px">
            <template #body="{ data }">
              <span class="accounts-count">{{ data.accounts_count }}</span>
            </template>
          </Column>
          <Column :header="t('proxy.lastCheck')" style="width: 180px">
            <template #body="{ data }">
              <span class="last-check">{{ formatDate(data.last_checked_at) }}</span>
            </template>
          </Column>
          <Column :header="t('common.actions')" style="width: 150px">
            <template #body="{ data }">
              <div class="actions-cell">
                <Button
                  icon="pi pi-refresh"
                  severity="secondary"
                  text
                  rounded
                  v-tooltip.top="t('common.check')"
                  @click="checkProxy(data)"
                />
                <Button
                  icon="pi pi-pencil"
                  severity="secondary"
                  text
                  rounded
                  v-tooltip.top="t('common.edit')"
                  @click="openEditDialog(data)"
                />
                <Button
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  v-tooltip.top="t('common.delete')"
                  @click="deleteProxy(data)"
                />
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
                <Dropdown
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
              <Dropdown
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
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #f3f4f6;
  letter-spacing: -0.5px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.table-card {
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 16px;
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
  color: #6b7280;
  margin-bottom: 20px;
  font-size: 15px;
}

.proxy-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.proxy-address {
  font-family: monospace;
  color: #e5e7eb;
}

.proxy-type {
  font-size: 10px;
}

.accounts-count {
  color: #9ca3af;
}

.last-check {
  font-size: 13px;
  color: #6b7280;
}

.actions-cell {
  display: flex;
  gap: 4px;
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
  background: rgba(255, 255, 255, 0.08);
  margin: 8px 0;
}

.hint-text {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

:deep(.custom-table .p-datatable) {
  background: transparent;
}

:deep(.custom-table .p-datatable-thead > tr > th) {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.06);
  color: #6b7280;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

:deep(.custom-table .p-datatable-tbody > tr) {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.04);
  transition: all 0.2s;
}

:deep(.custom-table .p-datatable-tbody > tr:hover) {
  background: rgba(255, 255, 255, 0.03);
}

:deep(.custom-table .p-datatable-tbody > tr > td) {
  border-color: rgba(255, 255, 255, 0.04);
  padding: 16px;
}

:deep(.custom-dialog .p-dialog-header) {
  background: #161616;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.custom-dialog .p-dialog-content) {
  background: #161616;
  padding: 24px;
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
  color: #6b7280;
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
  border: 1px solid rgba(255, 255, 255, 0.06);
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
  background: rgba(255, 255, 255, 0.03);
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
  color: #6b7280;
  font-weight: 500;
}

/* Edit dialog styles */
.string-input-row {
  display: flex;
  gap: 8px;
}

.edit-check-result {
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
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
  color: #6b7280;
  font-weight: 500;
}
</style>
