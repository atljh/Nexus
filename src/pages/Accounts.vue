<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
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
const importing = ref(false)
const batchChecking = ref(false)
const selectedProxy = ref<number | null>(null)
const sessionStringInput = ref('')
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
// Inline proxy creation
const showInlineProxyForm = ref(false)
const inlineProxyLoading = ref(false)
const newProxy = ref({
  type: 'socks5' as 'socks5' | 'socks4' | 'http' | 'https',
  host: '',
  port: '',
  username: '',
  password: ''
})
const proxyTypes = [
  { label: 'SOCKS5', value: 'socks5' },
  { label: 'SOCKS4', value: 'socks4' },
  { label: 'HTTP', value: 'http' },
  { label: 'HTTPS', value: 'https' }
]
const proxyString = ref('')
const proxyInputMode = ref<'form' | 'string'>('string')

// New Import Flow State
const importStep = ref<'upload' | 'preview'>('upload')
const parsedAccounts = ref<ParsedAccount[]>([])
const parseErrors = ref<{ file: string; error: string }[]>([])
const parsing = ref(false)
const verifying = ref(false)
const saving = ref(false)
const bulkProxyId = ref<number | null>(null)

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

const canVerify = computed(() =>
  allParsedHaveProxy.value &&
  !verifying.value &&
  parsedAccounts.value.some(a => a.status === 'pending')
)

const canSave = computed(() =>
  parsedAccounts.value.some(a => a.status === 'valid') && !saving.value
)

const validAccountsCount = computed(() =>
  parsedAccounts.value.filter(a => a.status === 'valid').length
)

const invalidAccountsCount = computed(() =>
  parsedAccounts.value.filter(a => a.status === 'invalid').length
)

const pendingAccountsCount = computed(() =>
  parsedAccounts.value.filter(a => a.status === 'pending').length
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
    // Filter tdata-relevant files
    const files = Array.from(input.files)
    const tdataRelevant = files.filter(f => {
      const path = f.webkitRelativePath || f.name
      // Include key_data, key_datas, and D877F783D5D3EF8C* files
      return path.includes('key_data') ||
             path.includes('key_datas') ||
             /D877F783D5D3EF8C[0-9A-F]*/.test(path) ||
             /[0-9A-F]{16}/.test(f.name)
    })

    if (tdataRelevant.length > 0) {
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
    // If we already have parsed accounts from tdata, append to them
    if (files.length > 0) {
      const existingAccounts = [...parsedAccounts.value]
      await addFiles(files)
      // Merge results if we had tdata accounts
      if (existingAccounts.length > 0 && parsedAccounts.value.length > 0) {
        parsedAccounts.value = [...existingAccounts, ...parsedAccounts.value]
      }
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

function getFileIcon(filename: string): string {
  if (filename.endsWith('.zip')) return 'pi pi-file-import'
  if (filename.endsWith('.json')) return 'pi pi-file'
  if (filename.endsWith('.session')) return 'pi pi-key'
  return 'pi pi-file'
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// New Import Flow Methods
async function parseTdataFolder() {
  if (tdataFiles.value.length === 0) return

  parsing.value = true
  parseErrors.value = []

  try {
    const result = await accountStore.parseTdataFiles(tdataFiles.value)

    parsedAccounts.value = result.accounts.map((a: any) => ({
      ...a,
      status: 'pending' as const,
      proxy_id: undefined
    }))

    parseErrors.value = result.errors || []

    if (parsedAccounts.value.length > 0) {
      importStep.value = 'preview'
    }

    if (parseErrors.value.length > 0) {
      parseErrors.value.forEach(err => {
        toast.add({
          severity: 'error',
          summary: err.file,
          detail: err.error,
          life: 5000
        })
      })
    }

    if (parsedAccounts.value.length === 0) {
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
    tdataFiles.value = []
  }
}

async function parseFiles() {
  if (pendingFiles.value.length === 0) return

  parsing.value = true
  parseErrors.value = []

  try {
    const sessionFiles = pendingFiles.value.filter(f => f.name.endsWith('.session'))
    const jsonFiles = pendingFiles.value.filter(f => f.name.endsWith('.json'))
    const zipFiles = pendingFiles.value.filter(f => f.name.endsWith('.zip'))
    const tdataFile = zipFiles[0] // Only one tdata at a time

    const result = await accountStore.parseImportFiles(sessionFiles, jsonFiles, tdataFile)

    parsedAccounts.value = result.accounts.map(a => ({
      ...a,
      status: 'pending' as const,
      proxy_id: undefined
    }))

    parseErrors.value = result.errors || []

    if (parsedAccounts.value.length > 0) {
      importStep.value = 'preview'
    }

    if (parseErrors.value.length > 0) {
      parseErrors.value.forEach(err => {
        toast.add({
          severity: 'error',
          summary: err.file,
          detail: err.error,
          life: 5000
        })
      })
    }

    if (parsedAccounts.value.length === 0) {
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

function setAccountProxy(tempId: string, proxyId: number | null) {
  const account = parsedAccounts.value.find(a => a.temp_id === tempId)
  if (account) {
    account.proxy_id = proxyId || undefined
  }
}

async function verifyParsedAccounts() {
  if (!allParsedHaveProxy.value) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('accounts.importFlow.assignProxyFirst'),
      life: 3000
    })
    return
  }

  verifying.value = true

  // Mark all pending as verifying
  parsedAccounts.value.forEach(a => {
    if (a.status === 'pending') {
      a.status = 'verifying'
    }
  })

  try {
    const accountsToVerify = parsedAccounts.value
      .filter(a => a.status === 'verifying')
      .map(a => ({
        temp_id: a.temp_id,
        session_string: a.session_string,
        proxy_id: a.proxy_id!
      }))

    const result = await accountStore.verifyParsedAccounts(accountsToVerify)

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
      }
    })

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.importFlow.verifyComplete', { valid: result.total_valid, invalid: result.total_invalid }),
      life: 5000
    })
  } catch (error: any) {
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

  try {
    const result = await accountStore.saveParsedAccounts(validAccounts)

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.importFlow.savedCount', { count: result.total_saved }),
      life: 3000
    })

    // Show errors if any
    if (result.errors?.length > 0) {
      result.errors.forEach(err => {
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
  selectedProxy.value = null
  sessionStringInput.value = ''
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

function translateError(error?: string): string {
  if (!error) return ''

  // Check for known error codes
  const errorMap: Record<string, string> = {
    'banned': t('accounts.errors.banned'),
    'deactivated': t('accounts.errors.deactivated'),
    'restricted': t('accounts.errors.restricted'),
    'frozen': t('accounts.errors.frozen'),
    'auth_key_duplicated': t('accounts.errors.authKeyDuplicated'),
    'session_expired': t('accounts.errors.sessionExpired'),
    'session_revoked': t('accounts.errors.sessionRevoked'),
    'flood_wait': t('accounts.errors.floodWait'),
    'connection_failed': t('accounts.errors.connectionFailed'),
    'timeout': t('accounts.errors.timeout'),
  }

  // Direct match
  if (errorMap[error]) {
    return errorMap[error]
  }

  // Check for prefixed errors like "flood_wait:60" or "restricted:reason"
  if (error.startsWith('flood_wait:')) {
    const seconds = error.split(':')[1]
    return t('accounts.errors.floodWaitSeconds', { seconds })
  }

  if (error.startsWith('restricted:')) {
    const reason = error.substring(11)
    return `${t('accounts.errors.restricted')}${reason ? ': ' + reason : ''}`
  }

  // Check for unknown:message format
  if (error.startsWith('unknown:')) {
    return error.substring(8)
  }

  // Return as-is if no translation found
  return error
}

function removeParsedAccount(tempId: string) {
  parsedAccounts.value = parsedAccounts.value.filter(a => a.temp_id !== tempId)
  if (parsedAccounts.value.length === 0) {
    backToUpload()
  }
}


async function importSessionString() {
  if (!selectedProxy.value) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('accounts.importDialog.proxyRequired'),
      life: 3000
    })
    return
  }

  if (!sessionStringInput.value.trim()) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('accounts.messages.enterSessionString'),
      life: 3000
    })
    return
  }

  importing.value = true
  try {
    await accountStore.importSessionString(
      sessionStringInput.value.trim(),
      selectedProxy.value || undefined
    )
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.messages.importSuccess'),
      life: 3000
    })
    sessionStringInput.value = ''
    showImportDialog.value = false
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.importFailed'),
      detail: error.message,
      life: 5000
    })
  } finally {
    importing.value = false
  }
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

async function createInlineProxy() {
  if (!newProxy.value.host || !newProxy.value.port) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('proxy.messages.enterHostPort'),
      life: 3000
    })
    return
  }

  inlineProxyLoading.value = true
  try {
    const created = await proxyStore.createProxy({
      type: newProxy.value.type,
      host: newProxy.value.host.trim(),
      port: parseInt(newProxy.value.port),
      username: newProxy.value.username.trim() || undefined,
      password: newProxy.value.password || undefined
    })

    // Check the proxy
    await proxyStore.checkProxy(created.id)

    // Auto-select if working
    const proxy = proxyStore.getById(created.id)
    if (proxy?.status === 'working') {
      selectedProxy.value = created.id
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('proxy.messages.added'),
        life: 3000
      })
    } else {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('proxy.messages.proxyInvalid'),
        life: 3000
      })
    }

    // Reset form and close
    resetInlineProxyForm()
    showInlineProxyForm.value = false
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.addFailed'),
      life: 5000
    })
  } finally {
    inlineProxyLoading.value = false
  }
}

function resetInlineProxyForm() {
  newProxy.value = {
    type: 'socks5',
    host: '',
    port: '',
    username: '',
    password: ''
  }
  proxyString.value = ''
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
        password = parts.slice(3).join(':') // Password may contain colons
      }
    }
  }

  if (!host || !port || isNaN(port)) return null

  return { type, host, port, username, password }
}

async function createProxyFromString() {
  const parsed = parseProxyString(proxyString.value)
  if (!parsed) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('proxy.messages.invalidProxyFormat'),
      life: 3000
    })
    return
  }

  inlineProxyLoading.value = true
  try {
    const created = await proxyStore.createProxy({
      type: parsed.type,
      host: parsed.host,
      port: parsed.port,
      username: parsed.username,
      password: parsed.password
    })

    // Check the proxy
    await proxyStore.checkProxy(created.id)

    // Auto-select if working
    const proxy = proxyStore.getById(created.id)
    if (proxy?.status === 'working') {
      selectedProxy.value = created.id
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('proxy.messages.added'),
        life: 3000
      })
    } else {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('proxy.messages.proxyInvalid'),
        life: 3000
      })
    }

    // Reset form and close
    resetInlineProxyForm()
    showInlineProxyForm.value = false
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.addFailed'),
      life: 5000
    })
  } finally {
    inlineProxyLoading.value = false
  }
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
        :style="{ width: importStep === 'preview' ? '900px' : '560px' }"
        :closable="!parsing && !verifying && !saving"
        class="custom-dialog"
        @hide="resetImportDialog"
      >
        <!-- Step 1: Upload Files -->
        <template v-if="importStep === 'upload'">
          <ProgressBar v-if="parsing" mode="indeterminate" style="height: 4px" class="mb-4" />

          <!-- Drag & Drop Zone -->
          <div
            class="drop-zone"
            :class="{ 'drop-zone-active': isDragging, 'drop-zone-disabled': parsing }"
            @dragenter.prevent="isDragging = true"
            @dragover.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @drop.prevent="handleFileDrop"
            @click="openFileSelector"
          >
            <div class="drop-zone-content">
              <i class="pi pi-cloud-upload drop-zone-icon"></i>
              <p class="drop-zone-title">{{ t('accounts.dropZone.dropTitle') }}</p>
              <p class="drop-zone-hint">{{ t('accounts.dropZone.dropHint') }}</p>
              <div class="drop-zone-formats">
                <span class="format-badge">.session + .json</span>
                <span class="format-badge">tdata {{ t('accounts.importFlow.folder') }}</span>
              </div>
            </div>
            <input
              ref="fileInput"
              type="file"
              multiple
              accept=".zip,.json,.session"
              class="hidden-input"
              @change="handleFileSelect"
            />
          </div>

          <!-- TData Folder Button -->
          <div class="tdata-folder-section">
            <div class="divider-text">{{ t('accounts.importFlow.orSelectTdata') }}</div>
            <Button
              :label="t('accounts.importFlow.selectTdataFolder')"
              icon="pi pi-folder-open"
              severity="secondary"
              :loading="parsing"
              @click.stop="openFolderSelector"
              class="w-full"
            />
            <input
              ref="folderInput"
              type="file"
              webkitdirectory
              directory
              class="hidden-input"
              @change="handleFolderSelect"
            />
          </div>

          <!-- Selected Files Preview (shown during parsing) -->
          <div v-if="pendingFiles.length > 0 && parsing" class="pending-files">
            <div class="pending-files-header">
              <span>{{ t('accounts.importFlow.parsing') }} ({{ pendingFiles.length }})</span>
            </div>
            <div class="pending-files-list">
              <div v-for="(file, index) in pendingFiles" :key="index" class="pending-file">
                <i :class="getFileIcon(file.name)"></i>
                <span class="file-name">{{ file.name }}</span>
                <span class="file-size">{{ formatFileSize(file.size) }}</span>
              </div>
            </div>
          </div>

          <!-- Session String Input -->
          <div class="session-string-section">
            <div class="divider-text">{{ t('accounts.dropZone.orPasteSession') }}</div>

            <!-- Proxy Selection for Session String -->
            <div class="form-field">
              <div class="proxy-header">
                <label class="form-label required-label">{{ t('accounts.importDialog.useProxy') }} *</label>
                <Button
                  :label="showInlineProxyForm ? t('common.cancel') : t('accounts.importDialog.addNewProxy')"
                  :icon="showInlineProxyForm ? 'pi pi-times' : 'pi pi-plus'"
                  severity="secondary"
                  text
                  size="small"
                  @click="showInlineProxyForm = !showInlineProxyForm; if (!showInlineProxyForm) resetInlineProxyForm()"
                />
              </div>

              <!-- Inline Proxy Form -->
              <div v-if="showInlineProxyForm" class="inline-proxy-form">
                <div class="proxy-mode-toggle">
                  <Button
                    :label="t('accounts.importDialog.proxyString')"
                    :severity="proxyInputMode === 'string' ? 'primary' : 'secondary'"
                    :outlined="proxyInputMode !== 'string'"
                    size="small"
                    @click="proxyInputMode = 'string'"
                  />
                  <Button
                    :label="t('accounts.importDialog.proxyForm')"
                    :severity="proxyInputMode === 'form' ? 'primary' : 'secondary'"
                    :outlined="proxyInputMode !== 'form'"
                    size="small"
                    @click="proxyInputMode = 'form'"
                  />
                </div>

                <div v-if="proxyInputMode === 'string'" class="proxy-string-input">
                  <div class="proxy-form-field">
                    <label class="form-label-small">{{ t('accounts.importDialog.proxyStringLabel') }}</label>
                    <InputText
                      v-model="proxyString"
                      :placeholder="t('accounts.importDialog.proxyStringPlaceholderFull')"
                      class="w-full font-mono"
                      @keyup.enter="createProxyFromString"
                    />
                  </div>
                  <small class="proxy-format-hint">{{ t('accounts.importDialog.proxyStringFormats') }}</small>
                  <Button
                    :label="t('accounts.importDialog.addAndCheck')"
                    icon="pi pi-check"
                    :loading="inlineProxyLoading"
                    :disabled="!proxyString.trim()"
                    @click="createProxyFromString"
                    class="w-full mt-2"
                    size="small"
                  />
                </div>

                <div v-else>
                  <div class="proxy-form-row">
                    <div class="proxy-form-field type-field">
                      <label class="form-label-small">{{ t('proxy.addDialog.type') }}</label>
                      <Dropdown
                        v-model="newProxy.type"
                        :options="proxyTypes"
                        optionLabel="label"
                        optionValue="value"
                        class="w-full"
                      />
                    </div>
                    <div class="proxy-form-field host-field">
                      <label class="form-label-small">{{ t('proxy.addDialog.host') }}</label>
                      <InputText
                        v-model="newProxy.host"
                        placeholder="127.0.0.1"
                        class="w-full"
                      />
                    </div>
                    <div class="proxy-form-field port-field">
                      <label class="form-label-small">{{ t('proxy.addDialog.port') }}</label>
                      <InputText
                        v-model="newProxy.port"
                        placeholder="1080"
                        class="w-full"
                      />
                    </div>
                  </div>
                  <div class="proxy-form-row">
                    <div class="proxy-form-field">
                      <label class="form-label-small">{{ t('proxy.addDialog.username') }} ({{ t('common.optional') }})</label>
                      <InputText
                        v-model="newProxy.username"
                        :placeholder="t('proxy.addDialog.username')"
                        class="w-full"
                      />
                    </div>
                    <div class="proxy-form-field">
                      <label class="form-label-small">{{ t('proxy.addDialog.password') }} ({{ t('common.optional') }})</label>
                      <InputText
                        v-model="newProxy.password"
                        type="password"
                        :placeholder="t('proxy.addDialog.password')"
                        class="w-full"
                      />
                    </div>
                  </div>
                  <Button
                    :label="t('accounts.importDialog.addAndCheck')"
                    icon="pi pi-check"
                    :loading="inlineProxyLoading"
                    @click="createInlineProxy"
                    class="w-full mt-2"
                    size="small"
                  />
                </div>
              </div>

              <Dropdown
                v-if="!showInlineProxyForm"
                v-model="selectedProxy"
                :options="proxyStore.workingProxies"
                optionLabel="host"
                optionValue="id"
                :placeholder="t('accounts.importDialog.selectProxy')"
                class="w-full"
              >
                <template #value="{ value }">
                  <span v-if="value">
                    {{ proxyStore.getById(value)?.host }}:{{ proxyStore.getById(value)?.port }}
                  </span>
                  <span v-else class="placeholder-text">{{ t('accounts.importDialog.selectProxy') }}</span>
                </template>
                <template #option="{ option }">
                  <div class="proxy-option">
                    <span>{{ option.host }}:{{ option.port }}</span>
                    <span class="proxy-type">{{ option.type }}</span>
                  </div>
                </template>
              </Dropdown>
            </div>

            <div class="form-field mb-0">
              <InputText
                v-model="sessionStringInput"
                :placeholder="t('accounts.sessionString.placeholder')"
                class="w-full font-mono"
                :disabled="importing || !selectedProxy"
                @keyup.enter="importSessionString"
              />
              <small v-if="!selectedProxy" class="proxy-required-hint mt-2">
                {{ t('accounts.importDialog.proxyRequired') }}
              </small>
            </div>
          </div>
        </template>

        <!-- Step 2: Preview & Verify Accounts -->
        <template v-else-if="importStep === 'preview'">
          <div class="import-preview-header">
            <Button
              icon="pi pi-arrow-left"
              :label="t('common.back')"
              severity="secondary"
              text
              @click="backToUpload"
            />
            <div class="import-stats">
              <span class="stat-item">
                <i class="pi pi-list"></i>
                {{ t('accounts.importFlow.total') }}: {{ parsedAccounts.length }}
              </span>
              <span v-if="validAccountsCount > 0" class="stat-item stat-valid">
                <i class="pi pi-check-circle"></i>
                {{ t('accounts.importFlow.valid') }}: {{ validAccountsCount }}
              </span>
              <span v-if="invalidAccountsCount > 0" class="stat-item stat-invalid">
                <i class="pi pi-times-circle"></i>
                {{ t('accounts.importFlow.invalid') }}: {{ invalidAccountsCount }}
              </span>
              <span v-if="pendingAccountsCount > 0" class="stat-item stat-pending">
                <i class="pi pi-clock"></i>
                {{ t('accounts.importFlow.pending') }}: {{ pendingAccountsCount }}
              </span>
            </div>
          </div>

          <!-- Bulk Proxy Assignment -->
          <div class="bulk-proxy-section">
            <label class="form-label">{{ t('accounts.importFlow.assignProxyToAll') }}</label>
            <div class="bulk-proxy-row">
              <Dropdown
                v-model="bulkProxyId"
                :options="proxyStore.workingProxies"
                optionLabel="host"
                optionValue="id"
                :placeholder="t('accounts.importDialog.selectProxy')"
                class="flex-1"
              >
                <template #value="{ value }">
                  <span v-if="value">
                    {{ proxyStore.getById(value)?.host }}:{{ proxyStore.getById(value)?.port }}
                  </span>
                  <span v-else class="placeholder-text">{{ t('accounts.importDialog.selectProxy') }}</span>
                </template>
                <template #option="{ option }">
                  <div class="proxy-option">
                    <span>{{ option.host }}:{{ option.port }}</span>
                    <span class="proxy-type">{{ option.type }}</span>
                  </div>
                </template>
              </Dropdown>
              <Button
                :label="t('accounts.importFlow.applyToAll')"
                icon="pi pi-check"
                severity="secondary"
                :disabled="!bulkProxyId"
                @click="assignBulkProxy"
              />
            </div>
          </div>

          <!-- Parsed Accounts Table -->
          <div class="parsed-accounts-table">
            <DataTable
              :value="parsedAccounts"
              :loading="verifying"
              scrollable
              scrollHeight="350px"
              class="custom-table import-table"
            >
              <Column :header="t('accounts.importFlow.sourceFile')" style="min-width: 150px">
                <template #body="{ data }">
                  <span class="source-file">{{ data.source_file || '—' }}</span>
                </template>
              </Column>

              <Column :header="t('accounts.account')" style="min-width: 180px">
                <template #body="{ data }">
                  <div class="account-preview">
                    <span v-if="data.username">@{{ data.username }}</span>
                    <span v-else-if="data.phone">{{ data.phone }}</span>
                    <span v-else-if="data.telegram_id">ID: {{ data.telegram_id }}</span>
                    <span v-else class="no-data">{{ t('accounts.importFlow.unknown') }}</span>
                  </div>
                </template>
              </Column>

              <Column :header="t('accounts.proxy')" style="min-width: 200px">
                <template #body="{ data }">
                  <Dropdown
                    :model-value="data.proxy_id"
                    :options="proxyStore.workingProxies"
                    optionLabel="host"
                    optionValue="id"
                    :placeholder="t('accounts.importFlow.selectProxy')"
                    class="w-full import-proxy-dropdown"
                    @update:model-value="setAccountProxy(data.temp_id, $event)"
                  >
                    <template #value="{ value }">
                      <span v-if="value" class="proxy-text-small">
                        {{ proxyStore.getById(value)?.host }}:{{ proxyStore.getById(value)?.port }}
                      </span>
                      <span v-else class="placeholder-text">{{ t('accounts.importFlow.selectProxy') }}</span>
                    </template>
                    <template #option="{ option }">
                      <div class="proxy-option">
                        <span>{{ option.host }}:{{ option.port }}</span>
                        <span class="proxy-type">{{ option.type }}</span>
                      </div>
                    </template>
                  </Dropdown>
                </template>
              </Column>

              <Column :header="t('common.status')" style="min-width: 120px">
                <template #body="{ data }">
                  <Tag
                    :value="t(`accounts.importFlow.status.${data.status}`)"
                    :severity="getImportStatusSeverity(data.status)"
                  />
                </template>
              </Column>

              <Column :header="t('accounts.importFlow.error')" style="min-width: 150px">
                <template #body="{ data }">
                  <span v-if="data.error" class="error-text" v-tooltip.top="translateError(data.error)">
                    {{ translateError(data.error) }}
                  </span>
                  <span v-else class="no-data">—</span>
                </template>
              </Column>

              <Column style="width: 60px">
                <template #body="{ data }">
                  <Button
                    icon="pi pi-trash"
                    severity="danger"
                    text
                    rounded
                    size="small"
                    :aria-label="t('common.delete')"
                    @click="removeParsedAccount(data.temp_id)"
                  />
                </template>
              </Column>
            </DataTable>
          </div>

          <!-- Action Buttons -->
          <div class="import-actions">
            <Button
              :label="t('accounts.importFlow.verifyAll')"
              icon="pi pi-refresh"
              :loading="verifying"
              :disabled="!canVerify"
              @click="verifyParsedAccounts"
              class="flex-1"
            />
            <Button
              :label="t('accounts.importFlow.saveValid', { count: validAccountsCount })"
              icon="pi pi-save"
              :loading="saving"
              :disabled="!canSave"
              @click="saveVerifiedAccounts"
              class="flex-1"
            />
          </div>
          <small v-if="!allParsedHaveProxy" class="proxy-required-hint">
            {{ t('accounts.importFlow.assignProxyFirst') }}
          </small>
        </template>
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

.drop-zone-formats {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}

.format-badge {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.06);
  color: #9ca3af;
  font-family: monospace;
}

.hidden-input {
  display: none;
}

.tdata-folder-section {
  margin-top: 16px;
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
</style>
