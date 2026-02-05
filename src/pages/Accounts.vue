<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAccountStore, useProxyStore, useGroupStore, useTagStore } from '@/stores'
import { useDebouncedRef } from '@/composables'
import type { Account, AccountStatus, BulkAction } from '@/types'

// Dialog components
import TwoFADialog from '@/components/accounts/TwoFADialog.vue'
import AddAccountDialog from '@/components/accounts/AddAccountDialog.vue'

import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import Checkbox from 'primevue/checkbox'
import Slider from 'primevue/slider'
import Menu from 'primevue/menu'
import InputGroup from 'primevue/inputgroup'
import InputGroupAddon from 'primevue/inputgroupaddon'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'

const { t } = useI18n()
const toast = useToast()
const confirm = useConfirm()

// Stores
const accountStore = useAccountStore()
const proxyStore = useProxyStore()
const groupStore = useGroupStore()
const tagStore = useTagStore()

// Parsed account interface for import flow
interface ParsedAccount {
  temp_id: string
  session_string: string
  telegram_id?: number
  phone?: string
  username?: string
  first_name?: string
  last_name?: string
  spamblock?: boolean
  register_time?: string
  geo?: string
  source_file?: string
  // Added by frontend
  proxy_id?: number
  status?: 'pending' | 'verifying' | 'valid' | 'invalid'
  error?: string
}

// Local state
const showImportDialog = ref(false)
const showGroupDialog = ref(false)
const showTagDialog = ref(false)
const showBatchCheckDialog = ref(false)
const showAddAccountDialog = ref(false)
const showTwoFADialog = ref(false)
const twoFAAccount = ref<Account | null>(null)
const batchChecking = ref(false)
const searchQuery = ref('')
const bulkMenu = ref()
const newGroupName = ref('')
const newGroupColor = ref('#a855f7')
const newTagName = ref('')
const newTagColor = ref('#a855f7')
// Drag & drop state
const isDragging = ref(false)
const pendingFiles = ref<File[]>([])
const tdataFiles = ref<File[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)
// Batch check options
const batchCheckSpamblock = ref(false)
const batchCheckMaxConcurrent = ref(3)

// New Import Flow State
const importStep = ref<'upload' | 'preview'>('upload')
const parsedAccounts = ref<ParsedAccount[]>([])
const parseErrors = ref<{ file: string; error: string }[]>([])
const parsing = ref(false)
const verifying = ref(false)
const saving = ref(false)
const checkingProxies = ref(false)
const bulkProxyId = ref<number | null>(null)
const importLogs = ref<{ time: string; type: 'info' | 'success' | 'error' | 'warn'; message: string }[]>([])
const logsContainer = ref<HTMLElement | null>(null)
const showLogs = ref(false)

// Quick proxy add dialog
const showQuickProxyDialog = ref(false)
const quickProxyString = ref('')
const quickProxyChecking = ref(false)
const quickProxyResult = ref<{ status: string; ping_ms?: number; geo?: string; error?: string } | null>(null)

function addImportLog(type: 'info' | 'success' | 'error' | 'warn', message: string) {
  const time = new Date().toLocaleTimeString()
  importLogs.value.push({ time, type, message })
  // Keep only last 50 logs
  if (importLogs.value.length > 50) {
    importLogs.value.shift()
  }
  // Auto-scroll to bottom
  nextTick(() => {
    if (logsContainer.value) {
      logsContainer.value.scrollTop = logsContainer.value.scrollHeight
    }
  })
}

// Computed
const selectedIds = computed({
  get: () => accountStore.selectedIds,
  set: (val) => {
    accountStore.selectedIds = val
  }
})

const hasSelection = computed(() => selectedIds.value.length > 0)

// Import flow computed
const allParsedHaveProxy = computed(() =>
  parsedAccounts.value.length > 0 &&
  parsedAccounts.value.every(a => a.proxy_id)
)

// Get unique proxy IDs assigned to parsed accounts
const assignedProxyIds = computed(() => {
  const ids = new Set<number>()
  parsedAccounts.value.forEach(a => {
    if (a.proxy_id) ids.add(a.proxy_id)
  })
  return Array.from(ids)
})

// Check if all assigned proxies have been checked and are working (including slow)
const proxiesChecked = computed(() => {
  if (assignedProxyIds.value.length === 0) return false
  return assignedProxyIds.value.every(id => {
    const proxy = proxyStore.getById(id)
    return proxy && ['working', 'slow', 'very_slow'].includes(proxy.status)
  })
})

const canVerify = computed(() =>
  allParsedHaveProxy.value &&
  proxiesChecked.value &&
  !verifying.value &&
  !checkingProxies.value &&
  parsedAccounts.value.some(a => a.status === 'pending')
)

const canSave = computed(() =>
  parsedAccounts.value.some(a => a.status === 'valid') && !saving.value
)

const validAccountsCount = computed(() =>
  parsedAccounts.value.filter(a => a.status === 'valid').length
)

const accountsWithProxy = computed(() =>
  parsedAccounts.value.filter(a => a.proxy_id).length
)


const statusOptions = computed(() => [
  { label: t('accounts.allStatuses'), value: null },
  { label: t('accounts.status.valid'), value: 'valid' },
  { label: t('accounts.status.invalid'), value: 'invalid' },
  { label: t('accounts.status.banned'), value: 'banned' },
  { label: t('accounts.status.muted'), value: 'muted' },
  { label: t('accounts.status.spamblock'), value: 'spamblock' },
  { label: t('accounts.status.session_expired'), value: 'session_expired' },
  { label: t('accounts.status.deactivated'), value: 'deactivated' },
  { label: t('accounts.status.needs_reauth'), value: 'needs_reauth' },
  { label: t('accounts.status.unchecked'), value: 'unchecked' }
])

const bulkMenuItems = computed(() => [
  {
    label: t('accounts.bulk.check'),
    icon: 'pi pi-refresh',
    command: () => showBatchCheckDialog.value = true
  },
  {
    label: t('accounts.bulk.setProxy'),
    icon: 'pi pi-globe',
    items: [
      { label: t('accounts.bulk.noProxy'), command: () => handleBulkAction('set_proxy', 0) },
      ...proxyStore.proxies.map(p => ({
        label: `${p.host}:${p.port}`,
        command: () => handleBulkAction('set_proxy', p.id)
      }))
    ]
  },
  {
    label: t('accounts.bulk.setGroup'),
    icon: 'pi pi-folder',
    items: [
      { label: t('accounts.bulk.noGroup'), command: () => handleBulkAction('set_group', 0) },
      ...groupStore.groups.map(g => ({
        label: g.name,
        command: () => handleBulkAction('set_group', g.id)
      }))
    ]
  },
  { separator: true },
  {
    label: t('accounts.bulk.delete'),
    icon: 'pi pi-trash',
    class: 'text-red-500',
    command: () => confirmBulkDelete()
  }
])

// Debounced search query for better performance
const debouncedSearch = useDebouncedRef(searchQuery, 300)

// Watch debounced search query
watch(debouncedSearch, (val) => {
  accountStore.setFilter('search', val || undefined)
})

// Lifecycle
onMounted(async () => {
  await Promise.all([
    accountStore.fetchAccounts(),
    proxyStore.fetchProxies(),
    groupStore.fetchGroups(),
    tagStore.fetchTags()
  ])
})

// Methods
function openFileSelector() {
  if (!parsing.value && fileInput.value) {
    fileInput.value.click()
  }
}

function openFolderSelector() {
  if (!parsing.value && folderInput.value) {
    folderInput.value.click()
  }
}

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files) {
    addFiles(Array.from(input.files))
    input.value = ''
  }
}

function handleFolderSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    // Filter tdata-relevant files from selected folder (can contain multiple tdata folders)
    const files = Array.from(input.files)
    const tdataRelevant = files.filter(f => {
      const path = (f.webkitRelativePath || f.name).replace(/\\/g, '/')
      // Check if path contains tdata folder (either at start or as subfolder)
      const hasTdata = path.startsWith('tdata/') || path.includes('/tdata/')
      // Include key_data, key_datas, and tdata session files (D877F783D5D3EF8C pattern or 16 hex chars)
      const isRelevantFile = path.includes('key_data') || /[0-9A-F]{16}/.test(path)
      return hasTdata && isRelevantFile
    })

    if (tdataRelevant.length > 0) {
      // Count unique tdata folders found
      const tdataFolders = new Set<string>()
      tdataRelevant.forEach(f => {
        const path = (f.webkitRelativePath || f.name).replace(/\\/g, '/')
        // Match tdata at start or as subfolder
        const match = path.match(/^(tdata|.+\/tdata)\//)
        if (match) tdataFolders.add(match[1])
      })

      const count = tdataFolders.size || 1
      toast.add({
        severity: 'info',
        summary: t('accounts.importFlow.tdataFound'),
        detail: t('accounts.importFlow.tdataFoundCount', { count }),
        life: 3000
      })

      tdataFiles.value = tdataRelevant
      parseTdataFolder()
    } else {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('accounts.importFlow.notTdataFolder'),
        life: 3000
      })
    }
    input.value = ''
  }
}

async function handleFileDrop(event: DragEvent) {
  isDragging.value = false
  if (parsing.value || !event.dataTransfer) return

  const items = event.dataTransfer.items
  const files: File[] = []
  const folderFiles: File[] = []

  // Process items to detect folders vs files
  if (items && items.length > 0) {
    const processEntry = async (entry: FileSystemEntry, path = ''): Promise<void> => {
      if (entry.isFile) {
        const fileEntry = entry as FileSystemFileEntry
        const file = await new Promise<File>((resolve) => {
          fileEntry.file((f) => {
            // Attach relative path
            Object.defineProperty(f, 'webkitRelativePath', {
              value: path + f.name,
              writable: false
            })
            resolve(f)
          })
        })
        // Check if it's a tdata-related file
        const fullPath = path + file.name
        if (fullPath.includes('key_data') ||
            fullPath.includes('key_datas') ||
            /D877F783D5D3EF8C/.test(fullPath) ||
            /[0-9A-F]{16}/.test(file.name)) {
          folderFiles.push(file)
        } else if (file.name.endsWith('.session') || file.name.endsWith('.json') || file.name.endsWith('.zip')) {
          files.push(file)
        }
      } else if (entry.isDirectory) {
        const dirEntry = entry as FileSystemDirectoryEntry
        const reader = dirEntry.createReader()
        const entries = await new Promise<FileSystemEntry[]>((resolve) => {
          reader.readEntries((e) => resolve(e))
        })
        for (const childEntry of entries) {
          await processEntry(childEntry, path + entry.name + '/')
        }
      }
    }

    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry()
      if (entry) {
        await processEntry(entry)
      }
    }
  }

  // Process both types if found
  if (folderFiles.length > 0 || files.length > 0) {
    // Process tdata files if found
    if (folderFiles.length > 0) {
      tdataFiles.value = folderFiles
      await parseTdataFolder()
    }
    // Process regular files (session/json/zip) if found
    if (files.length > 0) {
      await addFiles(files)
    }
  }
  // Fallback to simple file list
  else if (event.dataTransfer.files.length > 0) {
    await addFiles(Array.from(event.dataTransfer.files))
  }
}

async function addFiles(files: File[]) {
  const validExtensions = ['.zip', '.json', '.session']
  const validFiles = files.filter(f =>
    validExtensions.some(ext => f.name.toLowerCase().endsWith(ext))
  )
  pendingFiles.value = [...pendingFiles.value, ...validFiles]

  // Auto-parse files immediately
  if (pendingFiles.value.length > 0) {
    await parseFiles()
  }
}

// New Import Flow Methods
async function parseTdataFolder() {
  if (tdataFiles.value.length === 0) return

  parsing.value = true
  addImportLog('info', `Парсинг tdata папки (${tdataFiles.value.length} файлов)...`)

  try {
    const result = await accountStore.parseTdataFiles(tdataFiles.value)
    addImportLog('success', `Распарсено: ${result.accounts.length} аккаунтов`)

    const newAccounts = result.accounts.map((a: any) => ({
      ...a,
      status: 'pending' as const,
      proxy_id: undefined
    }))

    // Append to existing accounts instead of replacing
    parsedAccounts.value = [...parsedAccounts.value, ...newAccounts]

    if (result.errors?.length > 0) {
      result.errors.forEach((err: { file: string; error: string }) => {
        addImportLog('error', `Ошибка: ${err.file} - ${err.error}`)
        toast.add({
          severity: 'error',
          summary: err.file,
          detail: err.error,
          life: 5000
        })
      })
    }

    if (newAccounts.length > 0) {
      importStep.value = 'preview'
      newAccounts.forEach((acc: any, i: number) => {
        addImportLog('info', `Аккаунт ${i + 1}: ${acc.source_file || 'tdata'}, session=${!!acc.session_string}`)
      })
    } else {
      addImportLog('warn', 'Не удалось распарсить аккаунты')
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('accounts.importFlow.noAccountsParsed'),
        life: 3000
      })
    }
  } catch (error: any) {
    addImportLog('error', `Ошибка парсинга: ${error.message}`)
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.importFailed'),
      detail: error.message,
      life: 5000
    })
  } finally {
    parsing.value = false
    tdataFiles.value = []
  }
}

async function parseFiles() {
  if (pendingFiles.value.length === 0) return

  parsing.value = true

  try {
    const sessionFiles = pendingFiles.value.filter(f => f.name.endsWith('.session'))
    const jsonFiles = pendingFiles.value.filter(f => f.name.endsWith('.json'))
    const zipFiles = pendingFiles.value.filter(f => f.name.endsWith('.zip'))
    const tdataFile = zipFiles[0] // Only one tdata at a time

    const result = await accountStore.parseImportFiles(sessionFiles, jsonFiles, tdataFile)

    const newAccounts = result.accounts.map(a => ({
      ...a,
      status: 'pending' as const,
      proxy_id: undefined
    }))

    // Append to existing accounts instead of replacing
    parsedAccounts.value = [...parsedAccounts.value, ...newAccounts]

    if (result.errors?.length > 0) {
      result.errors.forEach(err => {
        toast.add({
          severity: 'error',
          summary: err.file,
          detail: err.error,
          life: 5000
        })
      })
    }

    if (newAccounts.length > 0) {
      importStep.value = 'preview'
    } else {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('accounts.importFlow.noAccountsParsed'),
        life: 3000
      })
    }
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.importFailed'),
      detail: error.message,
      life: 5000
    })
  } finally {
    parsing.value = false
  }
}

function assignBulkProxy() {
  if (!bulkProxyId.value) return
  parsedAccounts.value.forEach(a => {
    a.proxy_id = bulkProxyId.value!
  })
}

async function checkParsedProxies() {
  addImportLog('info', 'Запуск проверки прокси...')

  if (!allParsedHaveProxy.value || assignedProxyIds.value.length === 0) {
    addImportLog('warn', 'Не все аккаунты имеют назначенные прокси')
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('accounts.importFlow.assignProxyFirst'),
      life: 3000
    })
    return
  }

  addImportLog('info', `Проверяем ${assignedProxyIds.value.length} прокси: [${assignedProxyIds.value.join(', ')}]`)
  checkingProxies.value = true

  try {
    const result = await proxyStore.checkBatchProxies(assignedProxyIds.value)

    const workingCount = result.results.filter(r => ['working', 'slow', 'very_slow'].includes(r.status)).length
    const failedCount = result.results.length - workingCount

    result.results.forEach(r => {
      const proxy = proxyStore.getById(r.id)
      if (['working', 'slow', 'very_slow'].includes(r.status)) {
        addImportLog('success', `✓ Прокси ${proxy?.host}:${proxy?.port} работает (${r.status}, ${r.ping_ms}ms)`)
      } else {
        addImportLog('error', `✗ Прокси ${proxy?.host}:${proxy?.port} не работает (${r.status})`)
      }
    })

    addImportLog('info', `Проверка завершена: ${workingCount} работают, ${failedCount} не работают`)

    if (failedCount > 0) {
      toast.add({
        severity: 'warn',
        summary: t('proxy.messages.checkComplete', { count: result.results.length }),
        detail: `${workingCount} ${t('proxy.addDialog.working')}, ${failedCount} ${t('proxy.status.not_working')}`,
        life: 5000
      })
    } else {
      toast.add({
        severity: 'success',
        summary: t('proxy.messages.checkComplete', { count: result.results.length }),
        detail: `${workingCount} ${t('proxy.addDialog.working')}`,
        life: 3000
      })
    }
  } catch (error: any) {
    addImportLog('error', `Ошибка проверки прокси: ${error.message}`)
    toast.add({
      severity: 'error',
      summary: t('proxy.messages.checkFailed'),
      detail: error.message,
      life: 5000
    })
  } finally {
    checkingProxies.value = false
  }
}

function setAccountProxy(tempId: string, proxyId: number | null) {
  const account = parsedAccounts.value.find(a => a.temp_id === tempId)
  if (account) {
    account.proxy_id = proxyId || undefined
  }
}

async function verifyParsedAccounts() {
  addImportLog('info', `Запуск верификации аккаунтов...`)
  addImportLog('info', `allParsedHaveProxy: ${allParsedHaveProxy.value}, proxiesChecked: ${proxiesChecked.value}, canVerify: ${canVerify.value}`)
  addImportLog('info', `Аккаунтов: ${parsedAccounts.value.length}, assignedProxyIds: [${assignedProxyIds.value.join(', ')}]`)

  // Log each account's state
  parsedAccounts.value.forEach((a, i) => {
    const proxy = a.proxy_id ? proxyStore.getById(a.proxy_id) : null
    addImportLog('info', `Аккаунт ${i + 1}: proxy_id=${a.proxy_id}, status=${a.status}, hasSession=${!!a.session_string}, proxyStatus=${proxy?.status || 'none'}`)
  })

  if (!allParsedHaveProxy.value) {
    addImportLog('warn', 'Не все аккаунты имеют прокси!')
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('accounts.importFlow.assignProxyFirst'),
      life: 3000
    })
    return
  }

  if (!proxiesChecked.value) {
    addImportLog('warn', 'Прокси не проверены или не работают!')
    // Log proxy statuses
    assignedProxyIds.value.forEach(id => {
      const proxy = proxyStore.getById(id)
      addImportLog('info', `Прокси ${id}: status=${proxy?.status || 'not found'}`)
    })
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('accounts.importFlow.checkProxiesFirst'),
      life: 3000
    })
    return
  }

  verifying.value = true
  addImportLog('info', 'Начинаем верификацию...')

  // Mark all pending as verifying
  parsedAccounts.value.forEach(a => {
    if (a.status === 'pending') {
      a.status = 'verifying'
    }
  })

  try {
    // Create plain objects to avoid Vue reactivity serialization issues
    const accountsToVerify = parsedAccounts.value
      .filter(a => a.status === 'verifying')
      .map(a => JSON.parse(JSON.stringify({
        temp_id: a.temp_id,
        session_string: a.session_string,
        proxy_id: a.proxy_id
      })))

    addImportLog('info', `Отправляем ${accountsToVerify.length} аккаунтов на верификацию...`)

    if (accountsToVerify.length === 0) {
      addImportLog('warn', 'Нет аккаунтов для верификации!')
      verifying.value = false
      return
    }

    const result = await accountStore.verifyParsedAccounts(accountsToVerify)
    addImportLog('success', `Получен ответ от сервера`)

    // Update statuses from results
    result.results.forEach(r => {
      const account = parsedAccounts.value.find(a => a.temp_id === r.temp_id)
      if (account) {
        account.status = r.status === 'valid' ? 'valid' : 'invalid'
        account.error = r.error
        if (r.telegram_id) account.telegram_id = r.telegram_id
        if (r.username) account.username = r.username
        if (r.phone) account.phone = r.phone
        if (r.first_name) account.first_name = r.first_name
        if (r.last_name) account.last_name = r.last_name

        if (r.status === 'valid') {
          addImportLog('success', `✓ Аккаунт ${r.username || r.telegram_id || r.temp_id} валиден`)
        } else {
          addImportLog('error', `✗ Аккаунт ${r.temp_id}: ${r.error || 'invalid'}`)
        }
      }
    })

    addImportLog('success', `Верификация завершена: ${result.total_valid} валидных, ${result.total_invalid} невалидных`)

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.importFlow.verifyComplete', { valid: result.total_valid, invalid: result.total_invalid }),
      life: 5000
    })
  } catch (error: any) {
    addImportLog('error', `Ошибка: ${error.message}`)
    // Reset statuses on error
    parsedAccounts.value.forEach(a => {
      if (a.status === 'verifying') {
        a.status = 'pending'
      }
    })
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 5000
    })
  } finally {
    verifying.value = false
  }
}

async function saveVerifiedAccounts() {
  const validAccounts = parsedAccounts.value.filter(a => a.status === 'valid')
  if (validAccounts.length === 0) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('accounts.importFlow.noValidAccounts'),
      life: 3000
    })
    return
  }

  saving.value = true
  addImportLog('info', `Сохраняем ${validAccounts.length} аккаунтов...`)

  try {
    // Convert to plain objects to avoid Vue reactivity serialization issues
    const accountsToSave = validAccounts.map(a => JSON.parse(JSON.stringify(a)))
    const result = await accountStore.saveParsedAccounts(accountsToSave)

    addImportLog('success', `Збережено ${result.total_saved} акаунтів`)

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.importFlow.savedCount', { count: result.total_saved }),
      life: 3000
    })

    // Show errors if any
    if (result.errors?.length > 0) {
      result.errors.forEach(err => {
        addImportLog('error', `Помилка: ${err.error}`)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: err.error,
          life: 5000
        })
      })
    }

    // Reset and close dialog
    resetImportDialog()
    showImportDialog.value = false
  } catch (error: any) {
    addImportLog('error', `Помилка збереження: ${error.message}`)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 5000
    })
  } finally {
    saving.value = false
  }
}

function resetImportDialog() {
  importStep.value = 'upload'
  parsedAccounts.value = []
  parseErrors.value = []
  pendingFiles.value = []
  tdataFiles.value = []
  bulkProxyId.value = null
  importLogs.value = []
  showLogs.value = false
}

function backToUpload() {
  importStep.value = 'upload'
  parsedAccounts.value = []
}

function getImportStatusSeverity(status?: string): "success" | "info" | "warn" | "danger" | "secondary" | undefined {
  switch (status) {
    case 'valid': return 'success'
    case 'invalid': return 'danger'
    case 'verifying': return 'info'
    default: return 'secondary'
  }
}

function removeParsedAccount(tempId: string) {
  parsedAccounts.value = parsedAccounts.value.filter(a => a.temp_id !== tempId)
  if (parsedAccounts.value.length === 0) {
    backToUpload()
  }
}

function clearAllParsedAccounts() {
  parsedAccounts.value = []
  bulkProxyId.value = null
}

function getAccountStatusLabel(status?: string): string {
  switch (status) {
    case 'valid': return t('accounts.importFlow.status.valid')
    case 'invalid': return t('accounts.importFlow.status.invalid')
    case 'verifying': return t('accounts.importFlow.status.verifying')
    default: return t('accounts.importFlow.status.pending')
  }
}

function getProxyStatusLabel(proxyId: number): string {
  const proxy = proxyStore.getById(proxyId)
  if (!proxy) return '—'
  return t(`proxy.status.${proxy.status}`)
}

function getProxyStatusSeverity(proxyId: number): "success" | "info" | "warn" | "danger" | "secondary" | undefined {
  const proxy = proxyStore.getById(proxyId)
  if (!proxy) return 'secondary'
  switch (proxy.status) {
    case 'working': return 'success'
    case 'slow': return 'warn'
    case 'very_slow': return 'warn'
    case 'not_working': return 'danger'
    case 'timeout': return 'danger'
    case 'unchecked': return 'secondary'
    default: return 'secondary'
  }
}

// Quick proxy add functions
function parseProxyString(str: string): { type: string; host: string; port: number; username?: string; password?: string } | null {
  const trimmed = str.trim()
  if (!trimmed) return null

  // Try URL format: type://user:pass@host:port
  const urlMatch = trimmed.match(/^(socks5|socks4|http|https):\/\/(?:([^:]+):([^@]+)@)?([^:]+):(\d+)$/i)
  if (urlMatch) {
    return {
      type: urlMatch[1].toLowerCase(),
      username: urlMatch[2] || undefined,
      password: urlMatch[3] || undefined,
      host: urlMatch[4],
      port: parseInt(urlMatch[5])
    }
  }

  // Try simple format: host:port or host:port:user:pass
  const parts = trimmed.split(':')
  if (parts.length >= 2) {
    return {
      type: 'socks5',
      host: parts[0],
      port: parseInt(parts[1]),
      username: parts[2] || undefined,
      password: parts[3] || undefined
    }
  }

  return null
}

async function checkQuickProxy() {
  const parsed = parseProxyString(quickProxyString.value)
  if (!parsed) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('accounts.importFlow.invalidProxyFormat'),
      life: 3000
    })
    return
  }

  quickProxyChecking.value = true
  quickProxyResult.value = null
  addImportLog('info', `Проверяем прокси ${parsed.host}:${parsed.port}...`)

  try {
    const result = await window.api.post('/api/proxy/check-preview', {
      proxies: [parsed],
      lookup_geo: true
    }) as { results: any[] }

    if (result.results.length > 0) {
      quickProxyResult.value = result.results[0]
      if (result.results[0].status === 'working') {
        addImportLog('success', `✓ Прокси работает (${result.results[0].ping_ms}ms, ${result.results[0].geo || 'unknown'})`)
      } else {
        addImportLog('error', `✗ Прокси не работает: ${result.results[0].error || result.results[0].status}`)
      }
    }
  } catch (error: any) {
    addImportLog('error', `Ошибка проверки: ${error.message}`)
    quickProxyResult.value = { status: 'error', error: error.message }
  } finally {
    quickProxyChecking.value = false
  }
}

async function addQuickProxy() {
  const parsed = parseProxyString(quickProxyString.value)
  if (!parsed) return

  try {
    const proxyData: any = {
      ...parsed,
      username: parsed.username || null,
      password: parsed.password || null
    }

    // If checked and working, include check results
    if (quickProxyResult.value && quickProxyResult.value.status === 'working') {
      proxyData.status = quickProxyResult.value.status
      proxyData.ping_ms = quickProxyResult.value.ping_ms
      proxyData.geo = quickProxyResult.value.geo
    }

    const newProxy = await window.api.post('/api/proxy', proxyData)
    await proxyStore.fetchProxies()

    // Auto-select the new proxy
    bulkProxyId.value = newProxy.id
    assignBulkProxy()

    addImportLog('success', `Прокси добавлен: ${parsed.host}:${parsed.port}`)

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.importFlow.proxyAdded'),
      life: 3000
    })

    // Reset dialog
    showQuickProxyDialog.value = false
    quickProxyString.value = ''
    quickProxyResult.value = null
  } catch (error: any) {
    addImportLog('error', `Ошибка добавления прокси: ${error.message}`)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 5000
    })
  }
}

function resetQuickProxyDialog() {
  quickProxyString.value = ''
  quickProxyResult.value = null
  quickProxyChecking.value = false
}

async function checkAccount(account: Account) {
  try {
    const result = await accountStore.checkAccount(account.id)
    toast.add({
      severity: result.valid ? 'success' : 'error',
      summary: result.valid ? t('accounts.messages.accountValid') : t('accounts.messages.accountInvalid'),
      detail: result.valid
        ? t('accounts.messages.accountWorking', { name: result.user_info?.username || account.telegram_id })
        : result.error,
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.checkFailed'),
      detail: error.message,
      life: 3000
    })
  }
}

function confirmDelete(account: Account) {
  const name = account.username || account.telegram_id
  confirm.require({
    message: t('accounts.deleteConfirm', { name }),
    header: t('common.confirmation'),
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await accountStore.deleteAccount(account.id)
        toast.add({
          severity: 'success',
          summary: t('common.success'),
          detail: t('accounts.messages.deleted'),
          life: 3000
        })
      } catch (error: any) {
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.message,
          life: 3000
        })
      }
    }
  })
}

async function handleBulkAction(action: BulkAction, value?: number) {
  try {
    await accountStore.bulkAction(action, value)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.messages.bulkSuccess', { count: selectedIds.value.length }),
      life: 3000
    })
    if (action !== 'check') {
      accountStore.clearSelection()
    }
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 3000
    })
  }
}

function confirmBulkDelete() {
  confirm.require({
    message: t('accounts.bulkDeleteConfirm', { count: selectedIds.value.length }),
    header: t('common.confirmation'),
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => handleBulkAction('delete')
  })
}

function toggleBulkMenu(event: Event) {
  bulkMenu.value.toggle(event)
}

async function checkAllAccounts() {
  toast.add({
    severity: 'info',
    summary: t('common.info'),
    detail: t('accounts.messages.checkingAll'),
    life: 3000
  })

  for (const account of accountStore.accounts) {
    if (account.status !== 'valid') {
      await checkAccount(account)
    }
  }
}

async function checkBatchSelected() {
  if (selectedIds.value.length === 0) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('accounts.messages.selectAccountsFirst'),
      life: 3000
    })
    return
  }

  batchChecking.value = true
  showBatchCheckDialog.value = false

  try {
    const result = await accountStore.checkBatchAccounts(
      selectedIds.value,
      {
        checkSpamblock: batchCheckSpamblock.value,
        maxConcurrent: batchCheckMaxConcurrent.value
      }
    )

    const validCount = result.results.filter(r => r.status === 'valid').length
    const invalidCount = result.results.filter(r => r.status !== 'valid').length

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.messages.batchCheckComplete', { valid: validCount, invalid: invalidCount }),
      life: 5000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 5000
    })
  } finally {
    batchChecking.value = false
  }
}


function selectGroup(groupId: number | null) {
  groupStore.selectGroup(groupId)
  accountStore.setFilter('group_id', groupId || undefined)
}

function setStatusFilter(status: AccountStatus | null) {
  accountStore.setFilter('status', status || undefined)
}

async function createGroup() {
  if (!newGroupName.value.trim()) return

  try {
    await groupStore.createGroup({
      name: newGroupName.value.trim(),
      color: newGroupColor.value
    })
    newGroupName.value = ''
    showGroupDialog.value = false
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('groups.created'),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 3000
    })
  }
}

async function deleteGroup(id: number) {
  try {
    await groupStore.deleteGroup(id)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('groups.deleted'),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 3000
    })
  }
}

async function createTag() {
  if (!newTagName.value.trim()) return

  try {
    await tagStore.createTag({
      name: newTagName.value.trim(),
      color: newTagColor.value
    })
    newTagName.value = ''
    showTagDialog.value = false
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('tags.created'),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 3000
    })
  }
}

async function deleteTag(id: number) {
  try {
    await tagStore.deleteTag(id)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('tags.deleted'),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 3000
    })
  }
}

function getStatusSeverity(status: string): "success" | "info" | "warn" | "danger" | "secondary" | "contrast" | undefined {
  switch (status) {
    case 'valid': return 'success'
    case 'invalid': return 'danger'
    case 'banned': return 'danger'
    case 'deactivated': return 'danger'
    case 'muted': return 'warn'
    case 'spamblock': return 'warn'
    case 'session_expired': return 'warn'
    case 'needs_reauth': return 'warn'
    case 'connection_failed': return 'warn'
    case 'checking': return 'info'
    default: return 'secondary'
  }
}

function getDisplayName(account: Account): string {
  if (account.username) return `@${account.username}`
  if (account.first_name) return account.first_name
  if (account.telegram_id) return `ID: ${account.telegram_id}`
  if (account.phone) return account.phone
  return 'Unknown'
}

function openTwoFADialog(account: Account) {
  twoFAAccount.value = account
  showTwoFADialog.value = true
}

function handleAccountAdded() {
  showAddAccountDialog.value = false
  toast.add({
    severity: 'success',
    summary: t('common.success'),
    detail: t('accounts.auth.success.description'),
    life: 3000
  })
}

function onRowSelect(event: any) {
  accountStore.toggleSelection(event.data.id)
}

function onRowUnselect(event: any) {
  accountStore.toggleSelection(event.data.id)
}
</script>

<template>
  <MainLayout>
    <Toast />
    <ConfirmDialog />

    <div class="accounts-page">
      <div class="accounts-layout">
        <!-- Sidebar with Groups -->
        <div class="groups-sidebar">
          <div class="sidebar-header">
            <h3 class="sidebar-title">{{ t('groups.title') }}</h3>
            <Button
              icon="pi pi-plus"
              severity="secondary"
              text
              rounded
              size="small"
              @click="showGroupDialog = true"
            />
          </div>

          <div class="groups-list">
            <div
              class="group-item"
              :class="{ active: groupStore.selectedGroupId === null }"
              @click="selectGroup(null)"
            >
              <div class="group-icon" style="background: #6366f1">
                <i class="pi pi-users"></i>
              </div>
              <div class="group-info">
                <span class="group-name">{{ t('groups.allAccounts') }}</span>
                <span class="group-count">{{ accountStore.accounts.length }}</span>
              </div>
            </div>

            <div
              v-for="group in groupStore.groups"
              :key="group.id"
              class="group-item"
              :class="{ active: groupStore.selectedGroupId === group.id }"
              @click="selectGroup(group.id)"
            >
              <div class="group-icon" :style="{ background: group.color || '#a855f7' }">
                <i class="pi pi-folder"></i>
              </div>
              <div class="group-info">
                <span class="group-name">{{ group.name }}</span>
                <span class="group-count">{{ group.accounts_count }}</span>
              </div>
              <Button
                icon="pi pi-trash"
                severity="danger"
                text
                rounded
                size="small"
                class="delete-btn"
                @click.stop="deleteGroup(group.id)"
              />
            </div>
          </div>

          <!-- Tags Section -->
          <div class="sidebar-section">
            <div class="sidebar-header">
              <h3 class="sidebar-title">{{ t('tags.title') }}</h3>
              <Button
                icon="pi pi-plus"
                severity="secondary"
                text
                rounded
                size="small"
                @click="showTagDialog = true"
              />
            </div>

            <div class="tags-list">
              <div
                v-for="tag in tagStore.tags"
                :key="tag.id"
                class="tag-item"
                :class="{ active: accountStore.filters.tag_id === tag.id }"
                @click="accountStore.setFilter('tag_id', accountStore.filters.tag_id === tag.id ? undefined : tag.id)"
              >
                <span class="tag-dot" :style="{ background: tag.color }"></span>
                <span class="tag-name">{{ tag.name }}</span>
                <Button
                  icon="pi pi-times"
                  severity="danger"
                  text
                  rounded
                  size="small"
                  class="delete-btn"
                  :aria-label="t('common.delete') + ' ' + tag.name"
                  @click.stop="deleteTag(tag.id)"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
          <div class="page-header">
            <h1 class="page-title">{{ t('accounts.title') }}</h1>
            <div class="header-actions">
              <Button
                :label="t('accounts.addAccount')"
                icon="pi pi-plus"
                @click="showAddAccountDialog = true"
              />
              <Button
                :label="t('accounts.import')"
                icon="pi pi-upload"
                severity="secondary"
                @click="showImportDialog = true"
              />
              <Button
                :label="t('accounts.checkAll')"
                icon="pi pi-refresh"
                severity="secondary"
                @click="checkAllAccounts"
                :disabled="accountStore.accounts.length === 0"
              />
            </div>
          </div>

          <!-- Filters Bar -->
          <div class="filters-bar">
            <InputGroup>
              <InputGroupAddon>
                <i class="pi pi-search"></i>
              </InputGroupAddon>
              <InputText
                v-model="searchQuery"
                :placeholder="t('accounts.searchPlaceholder')"
                class="search-input"
              />
            </InputGroup>

            <Dropdown
              :model-value="accountStore.filters.status"
              :options="statusOptions"
              optionLabel="label"
              optionValue="value"
              :placeholder="t('accounts.filterByStatus')"
              @update:model-value="setStatusFilter"
              class="status-filter"
              showClear
            />

            <div v-if="hasSelection" class="bulk-actions">
              <span class="selection-count">
                {{ t('accounts.selected', { count: selectedIds.length }) }}
              </span>
              <Button
                :label="t('accounts.bulk.actions')"
                icon="pi pi-chevron-down"
                iconPos="right"
                severity="secondary"
                @click="toggleBulkMenu"
              />
              <Menu ref="bulkMenu" :model="bulkMenuItems" :popup="true" />
              <Button
                icon="pi pi-times"
                severity="secondary"
                text
                rounded
                :aria-label="t('accounts.bulk.clearSelection')"
                v-tooltip.top="t('accounts.bulk.clearSelection')"
                @click="accountStore.clearSelection"
              />
            </div>
          </div>

          <!-- Accounts Table -->
          <div class="table-card">
            <DataTable
              v-model:selection="selectedIds"
              :value="accountStore.filteredAccounts"
              :loading="accountStore.loading"
              paginator
              :rows="20"
              dataKey="id"
              class="custom-table"
              selectionMode="multiple"
              @row-select="onRowSelect"
              @row-unselect="onRowUnselect"
            >
              <template #empty>
                <div class="empty-state">
                  <div class="empty-icon">
                    <i class="pi pi-users"></i>
                  </div>
                  <p class="empty-text">{{ t('accounts.noAccounts') }}</p>
                  <Button
                    :label="t('accounts.importAccounts')"
                    icon="pi pi-upload"
                    @click="showImportDialog = true"
                  />
                </div>
              </template>

              <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>

              <Column field="id" header="ID" sortable style="width: 80px" />

              <Column :header="t('accounts.account')" sortable>
                <template #body="{ data }">
                  <div class="account-cell">
                    <div class="account-avatar">
                      {{ (data.first_name || data.username || '?')[0].toUpperCase() }}
                    </div>
                    <div class="account-info">
                      <div class="account-name">{{ getDisplayName(data) }}</div>
                      <div v-if="data.phone" class="account-phone">{{ data.phone }}</div>
                    </div>
                  </div>
                </template>
              </Column>

              <Column field="status" :header="t('common.status')" sortable style="width: 140px">
                <template #body="{ data }">
                  <Tag :value="t(`accounts.status.${data.status}`)" :severity="getStatusSeverity(data.status)" />
                </template>
              </Column>

              <Column :header="t('accounts.proxy')" style="width: 180px">
                <template #body="{ data }">
                  <span v-if="data.proxy" class="proxy-text">
                    {{ data.proxy.host }}:{{ data.proxy.port }}
                  </span>
                  <span v-else class="no-data">{{ t('accounts.noProxy') }}</span>
                </template>
              </Column>

              <Column :header="t('accounts.group')" style="width: 150px">
                <template #body="{ data }">
                  <span v-if="data.group" class="group-text">{{ data.group.name }}</span>
                  <span v-else class="no-data">—</span>
                </template>
              </Column>

              <Column :header="t('accounts.tags')" style="width: 180px">
                <template #body="{ data }">
                  <div class="tags-cell">
                    <Tag
                      v-for="tag in data.tags"
                      :key="tag.id"
                      :value="tag.name"
                      :style="{ backgroundColor: tag.color }"
                    />
                  </div>
                </template>
              </Column>

              <Column :header="t('common.actions')" style="width: 160px">
                <template #body="{ data }">
                  <div class="actions-cell">
                    <Button
                      icon="pi pi-refresh"
                      severity="secondary"
                      text
                      rounded
                      v-tooltip.top="t('common.check')"
                      :aria-label="t('common.check')"
                      @click="checkAccount(data)"
                    />
                    <Button
                      :icon="data.has_2fa ? 'pi pi-lock' : 'pi pi-lock-open'"
                      :severity="data.has_2fa ? 'success' : 'secondary'"
                      text
                      rounded
                      v-tooltip.top="t('accounts.twoFA.title')"
                      :aria-label="t('accounts.twoFA.title')"
                      @click="openTwoFADialog(data)"
                    />
                    <Button
                      icon="pi pi-trash"
                      severity="danger"
                      text
                      rounded
                      v-tooltip.top="t('common.delete')"
                      :aria-label="t('common.delete')"
                      @click="confirmDelete(data)"
                    />
                  </div>
                </template>
              </Column>
            </DataTable>
          </div>
        </div>
      </div>

      <!-- Import Dialog -->
      <Dialog
        v-model:visible="showImportDialog"
        :header="t('accounts.importDialog.title')"
        modal
        :style="{ width: '1000px' }"
        :closable="!parsing && !verifying && !saving"
        class="custom-dialog import-dialog-unified"
        @hide="resetImportDialog"
      >
        <ProgressBar v-if="parsing" mode="indeterminate" style="height: 4px" class="mb-4" />

        <!-- Upload Cards -->
        <div
          class="upload-zone-unified"
          :class="{ 'upload-zone-active': isDragging }"
          @dragenter.prevent="isDragging = true"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleFileDrop"
        >
          <div class="upload-cards">
            <div class="upload-card" @click.stop="openFolderSelector">
              <div class="upload-card-icon tdata-icon">
                <i class="pi pi-folder"></i>
              </div>
              <span class="upload-card-label">TData</span>
            </div>
            <div class="upload-card-divider"></div>
            <div class="upload-card" @click.stop="openFileSelector">
              <div class="upload-card-icon session-icon">
                <i class="pi pi-file"></i>
              </div>
              <span class="upload-card-label">.session</span>
            </div>
          </div>
          <div class="upload-hint">
            <i class="pi pi-arrows-alt"></i>
            <span>{{ t('accounts.importFlow.orDragHere') }}</span>
          </div>
          <input
            ref="fileInput"
            type="file"
            multiple
            accept=".zip,.json,.session"
            class="hidden-input"
            @change="handleFileSelect"
          />
          <input
            ref="folderInput"
            type="file"
            webkitdirectory
            directory
            multiple
            class="hidden-input"
            @change="handleFolderSelect"
          />
        </div>

        <!-- Proxy Selection Row -->
        <div class="proxy-selection-row">
          <Dropdown
            v-model="bulkProxyId"
            :options="proxyStore.proxies"
            optionLabel="host"
            optionValue="id"
            :placeholder="t('accounts.importFlow.selectProxy')"
            class="proxy-main-dropdown"
            @update:model-value="assignBulkProxy"
          >
            <template #value="{ value }">
              <div class="proxy-dropdown-value">
                <i class="pi pi-server"></i>
                <span v-if="value">
                  {{ proxyStore.getById(value)?.host }}:{{ proxyStore.getById(value)?.port }}
                </span>
                <span v-else>{{ t('accounts.importFlow.selectProxy') }}</span>
              </div>
            </template>
            <template #option="{ option }">
              <div class="proxy-option">
                <span>{{ option.host }}:{{ option.port }}</span>
                <Tag
                  :value="t(`proxy.status.${option.status}`)"
                  :severity="option.status === 'working' ? 'success' : option.status === 'unchecked' ? 'secondary' : 'danger'"
                  class="proxy-status-tag"
                />
              </div>
            </template>
          </Dropdown>
          <Button
            icon="pi pi-plus"
            severity="secondary"
            v-tooltip.top="t('accounts.importFlow.addProxy')"
            @click="showQuickProxyDialog = true"
          />
          <Button
            icon="pi pi-trash"
            severity="danger"
            text
            :disabled="parsedAccounts.length === 0"
            @click="clearAllParsedAccounts"
            v-tooltip.top="t('accounts.importFlow.clearAll')"
          />
        </div>

        <!-- Stats Bar -->
        <div class="import-stats-bar">
          <div class="stat-badge">
            <i class="pi pi-users"></i>
            <span>{{ parsedAccounts.length }}</span>
          </div>
          <div class="stat-badge stat-proxy">
            <i class="pi pi-server"></i>
            <span>{{ accountsWithProxy }}/{{ parsedAccounts.length }}</span>
          </div>
          <div class="stat-badge stat-verified">
            <i class="pi pi-check-circle"></i>
            <span>{{ validAccountsCount }}</span>
          </div>
        </div>

        <!-- Accounts Table -->
        <div class="import-table-container">
          <DataTable
            v-if="parsedAccounts.length > 0"
            :value="parsedAccounts"
            :loading="verifying"
            scrollable
            scrollHeight="300px"
            class="custom-table import-table-unified"
          >
            <Column :header="t('accounts.account')" style="min-width: 140px">
              <template #body="{ data }">
                <div class="account-cell">
                  <i class="pi pi-user"></i>
                  <span>{{ data.source_file || 'tdata' }}</span>
                </div>
              </template>
            </Column>

            <Column :header="t('accounts.importFlow.format')" style="min-width: 100px">
              <template #body="{ data }">
                <div class="format-cell">
                  <i class="pi pi-file"></i>
                  <span>{{ data.source_file?.includes('.session') ? 'session' : 'tdata' }}</span>
                </div>
              </template>
            </Column>

            <Column :header="t('accounts.importFlow.phone')" style="min-width: 120px">
              <template #body="{ data }">
                <span>{{ data.phone || '—' }}</span>
              </template>
            </Column>

            <Column header="Username" style="min-width: 120px">
              <template #body="{ data }">
                <span>{{ data.username ? `@${data.username}` : '—' }}</span>
              </template>
            </Column>

            <Column :header="t('accounts.proxy')" style="min-width: 200px">
              <template #body="{ data }">
                <Dropdown
                  :model-value="data.proxy_id"
                  :options="proxyStore.proxies"
                  optionLabel="host"
                  optionValue="id"
                  :placeholder="t('accounts.importFlow.selectProxy')"
                  class="table-proxy-dropdown"
                  @update:model-value="setAccountProxy(data.temp_id, $event)"
                >
                  <template #value="{ value }">
                    <span v-if="value" class="proxy-value-small">
                      {{ proxyStore.getById(value)?.type }}://{{ proxyStore.getById(value)?.host }}:{{ proxyStore.getById(value)?.port }}
                    </span>
                    <span v-else class="placeholder-text">—</span>
                  </template>
                  <template #option="{ option }">
                    <div class="proxy-option">
                      <span>{{ option.host }}:{{ option.port }}</span>
                      <Tag
                        :value="t(`proxy.status.${option.status}`)"
                        :severity="option.status === 'working' ? 'success' : option.status === 'unchecked' ? 'secondary' : 'danger'"
                        class="proxy-status-tag"
                      />
                    </div>
                  </template>
                </Dropdown>
              </template>
            </Column>

            <Column :header="t('accounts.importFlow.accountStatus')" style="min-width: 140px">
              <template #body="{ data }">
                <Tag
                  :value="getAccountStatusLabel(data.status)"
                  :severity="getImportStatusSeverity(data.status)"
                  class="status-tag"
                />
              </template>
            </Column>

            <Column :header="t('accounts.importFlow.proxyStatus')" style="min-width: 130px">
              <template #body="{ data }">
                <Tag
                  v-if="data.proxy_id"
                  :value="getProxyStatusLabel(data.proxy_id)"
                  :severity="getProxyStatusSeverity(data.proxy_id)"
                  class="status-tag"
                />
                <span v-else class="no-proxy-text">—</span>
              </template>
            </Column>

            <Column style="width: 50px">
              <template #body="{ data }">
                <Button
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  size="small"
                  @click="removeParsedAccount(data.temp_id)"
                />
              </template>
            </Column>
          </DataTable>

          <div v-else class="empty-table-message">
            <i class="pi pi-inbox"></i>
            <span>{{ t('accounts.importFlow.noAccountsYet') }}</span>
          </div>
        </div>

        <!-- Logs Toggle Button -->
        <div class="logs-toggle-row">
          <Button
            :label="showLogs ? 'Скрыть логи' : `Показать логи (${importLogs.length})`"
            :icon="showLogs ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"
            severity="secondary"
            text
            size="small"
            :disabled="importLogs.length === 0"
            @click="showLogs = !showLogs"
          />
          <Button
            v-if="importLogs.length > 0"
            icon="pi pi-trash"
            severity="secondary"
            text
            size="small"
            @click="importLogs = []; showLogs = false"
            v-tooltip.top="'Очистить логи'"
          />
        </div>

        <!-- Logs Panel -->
        <div v-if="showLogs && importLogs.length > 0" class="import-logs-panel">
          <div class="logs-content" ref="logsContainer">
            <div
              v-for="(log, index) in importLogs"
              :key="index"
              class="log-entry"
              :class="'log-' + log.type"
            >
              <span class="log-time">{{ log.time }}</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="import-action-buttons">
          <Button
            :label="t('accounts.importFlow.checkProxies')"
            icon="pi pi-wifi"
            class="action-btn action-btn-orange"
            :disabled="parsedAccounts.length === 0 || !allParsedHaveProxy || checkingProxies"
            :loading="checkingProxies"
            @click="checkParsedProxies"
          />
          <Button
            :label="t('accounts.importFlow.checkAccounts')"
            icon="pi pi-check-circle"
            class="action-btn action-btn-blue"
            :disabled="!canVerify || checkingProxies"
            :loading="verifying"
            @click="verifyParsedAccounts"
          />
          <Button
            :label="t('accounts.importFlow.saveToApp')"
            icon="pi pi-check"
            class="action-btn action-btn-green"
            :disabled="!canSave"
            :loading="saving"
            @click="saveVerifiedAccounts"
          />
        </div>
      </Dialog>

      <!-- Quick Proxy Add Dialog -->
      <Dialog
        v-model:visible="showQuickProxyDialog"
        :header="t('accounts.importFlow.addProxy')"
        modal
        :style="{ width: '450px' }"
        class="custom-dialog"
        @hide="resetQuickProxyDialog"
      >
        <div class="quick-proxy-content">
          <div class="form-field">
            <label class="form-label">{{ t('accounts.importFlow.proxyString') }}</label>
            <InputText
              v-model="quickProxyString"
              :placeholder="t('accounts.importFlow.proxyStringPlaceholder')"
              class="w-full font-mono"
              @keyup.enter="checkQuickProxy"
            />
            <small class="format-hint">socks5://user:pass@host:port {{ t('common.or') }} host:port:user:pass</small>
          </div>

          <!-- Check Result -->
          <div v-if="quickProxyResult" class="quick-proxy-result">
            <Tag
              :value="t(`proxy.status.${quickProxyResult.status}`)"
              :severity="quickProxyResult.status === 'working' ? 'success' : 'danger'"
            />
            <span v-if="quickProxyResult.ping_ms" class="result-ping">{{ quickProxyResult.ping_ms }}ms</span>
            <span v-if="quickProxyResult.geo" class="result-geo">{{ quickProxyResult.geo }}</span>
            <span v-if="quickProxyResult.error" class="result-error">{{ quickProxyResult.error }}</span>
          </div>

          <div class="dialog-actions">
            <Button
              :label="t('common.cancel')"
              severity="secondary"
              @click="showQuickProxyDialog = false"
            />
            <Button
              :label="t('common.check')"
              icon="pi pi-refresh"
              severity="secondary"
              :loading="quickProxyChecking"
              @click="checkQuickProxy"
            />
            <Button
              :label="t('common.add')"
              icon="pi pi-plus"
              :disabled="!quickProxyString.trim()"
              @click="addQuickProxy"
            />
          </div>
        </div>
      </Dialog>

      <!-- Create Group Dialog -->
      <Dialog
        v-model:visible="showGroupDialog"
        :header="t('groups.create')"
        modal
        :style="{ width: '400px' }"
        class="custom-dialog"
      >
        <div class="form-field">
          <label class="form-label">{{ t('groups.name') }}</label>
          <InputText
            v-model="newGroupName"
            :placeholder="t('groups.namePlaceholder')"
            class="w-full"
          />
        </div>
        <div class="form-field">
          <label class="form-label">{{ t('common.color') }}</label>
          <div class="color-picker">
            <div
              v-for="color in tagStore.presetColors"
              :key="color"
              class="color-option"
              :class="{ active: newGroupColor === color }"
              :style="{ background: color }"
              @click="newGroupColor = color"
            ></div>
          </div>
        </div>

        <template #footer>
          <Button :label="t('common.cancel')" severity="secondary" @click="showGroupDialog = false" />
          <Button :label="t('common.create')" icon="pi pi-check" @click="createGroup" />
        </template>
      </Dialog>

      <!-- Create Tag Dialog -->
      <Dialog
        v-model:visible="showTagDialog"
        :header="t('tags.create')"
        modal
        :style="{ width: '400px' }"
        class="custom-dialog"
      >
        <div class="form-field">
          <label class="form-label">{{ t('tags.name') }}</label>
          <InputText
            v-model="newTagName"
            :placeholder="t('tags.namePlaceholder')"
            class="w-full"
          />
        </div>
        <div class="form-field">
          <label class="form-label">{{ t('common.color') }}</label>
          <div class="color-picker">
            <div
              v-for="color in tagStore.presetColors"
              :key="color"
              class="color-option"
              :class="{ active: newTagColor === color }"
              :style="{ background: color }"
              @click="newTagColor = color"
            ></div>
          </div>
        </div>

        <template #footer>
          <Button :label="t('common.cancel')" severity="secondary" @click="showTagDialog = false" />
          <Button :label="t('common.create')" icon="pi pi-check" @click="createTag" />
        </template>
      </Dialog>

      <!-- Batch Check Dialog -->
      <Dialog
        v-model:visible="showBatchCheckDialog"
        :header="t('accounts.batchCheck.title')"
        modal
        :style="{ width: '400px' }"
        class="custom-dialog"
      >
        <div class="form-field">
          <p class="description">{{ t('accounts.batchCheck.description') }}</p>
          <p class="hint-text">{{ t('accounts.selected', { count: selectedIds.length }) }}</p>
        </div>
        <div class="form-field">
          <div class="checkbox-field">
            <Checkbox v-model="batchCheckSpamblock" inputId="checkSpamblock" binary />
            <label for="checkSpamblock" class="ml-2">{{ t('accounts.batchCheck.checkSpamblock') }}</label>
          </div>
          <p class="hint-text">{{ t('accounts.batchCheck.spamblockWarning') }}</p>
        </div>
        <div class="form-field">
          <label class="form-label">{{ t('accounts.batchCheck.maxConcurrent') }}: {{ batchCheckMaxConcurrent }}</label>
          <Slider v-model="batchCheckMaxConcurrent" :min="1" :max="10" class="w-full" />
        </div>

        <template #footer>
          <Button :label="t('common.cancel')" severity="secondary" @click="showBatchCheckDialog = false" />
          <Button
            :label="t('accounts.batchCheck.startCheck')"
            icon="pi pi-check"
            :loading="batchChecking"
            @click="checkBatchSelected"
          />
        </template>
      </Dialog>

      <!-- Add Account Dialog -->
      <AddAccountDialog
        v-model:visible="showAddAccountDialog"
        @added="handleAccountAdded"
      />

      <!-- 2FA Management Dialog -->
      <TwoFADialog
        v-model:visible="showTwoFADialog"
        :account="twoFAAccount"
        @updated="accountStore.fetchAccounts"
      />
    </div>
  </MainLayout>
</template>

<style scoped>
.accounts-page {
  height: 100%;
}

.accounts-layout {
  display: flex;
  gap: 24px;
  height: 100%;
}

/* Sidebar */
.groups-sidebar {
  width: 280px;
  flex-shrink: 0;
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 16px;
  overflow-y: auto;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sidebar-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.groups-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.group-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.group-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.group-item.active {
  background: rgba(168, 85, 247, 0.15);
}

.group-item .delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
}

.group-item:hover .delete-btn {
  opacity: 1;
}

.group-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
}

.group-info {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.group-name {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
}

.group-count {
  font-size: 12px;
  color: #6b7280;
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 8px;
  border-radius: 10px;
}

/* Tags */
.tags-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tag-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.tag-item.active {
  background: rgba(168, 85, 247, 0.15);
}

.tag-item .delete-btn {
  opacity: 0;
  margin-left: auto;
}

.tag-item:hover .delete-btn {
  opacity: 1;
}

.tag-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.tag-name {
  font-size: 13px;
  color: #d1d5db;
}

/* Main Content */
.main-content {
  flex: 1;
  min-width: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
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

/* Filters Bar */
.filters-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input {
  width: 280px;
}

.status-filter {
  width: 180px;
}

.bulk-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
  padding-left: 16px;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
}

.selection-count {
  font-size: 13px;
  color: #a855f7;
  font-weight: 500;
}

/* Table */
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
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(124, 58, 237, 0.1) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.empty-icon i {
  font-size: 32px;
  color: #a855f7;
}

.empty-text {
  color: #6b7280;
  margin-bottom: 20px;
  font-size: 15px;
}

.account-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.account-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 600;
  color: white;
}

.account-info {
  display: flex;
  flex-direction: column;
}

.account-name {
  font-weight: 500;
  color: #e5e7eb;
}

.account-phone {
  font-size: 12px;
  color: #6b7280;
}

.proxy-text {
  font-size: 13px;
  color: #9ca3af;
  font-family: monospace;
}

.group-text {
  font-size: 13px;
  color: #9ca3af;
}

.no-data {
  color: #4b5563;
  font-size: 13px;
}

.tags-cell {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.actions-cell {
  display: flex;
  gap: 4px;
}

/* Dialogs */
.form-field {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  font-size: 13px;
  color: #9ca3af;
  margin-bottom: 8px;
  font-weight: 500;
}

.placeholder-text {
  color: #6b7280;
}

.tab-content {
  padding: 20px 0;
}

.description {
  color: #9ca3af;
  margin-bottom: 16px;
  font-size: 14px;
}

.steps-list {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 20px;
  padding-left: 20px;
}

.steps-list li {
  margin-bottom: 8px;
}

.format-hint {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 16px;
}

.format-hint code {
  background: rgba(0, 0, 0, 0.3);
  padding: 2px 8px;
  border-radius: 4px;
  font-family: monospace;
}

/* Color Picker */
.color-picker {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.color-option {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s;
}

.color-option:hover {
  transform: scale(1.1);
}

.color-option.active {
  box-shadow: 0 0 0 2px #161616, 0 0 0 4px white;
}

/* Table styles */
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

:deep(.custom-table .p-datatable-tbody > tr.p-highlight) {
  background: rgba(168, 85, 247, 0.1);
}

:deep(.custom-dialog .p-dialog-header) {
  background: #161616;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.custom-dialog .p-dialog-content) {
  background: #161616;
}

:deep(.custom-dialog .p-dialog-footer) {
  background: #161616;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.p-tabview .p-tabview-nav) {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.06);
}

:deep(.p-tabview .p-tabview-nav li .p-tabview-nav-link) {
  background: transparent;
  border-color: transparent;
  color: #6b7280;
}

:deep(.p-tabview .p-tabview-nav li.p-highlight .p-tabview-nav-link) {
  color: #a855f7;
  border-color: #a855f7;
  background: transparent;
}

:deep(.p-tabview .p-tabview-panels) {
  background: transparent;
}

:deep(.p-checkbox .p-checkbox-box) {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.2);
}

:deep(.p-checkbox .p-checkbox-box.p-highlight) {
  background: #a855f7;
  border-color: #a855f7;
}

/* Drop Zone */
.drop-zone {
  border: 2px dashed rgba(168, 85, 247, 0.3);
  border-radius: 16px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(168, 85, 247, 0.03);
  margin-bottom: 16px;
}

.drop-zone:hover {
  border-color: rgba(168, 85, 247, 0.5);
  background: rgba(168, 85, 247, 0.06);
}

.drop-zone-active {
  border-color: #a855f7;
  background: rgba(168, 85, 247, 0.1);
}

.drop-zone-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.drop-zone-content {
  pointer-events: none;
}

.drop-zone-icon {
  font-size: 40px;
  color: #a855f7;
  margin-bottom: 12px;
}

.drop-zone-title {
  font-size: 16px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 4px;
}

.drop-zone-hint {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 12px;
}

.drop-zone-buttons {
  display: flex;
  gap: 16px;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 16px;
  pointer-events: auto;
}

.drop-zone-buttons :deep(.p-button) {
  padding: 12px 24px;
}

.hidden-input {
  display: none;
}

/* Pending Files */
.pending-files {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 16px;
}

.pending-files-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: #9ca3af;
}

.pending-files-list {
  max-height: 150px;
  overflow-y: auto;
}

.pending-file {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  margin-bottom: 4px;
}

.pending-file i {
  color: #a855f7;
  font-size: 14px;
}

.pending-file .file-name {
  flex: 1;
  font-size: 13px;
  color: #e5e7eb;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pending-file .file-size {
  font-size: 11px;
  color: #6b7280;
}

/* Session String Section */
.session-string-section {
  margin-top: 8px;
}

.divider-text {
  text-align: center;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 12px;
  position: relative;
}

.divider-text::before,
.divider-text::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 35%;
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
}

.divider-text::before {
  left: 0;
}

.divider-text::after {
  right: 0;
}

/* Batch Check Dialog */
.checkbox-field {
  display: flex;
  align-items: center;
}

.hint-text {
  font-size: 12px;
  color: #f59e0b;
  margin-top: 4px;
}

:deep(.p-slider .p-slider-handle) {
  background: #a855f7;
  border-color: #a855f7;
}

:deep(.p-slider .p-slider-range) {
  background: #a855f7;
}

/* Required label */
.required-label::after {
  content: '';
  color: #ef4444;
}

/* Proxy required hint */
.proxy-required-hint {
  display: block;
  color: #f59e0b;
  font-size: 12px;
  margin-top: 8px;
}

.no-proxy-warning {
  display: block;
  color: #ef4444;
  font-size: 12px;
  margin-top: 4px;
}

/* Proxy option in dropdown */
.proxy-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.proxy-type {
  font-size: 11px;
  color: #6b7280;
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}

/* Inline Proxy Form */
.proxy-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.proxy-header .form-label {
  margin-bottom: 0;
}

.inline-proxy-form {
  background: rgba(168, 85, 247, 0.05);
  border: 1px solid rgba(168, 85, 247, 0.15);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

.proxy-form-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.proxy-form-row:last-of-type {
  margin-bottom: 0;
}

.proxy-form-field {
  flex: 1;
}

.proxy-form-field.type-field {
  flex: 0.8;
}

.proxy-form-field.host-field {
  flex: 1.5;
}

.proxy-form-field.port-field {
  flex: 0.7;
}

.form-label-small {
  display: block;
  font-size: 11px;
  color: #9ca3af;
  margin-bottom: 4px;
  font-weight: 500;
}

.proxy-mode-toggle {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.proxy-mode-toggle :deep(.p-button) {
  flex: 1;
}

.proxy-string-input {
  display: flex;
  flex-direction: column;
}

.proxy-format-hint {
  color: #6b7280;
  font-size: 11px;
  margin-top: 4px;
}

/* Import Preview Styles */
.import-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.import-stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #9ca3af;
}

.stat-item i {
  font-size: 14px;
}

.stat-valid {
  color: #22c55e;
}

.stat-invalid {
  color: #ef4444;
}

.stat-pending {
  color: #6b7280;
}

.bulk-proxy-section {
  margin-bottom: 16px;
  padding: 12px;
  background: rgba(168, 85, 247, 0.05);
  border: 1px solid rgba(168, 85, 247, 0.15);
  border-radius: 12px;
}

.bulk-proxy-section .form-label {
  margin-bottom: 8px;
}

.bulk-proxy-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.parsed-accounts-table {
  margin-bottom: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  overflow: hidden;
}

.import-table {
  font-size: 13px;
}

:deep(.import-table .p-datatable-tbody > tr > td) {
  padding: 10px 12px;
}

.import-proxy-dropdown {
  min-width: 160px;
}

:deep(.import-proxy-dropdown .p-dropdown-label) {
  font-size: 12px;
  padding: 6px 10px;
}

.source-file {
  font-size: 12px;
  color: #6b7280;
  font-family: monospace;
}

.account-preview {
  font-size: 13px;
  color: #e5e7eb;
}

.proxy-text-small {
  font-size: 12px;
  font-family: monospace;
}

.error-text {
  font-size: 12px;
  color: #ef4444;
  cursor: help;
}

.import-actions {
  display: flex;
  gap: 12px;
}

.import-actions .p-button {
  justify-content: center;
}

/* Unified Import Dialog Styles - base styles in main.css */
.upload-cards {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  margin-bottom: 16px;
}

.proxy-selection-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.proxy-main-dropdown {
  flex: 1;
}

.proxy-dropdown-value {
  display: flex;
  align-items: center;
  gap: 8px;
}

.proxy-dropdown-value i {
  color: #a855f7;
}

:deep(.import-table-unified .p-datatable-tbody > tr > td) {
  padding: 10px 12px;
}

.table-proxy-dropdown {
  min-width: 150px;
}

:deep(.table-proxy-dropdown .p-dropdown-label) {
  font-size: 12px;
  padding: 6px 10px;
}

.proxy-value-small {
  font-size: 11px;
  font-family: monospace;
}

.status-tag {
  font-size: 11px;
}

.no-proxy-text {
  color: #6b7280;
}

.format-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #9ca3af;
  font-size: 12px;
}

.format-cell i {
  color: #6b7280;
}

.import-action-buttons {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

:deep(.import-dialog-unified .p-dialog-content) {
  padding: 20px 24px !important;
  background: var(--color-bg-elevated, #18181b) !important;
}

:deep(.import-dialog-unified .p-dialog-header) {
  background: var(--color-bg-elevated, #18181b) !important;
}

:deep(.light .import-dialog-unified .p-dialog-content),
:deep(.light .import-dialog-unified .p-dialog-header) {
  background: #ffffff !important;
}

/* Logs Toggle Row */
.logs-toggle-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

/* Import Logs Panel */
.import-logs-panel {
  margin-bottom: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.2);
}

.logs-content {
  max-height: 150px;
  overflow-y: auto;
  padding: 8px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 11px;
}

.log-entry {
  display: flex;
  gap: 8px;
  padding: 3px 6px;
  border-radius: 4px;
  margin-bottom: 2px;
}

.log-entry:hover {
  background: rgba(255, 255, 255, 0.03);
}

.log-time {
  color: #6b7280;
  flex-shrink: 0;
}

.log-message {
  word-break: break-word;
}

.log-info .log-message {
  color: #9ca3af;
}

.log-success .log-message {
  color: #22c55e;
}

.log-error .log-message {
  color: #ef4444;
}

.log-warn .log-message {
  color: #f59e0b;
}

/* Light theme logs */
.light .import-logs-panel {
  background: rgba(0, 0, 0, 0.02);
  border-color: rgba(0, 0, 0, 0.1);
}

.light .logs-header {
  background: rgba(0, 0, 0, 0.02);
  border-color: rgba(0, 0, 0, 0.06);
}

.light .log-entry:hover {
  background: rgba(0, 0, 0, 0.03);
}

.light .logs-toggle-row {
  border-color: rgba(0, 0, 0, 0.1);
}

/* Quick Proxy Dialog */
.quick-proxy-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.quick-proxy-result {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.result-ping {
  color: #22c55e;
  font-size: 13px;
}

.result-geo {
  color: #9ca3af;
  font-size: 13px;
}

.result-error {
  color: #ef4444;
  font-size: 13px;
}

.proxy-status-tag {
  font-size: 10px;
  padding: 2px 6px;
}

.light .quick-proxy-result {
  background: rgba(0, 0, 0, 0.02);
  border-color: rgba(0, 0, 0, 0.06);
}
</style>
