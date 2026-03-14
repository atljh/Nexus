<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick, defineAsyncComponent } from 'vue'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAccountStore, useProxyStore, useGroupStore, useTagStore } from '@/stores'
import { useDebouncedRef } from '@/composables'
import { countryFlag } from '@/utils/formatters'
import type { Account, AccountStatus, BulkAction } from '@/types'

// Dialog components
// Lazy-load heavy dialog components for faster initial render
const TwoFADialog = defineAsyncComponent(() => import('@/components/accounts/TwoFADialog.vue'))
const AddAccountDialog = defineAsyncComponent(() => import('@/components/accounts/AddAccountDialog.vue'))
const WebViewer = defineAsyncComponent(() => import('@/components/accounts/WebViewer.vue'))
const ProfileEditDialog = defineAsyncComponent(() => import('@/components/accounts/ProfileEditDialog.vue'))

import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import MultiSelect from 'primevue/multiselect'
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

const { t, locale } = useI18n()
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
  // From JSON metadata
  api_id?: number
  api_hash?: string
  device_fingerprint?: Record<string, any>
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
const showWebViewer = ref(false)
const webViewerAccount = ref<Account | null>(null)
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
// Bulk 2FA state
const showBulk2FADialog = ref(false)
const bulk2FAPassword = ref('')
const bulk2FAHint = ref('')
const bulk2FALoading = ref(false)
// Profile edit state
const showProfileDialog = ref(false)
const profileAccount = ref<Account | null>(null)
// Bulk profile state
const showBulkProfileDialog = ref(false)
const bulkProfileMode = ref<'manual' | 'auto'>('auto')
const bulkProfileFirstName = ref('')
const bulkProfileLastName = ref('')
const bulkProfileBio = ref('')
const bulkProfileGender = ref<'male' | 'female' | undefined>(undefined)
const bulkProfileLoading = ref(false)
// Bulk terminate state
const bulkTerminateLoading = ref(false)
// Bulk proxy check state
const bulkProxyChecking = ref(false)
const checkingProxyIds = ref<Set<number>>(new Set())

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

// Proxy pool
const showProxyPool = ref(false)
const proxyPoolText = ref('')
const distributingPool = ref(false)

const proxyPoolCount = computed(() => {
  if (!proxyPoolText.value.trim()) return 0
  return proxyPoolText.value.trim().split('\n').filter(line => line.trim()).length
})

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
// Bridge: DataTable expects array of row objects, store holds array of IDs
const selectedIdSet = computed(() => new Set(accountStore.selectedIds))
const selectedRows = computed({
  get: () => accountStore.filteredAccounts.filter(a => selectedIdSet.value.has(a.id)),
  set: (rows: Account[]) => {
    accountStore.selectedIds = rows.map(r => r.id)
  }
})

const selectedIds = computed({
  get: () => accountStore.selectedIds,
  set: (val) => {
    accountStore.selectedIds = val
  }
})

const hasSelection = computed(() => selectedIds.value.length > 0)
const allSelected = computed(() =>
  accountStore.filteredAccounts.length > 0 &&
  selectedIds.value.length === accountStore.filteredAccounts.length
)

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


const proxyFilterOptions = computed(() =>
  proxyStore.proxies.map(p => ({
    label: `${p.host}:${p.port}`,
    value: p.id
  }))
)

const statusOptions = computed(() => [
  { label: t('accounts.allStatuses'), value: null },
  { label: t('accounts.status.valid'), value: 'valid' },
  { label: t('accounts.status.invalid'), value: 'invalid' },
  { label: t('accounts.status.banned'), value: 'banned' },
  { label: t('accounts.status.muted'), value: 'muted' },
  { label: t('accounts.status.spamblock'), value: 'spamblock' },
  { label: t('accounts.status.frozen'), value: 'frozen' },
  { label: t('accounts.status.session_expired'), value: 'session_expired' },
  { label: t('accounts.status.deactivated'), value: 'deactivated' },
  { label: t('accounts.status.needs_reauth'), value: 'needs_reauth' },
  { label: t('accounts.status.unchecked'), value: 'unchecked' },
  { label: t('accounts.status.checking'), value: 'checking' },
  { label: t('accounts.status.connection_failed'), value: 'connection_failed' }
])

const bulkMenuItems = computed(() => [
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
    label: t('accounts.bulk.distributeProxies'),
    icon: 'pi pi-sync',
    command: () => distributeProxiesEvenly()
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
    const files = Array.from(input.files)

    // Group files by their top-level subfolder (relative to selected folder)
    // webkitRelativePath: "selected_folder/subfolder/file" or "selected_folder/file"
    const folderGroups = new Map<string, File[]>()
    for (const f of files) {
      const path = (f.webkitRelativePath || f.name).replace(/\\/g, '/')
      const parts = path.split('/')
      // parts[0] is the selected folder, parts[1] is the subfolder or file
      if (parts.length >= 3) {
        // File is inside a subfolder: group by subfolder name
        const subfolder = parts[1]
        if (!folderGroups.has(subfolder)) folderGroups.set(subfolder, [])
        folderGroups.get(subfolder)!.push(f)
      } else if (parts.length === 2) {
        // File is directly in the selected folder — use root key
        if (!folderGroups.has('__root__')) folderGroups.set('__root__', [])
        folderGroups.get('__root__')!.push(f)
      }
    }

    // Detect tdata folders: any group that contains key_data/key_datas
    let tdataRelevant: File[] = []
    let tdataCount = 0

    // Check if the selected folder itself is a tdata folder (key_data at root level)
    const rootFiles = folderGroups.get('__root__') || []
    const rootIsTdata = rootFiles.some(f => {
      const name = f.name.toLowerCase()
      return name === 'key_data' || name === 'key_datas'
    })

    if (rootIsTdata) {
      // The entire selected folder is one tdata — include all files
      tdataRelevant = files
      tdataCount = 1
    } else {
      // Check each subfolder for key_data
      for (const [key, groupFiles] of folderGroups) {
        if (key === '__root__') continue
        const hasTdata = groupFiles.some(f => {
          const name = f.name.toLowerCase()
          return name === 'key_data' || name === 'key_datas'
        })
        if (hasTdata) {
          tdataRelevant.push(...groupFiles)
          tdataCount++
        }
      }
    }

    if (tdataRelevant.length > 0) {
      toast.add({
        severity: 'info',
        summary: t('accounts.importFlow.tdataFound'),
        detail: t('accounts.importFlow.tdataFoundCount', { count: tdataCount }),
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
  const regularFiles: File[] = []

  // Two-pass approach:
  // 1) Collect ALL files from each top-level entry, grouped by top-level folder
  // 2) Determine which folders are tdata (contain key_data), include ALL their files
  if (items && items.length > 0) {
    // Map: top-level entry name -> all files inside it
    const topLevelGroups = new Map<string, File[]>()
    const topLevelFiles: File[] = [] // files dropped directly (not in folders)

    const readAllFiles = async (entry: FileSystemEntry, path = ''): Promise<File[]> => {
      const result: File[] = []
      if (entry.isFile) {
        const fileEntry = entry as FileSystemFileEntry
        const file = await new Promise<File>((resolve, reject) => {
          fileEntry.file(
            (f) => {
              Object.defineProperty(f, 'webkitRelativePath', {
                value: path + f.name,
                writable: false
              })
              resolve(f)
            },
            (err) => reject(err)
          )
        })
        result.push(file)
      } else if (entry.isDirectory) {
        const dirEntry = entry as FileSystemDirectoryEntry
        const reader = dirEntry.createReader()
        let allEntries: FileSystemEntry[] = []
        let batch: FileSystemEntry[]
        do {
          batch = await new Promise<FileSystemEntry[]>((resolve, reject) => {
            reader.readEntries(
              (e) => resolve(e),
              (err) => reject(err)
            )
          })
          allEntries = allEntries.concat(batch)
        } while (batch.length > 0)
        for (const childEntry of allEntries) {
          const childFiles = await readAllFiles(childEntry, path + entry.name + '/')
          result.push(...childFiles)
        }
      }
      return result
    }

    // IMPORTANT: Collect all entries synchronously FIRST!
    // DataTransfer.items is cleared after the first await in Chromium/Electron.
    const entries: FileSystemEntry[] = []
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry()
      if (entry) entries.push(entry)
    }

    // Now process entries asynchronously
    for (const entry of entries) {
      try {
        if (entry.isDirectory) {
          const files = await readAllFiles(entry)
          topLevelGroups.set(entry.name, files)
        } else {
          const files = await readAllFiles(entry)
          topLevelFiles.push(...files)
        }
      } catch (err) {
        addImportLog('error', `Ошибка чтения: ${entry.name} - ${err}`)
      }
    }

    // Classify each top-level folder: tdata (has key_data) or not
    const allTdataFiles: File[] = []
    for (const [, groupFiles] of topLevelGroups) {
      const hasTdata = groupFiles.some(f => {
        const name = f.name.toLowerCase()
        return name === 'key_data' || name === 'key_datas'
      })
      if (hasTdata) {
        allTdataFiles.push(...groupFiles)
      } else {
        // Not a tdata folder — check individual files
        for (const f of groupFiles) {
          if (f.name.endsWith('.session') || f.name.endsWith('.json') || f.name.endsWith('.zip')) {
            regularFiles.push(f)
          }
        }
      }
    }

    // Check top-level files (not in folders)
    for (const f of topLevelFiles) {
      if (f.name.endsWith('.session') || f.name.endsWith('.json') || f.name.endsWith('.zip')) {
        regularFiles.push(f)
      }
    }

    // Process tdata files
    if (allTdataFiles.length > 0) {
      tdataFiles.value = allTdataFiles
      await parseTdataFolder()
    }
    // Process regular files
    if (regularFiles.length > 0) {
      await addFiles(regularFiles)
    }
  }
  // Fallback to simple file list
  if (regularFiles.length === 0 && tdataFiles.value.length === 0 && event.dataTransfer.files.length > 0) {
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
    } else if (result.errors?.length > 0) {
      // All accounts were duplicates or had errors — already shown as toasts above
      addImportLog('warn', `Все ${result.total_errors} аккаунт(ов) пропущены (дубликаты или ошибки)`)
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

  // Grab files and clear immediately to prevent duplicate processing
  const filesToParse = [...pendingFiles.value]
  pendingFiles.value = []

  try {
    const sessionFiles = filesToParse.filter(f => f.name.endsWith('.session'))
    const jsonFiles = filesToParse.filter(f => f.name.endsWith('.json'))
    const zipFiles = filesToParse.filter(f => f.name.endsWith('.zip'))
    const tdataFile = zipFiles[0] // Only one tdata at a time

    console.log('[Import] Files to parse:', {
      sessions: sessionFiles.map(f => f.name),
      jsons: jsonFiles.map(f => f.name),
      tdata: tdataFile?.name
    })

    const result = await accountStore.parseImportFiles(sessionFiles, jsonFiles, tdataFile)
    console.log('[Import] Parse result:', { accounts: result.accounts?.length, errors: result.errors })

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
          life: 8000
        })
      })
    }

    if (newAccounts.length > 0) {
      importStep.value = 'preview'
    } else {
      const errorDetails = result.errors?.length > 0
        ? result.errors.map(e => `${e.file}: ${e.error}`).join('\n')
        : t('accounts.importFlow.noAccountsParsed')
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: errorDetails,
        life: 8000
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

function distributeExistingProxies() {
  const proxies = proxyStore.proxies
  if (proxies.length === 0 || parsedAccounts.value.length === 0) return

  const proxyIds = proxies.map(p => p.id)
  parsedAccounts.value.forEach((account, index) => {
    account.proxy_id = proxyIds[index % proxyIds.length]
  })

  addImportLog('success', `Розподілено ${proxyIds.length} проксі на ${parsedAccounts.value.length} акаунтів`)
  toast.add({
    severity: 'success',
    summary: t('common.success'),
    detail: t('accounts.messages.proxiesDistributed', { count: parsedAccounts.value.length }),
    life: 3000
  })
}

async function distributeFromPool() {
  const lines = proxyPoolText.value.trim().split('\n').filter(line => line.trim())
  if (lines.length === 0) {
    toast.add({ severity: 'warn', summary: t('common.warning'), detail: t('accounts.importFlow.proxyPoolEmpty'), life: 3000 })
    return
  }
  if (parsedAccounts.value.length === 0) {
    toast.add({ severity: 'warn', summary: t('common.warning'), detail: t('accounts.importFlow.noAccountsToDistribute'), life: 3000 })
    return
  }

  distributingPool.value = true
  addImportLog('info', `Розподіл проксі з пулу: ${lines.length} проксі на ${parsedAccounts.value.length} акаунтів...`)

  const createdProxyIds: number[] = []
  const failedLines: string[] = []

  for (const line of lines) {
    const parsed = parseProxyString(line)
    if (!parsed) {
      failedLines.push(line)
      addImportLog('warn', `Не вдалося розпарсити: ${line}`)
      continue
    }

    try {
      const proxyData: any = {
        ...parsed,
        username: parsed.username || null,
        password: parsed.password || null
      }

      // Check if proxy already exists by host:port
      const existing = proxyStore.proxies.find(
        p => p.host === parsed.host && p.port === parsed.port
      )
      if (existing) {
        // Update existing proxy if credentials or type changed
        const needsUpdate =
          existing.type !== parsed.type ||
          (existing.username || null) !== (parsed.username || null) ||
          (existing.password || null) !== (parsed.password || null)
        if (needsUpdate) {
          await window.api.put(`/api/proxy/${existing.id}`, proxyData)
          addImportLog('info', `Проксі оновлено: ${parsed.host}:${parsed.port}`)
        } else {
          addImportLog('info', `Проксі вже існує: ${parsed.host}:${parsed.port}`)
        }
        createdProxyIds.push(existing.id)
        continue
      }

      const newProxy = await window.api.post('/api/proxy', proxyData) as { id: number }
      createdProxyIds.push(newProxy.id)
      addImportLog('success', `Проксі додано: ${parsed.host}:${parsed.port}`)
    } catch (error: any) {
      failedLines.push(line)
      addImportLog('error', `Помилка додавання ${parsed.host}:${parsed.port}: ${error.message}`)
    }
  }

  if (createdProxyIds.length > 0) {
    await proxyStore.fetchProxies()

    // Round-robin distribution
    parsedAccounts.value.forEach((account, index) => {
      account.proxy_id = createdProxyIds[index % createdProxyIds.length]
    })

    addImportLog('success', `Розподілено ${createdProxyIds.length} проксі на ${parsedAccounts.value.length} акаунтів`)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: `Розподілено ${createdProxyIds.length} проксі`,
      life: 3000
    })
  }

  if (failedLines.length > 0) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: `Не вдалося обробити ${failedLines.length} рядків`,
      life: 5000
    })
  }

  distributingPool.value = false
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
        proxy_id: a.proxy_id,
        api_id: a.api_id,
        api_hash: a.api_hash,
        device_fingerprint: a.device_fingerprint,
        phone: a.phone,
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
  showProxyPool.value = false
  proxyPoolText.value = ''
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

    const newProxy = await window.api.post('/api/proxy', proxyData) as { id: number }
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
        : getCheckErrorSummary(result.error_code, result.error),
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

async function distributeProxiesEvenly() {
  const accountIds = selectedIds.value.length > 0
    ? selectedIds.value
    : accountStore.filteredAccounts.map(a => a.id)

  if (accountIds.length === 0) {
    toast.add({ severity: 'warn', summary: t('common.warning'), detail: t('accounts.messages.noAccounts'), life: 3000 })
    return
  }

  const proxyIds = proxyStore.proxies.map(p => p.id)
  if (proxyIds.length === 0) {
    toast.add({ severity: 'warn', summary: t('common.warning'), detail: t('accounts.messages.noProxies'), life: 3000 })
    return
  }

  try {
    const result = await accountStore.assignProxies({
      account_ids: accountIds,
      proxy_ids: proxyIds,
      mode: 'sequential'
    })
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.messages.proxiesDistributed', { count: result.updated }),
      life: 3000
    })
  } catch (error: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: error.message, life: 3000 })
  }
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
    const frozenCount = result.results.filter(r => r.status === 'frozen').length
    const otherCount = result.results.filter(r => r.status !== 'valid' && r.status !== 'frozen').length

    const parts = []
    if (validCount > 0) parts.push(t('accounts.messages.batchCheckValid', { count: validCount }))
    if (frozenCount > 0) parts.push(t('accounts.messages.batchCheckFrozen', { count: frozenCount }))
    if (otherCount > 0) parts.push(t('accounts.messages.batchCheckInvalid', { count: otherCount }))

    toast.add({
      severity: frozenCount > 0 || otherCount > 0 ? 'warn' : 'success',
      summary: t('common.success'),
      detail: parts.join(', '),
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

async function checkBulkProxies() {
  const proxyIds = [...new Set(
    accountStore.filteredAccounts
      .filter(a => selectedIds.value.includes(a.id) && a.proxy_id)
      .map(a => a.proxy_id!)
  )]

  if (proxyIds.length === 0) {
    toast.add({ severity: 'warn', summary: t('common.warning'), detail: t('accounts.messages.noProxiesToCheck'), life: 3000 })
    return
  }

  bulkProxyChecking.value = true
  checkingProxyIds.value = new Set(proxyIds)
  try {
    const result = await proxyStore.checkBatchProxies(proxyIds)
    const working = result.results.filter(r => r.status === 'working' || r.status === 'slow').length
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.messages.proxyCheckComplete', { working, total: result.results.length }),
      life: 5000
    })
  } catch (error: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: error.message, life: 5000 })
  } finally {
    bulkProxyChecking.value = false
    checkingProxyIds.value = new Set()
  }
}

async function handleBulk2FASet() {
  if (!bulk2FAPassword.value.trim()) return

  bulk2FALoading.value = true
  try {
    const result = await accountStore.bulkSet2FA(
      selectedIds.value,
      bulk2FAPassword.value.trim(),
      bulk2FAHint.value.trim() || undefined
    )

    toast.add({
      severity: result.succeeded > 0 ? 'success' : 'error',
      summary: result.succeeded > 0 ? t('common.success') : t('common.error'),
      detail: t('accounts.messages.bulk2FAComplete', { succeeded: result.succeeded, failed: result.failed }),
      life: 5000
    })

    showBulk2FADialog.value = false
    bulk2FAPassword.value = ''
    bulk2FAHint.value = ''
  } catch (error: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: error.message, life: 5000 })
  } finally {
    bulk2FALoading.value = false
  }
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

function getStatusSeverity(status: string): "success" | "info" | "warn" | "danger" | "secondary" | "contrast" | undefined {
  switch (status) {
    case 'valid': return 'success'
    case 'invalid': return 'danger'
    case 'banned': return 'danger'
    case 'deactivated': return 'danger'
    case 'muted': return 'warn'
    case 'spamblock': return 'warn'
    case 'frozen': return 'info'
    case 'session_expired': return 'warn'
    case 'needs_reauth': return 'warn'
    case 'connection_failed': return 'warn'
    case 'checking': return 'info'
    default: return 'secondary'
  }
}

function getCheckErrorLabel(errorCode: string | null | undefined): string {
  if (!errorCode) return ''
  const key = `accounts.checkErrors.codes.${errorCode}`
  const translated = t(key)
  return translated === key ? errorCode : translated
}

function getCheckErrorTooltip(account: Account): string {
  if (!account.last_check_error_code && !account.last_check_error) {
    return ''
  }

  const details: string[] = []
  if (account.last_check_error_code) {
    details.push(`${t('accounts.checkErrors.code')}: ${getCheckErrorLabel(account.last_check_error_code)} (${account.last_check_error_code})`)
  }
  if (account.last_check_error) {
    details.push(`${t('accounts.checkErrors.message')}: ${account.last_check_error}`)
  }
  return details.join('\n')
}

function getCheckErrorSummary(errorCode: string | null | undefined, errorMessage: string | null | undefined): string {
  const normalizedMessage = errorMessage && errorCode && errorMessage === errorCode ? null : errorMessage
  const codeLabel = getCheckErrorLabel(errorCode)
  if (normalizedMessage && codeLabel) {
    return `${codeLabel}: ${normalizedMessage}`
  }
  return normalizedMessage || codeLabel || t('accounts.messages.sessionNotValid')
}

function openTwoFADialog(account: Account) {
  twoFAAccount.value = account
  showTwoFADialog.value = true
}

function openProfileDialog(account: Account) {
  profileAccount.value = account
  showProfileDialog.value = true
}

async function handleBulkProfileUpdate() {
  bulkProfileLoading.value = true
  try {
    const data: any = {
      account_ids: selectedIds.value,
      auto_generate: bulkProfileMode.value === 'auto',
      max_concurrent: 2,
    }

    if (bulkProfileMode.value === 'auto') {
      data.gender = bulkProfileGender.value || undefined
    } else {
      if (bulkProfileFirstName.value.trim()) data.first_name = bulkProfileFirstName.value.trim()
      if (bulkProfileLastName.value.trim()) data.last_name = bulkProfileLastName.value.trim()
      if (bulkProfileBio.value.trim()) data.bio = bulkProfileBio.value.trim()
    }

    const result = await accountStore.bulkUpdateProfile(data)

    toast.add({
      severity: result.succeeded > 0 ? 'success' : 'error',
      summary: result.succeeded > 0 ? t('common.success') : t('common.error'),
      detail: t('accounts.messages.bulkProfileComplete', { succeeded: result.succeeded, failed: result.failed }),
      life: 5000
    })

    showBulkProfileDialog.value = false
  } catch (error: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: error.message, life: 5000 })
  } finally {
    bulkProfileLoading.value = false
    bulkProfileFirstName.value = ''
    bulkProfileLastName.value = ''
    bulkProfileBio.value = ''
    bulkProfileGender.value = undefined
  }
}

async function handleTerminateSessions(account: Account) {
  if (!window.confirm(t('accounts.sessions.confirmTerminate'))) return

  try {
    const result = await accountStore.terminateOtherSessions(account.id)
    if (result.success) {
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('accounts.sessions.terminated', { count: result.terminated_count }),
        life: 3000
      })
    } else {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: result.errors?.join(', ') || 'Failed',
        life: 5000
      })
    }
  } catch (error: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: error.message || error.detail, life: 5000 })
  }
}

async function handleBulkTerminateSessions() {
  if (!window.confirm(t('accounts.sessions.confirmBulkTerminate', { count: selectedIds.value.length }))) return

  bulkTerminateLoading.value = true
  try {
    const result = await accountStore.bulkTerminateSessions(selectedIds.value)
    toast.add({
      severity: result.succeeded > 0 ? 'success' : 'error',
      summary: result.succeeded > 0 ? t('common.success') : t('common.error'),
      detail: t('accounts.sessions.bulkTerminated', {
        succeeded: result.succeeded,
        failed: result.failed,
        terminated: result.total_terminated,
      }),
      life: 5000
    })
  } catch (error: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: error.message, life: 5000 })
  } finally {
    bulkTerminateLoading.value = false
  }
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text)
  toast.add({
    severity: 'info',
    summary: t('common.copied'),
    life: 1500
  })
}

function openWebViewer(account: Account) {
  webViewerAccount.value = account
  showWebViewer.value = true
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

// Row select/unselect handled by v-model:selection bridge (selectedRows)

// Helper: country code to flag emoji

// Helper: format aging time since registration
function formatAging(registerTime: string | null): string {
  if (!registerTime) return '—'
  const now = new Date()
  const reg = new Date(registerTime)
  const diffMs = now.getTime() - reg.getTime()
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (days < 1) return t('accounts.time.today')
  if (days < 30) return t('accounts.time.days', { count: days })

  const months = Math.floor(days / 30)
  const remainDays = days % 30

  if (months < 12) {
    return remainDays > 0 ? t('accounts.time.daysMonths', { months, days: remainDays }) : t('accounts.time.months', { count: months })
  }

  const years = Math.floor(months / 12)
  const remainMonths = months % 12
  return remainMonths > 0 ? t('accounts.time.yearsMonths', { years, months: remainMonths }) : t('accounts.time.years', { count: years })
}

// Helper: format last used time
function formatLastUsed(lastUsedAt: string | null): string {
  if (!lastUsedAt) return '—'
  const date = new Date(lastUsedAt)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate())

  const loc = locale.value === 'uk' ? 'uk-UA' : 'en-US'
  const time = date.toLocaleTimeString(loc, { hour: '2-digit', minute: '2-digit' })

  if (dateDay.getTime() === today.getTime()) return `${t('accounts.time.today')}, ${time}`
  if (dateDay.getTime() === yesterday.getTime()) return `${t('accounts.time.yesterday')}, ${time}`

  return date.toLocaleDateString(loc, { day: '2-digit', month: '2-digit', year: '2-digit' })
}

// Helper: full name
function getFullName(account: Account): string {
  const parts = []
  if (account.first_name) parts.push(account.first_name)
  if (account.last_name) parts.push(account.last_name)
  return parts.join(' ') || account.username || '—'
}

// Inline update functions
async function updateAccountProxy(account: Account, proxyId: number | null) {
  try {
    await accountStore.updateAccount(account.id, { proxy_id: proxyId ?? 0 })
  } catch (error: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: error.message, life: 3000 })
  }
}

async function updateAccountGroup(account: Account, groupId: number | null) {
  try {
    await accountStore.updateAccount(account.id, { group_id: groupId ?? 0 })
  } catch (error: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: error.message, life: 3000 })
  }
}

async function updateAccountTags(account: Account, tagIds: number[]) {
  try {
    await accountStore.updateAccount(account.id, { tag_ids: tagIds })
  } catch (error: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: error.message, life: 3000 })
  }
}

// Proxy options for inline dropdown
const proxyOptions = computed(() => [
  { label: '—', value: null, host: '', port: 0, type: '', status: '', geo: null },
  ...proxyStore.proxies.map(p => ({
    label: `${p.host}:${p.port}`,
    value: p.id,
    host: p.host,
    port: p.port,
    type: p.type,
    status: p.status,
    geo: p.geo,
  }))
])

// Group options for inline dropdown
const groupOptions = computed(() => [
  { label: '—', value: null },
  ...groupStore.groups.map(g => ({ label: g.name, value: g.id, color: g.color }))
])

// Tag options for inline multiselect
const tagOptions = computed(() =>
  tagStore.tags.map(tg => ({ label: tg.name, value: tg.id, color: tg.color }))
)

// O(1) lookup maps for table cell rendering (avoids repeated .find()/.getById() per row)
const proxyMap = computed(() => {
  const m = new Map<number, typeof proxyStore.proxies[0]>()
  for (const p of proxyStore.proxies) m.set(p.id, p)
  return m
})
const groupMap = computed(() => {
  const m = new Map<number, typeof groupStore.groups[0]>()
  for (const g of groupStore.groups) m.set(g.id, g)
  return m
})
const tagMap = computed(() => {
  const m = new Map<number, typeof tagStore.tags[0]>()
  for (const t of tagStore.tags) m.set(t.id, t)
  return m
})

// Stats — single pass over accounts array instead of 6 separate .filter() calls
const accountStats = computed(() => {
  let valid = 0, banned = 0, premium = 0, noRestrictions = 0, restricted = 0
  for (const a of accountStore.accounts) {
    if (a.status === 'valid') { valid++; if (!a.spamblock) noRestrictions++ }
    if (a.status === 'banned' || a.status === 'deactivated') banned++
    if (a.is_premium) premium++
    if (a.spamblock === true) restricted++
  }
  return { total: accountStore.accounts.length, valid, banned, premium, noRestrictions, restricted }
})
const totalAccounts = computed(() => accountStats.value.total)
const validAccounts = computed(() => accountStats.value.valid)
const bannedAccounts = computed(() => accountStats.value.banned)
const premiumAccounts = computed(() => accountStats.value.premium)
const noRestrictionsAccounts = computed(() => accountStats.value.noRestrictions)
const restrictedAccounts = computed(() => accountStats.value.restricted)

</script>

<template>
  <MainLayout>
    <Toast />
    <ConfirmDialog />

    <div class="accounts-page">
      <!-- Stats Cards -->
      <div class="stats-row">
        <div class="stat-card" :class="{ active: !accountStore.filters.status }" @click="setStatusFilter(null)">
          <div class="stat-value accent">{{ totalAccounts }}</div>
          <div class="stat-label">{{ t('accounts.allAccounts') }}</div>
        </div>
        <div class="stat-card" @click="setStatusFilter('valid')">
          <div class="stat-value">{{ validAccounts }}</div>
          <div class="stat-label">{{ t('accounts.validAccounts') }}</div>
        </div>
        <div class="stat-card" @click="setStatusFilter('banned')">
          <div class="stat-value">{{ bannedAccounts }}</div>
          <div class="stat-label">{{ t('accounts.bannedAccounts') }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ premiumAccounts }}</div>
          <div class="stat-label">⭐ Premium</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ noRestrictionsAccounts }}</div>
          <div class="stat-label">{{ t('accounts.noRestrictions') }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ restrictedAccounts }}</div>
          <div class="stat-label">{{ t('accounts.withRestrictions') }}</div>
        </div>
      </div>

      <!-- Toolbar -->
      <div class="toolbar-row">
        <div class="toolbar-actions">
          <button class="toolbar-btn toolbar-btn--primary" @click="showImportDialog = true" v-tooltip.top="t('accounts.import')">
            <i class="pi pi-plus"></i>
          </button>
          <button class="toolbar-btn" :disabled="accountStore.accounts.length === 0" @click="checkAllAccounts" v-tooltip.top="t('accounts.checkAll')">
            <i class="pi pi-refresh"></i>
          </button>
          <button class="toolbar-btn" :disabled="!hasSelection" @click="showBatchCheckDialog = true" v-tooltip.top="t('accounts.checkSelected')">
            <i class="pi pi-check"></i>
          </button>
          <button class="toolbar-btn" :disabled="!hasSelection" @click="checkBulkProxies" v-tooltip.top="t('accounts.checkProxiesBtn')">
            <i class="pi pi-check-circle"></i>
          </button>
          <div class="toolbar-divider"></div>
          <button class="toolbar-btn" @click="showGroupDialog = true" v-tooltip.top="t('accounts.createGroup')">
            <i class="pi pi-folder"></i>
          </button>
          <button class="toolbar-btn" @click="showTagDialog = true" v-tooltip.top="t('accounts.createTag')">
            <i class="pi pi-tag"></i>
          </button>
        </div>
        <span class="shown-count">
          {{ t('accounts.shownAccounts', { filtered: accountStore.filteredAccounts.length, total: accountStore.accounts.length }) }}
        </span>
      </div>

      <!-- Filters + Search -->
      <div class="filters-row">
        <div class="filter-chips">
          <Select
            :model-value="accountStore.filters.group_id"
            :options="[{ label: t('accounts.all'), value: null }, ...groupStore.groups.map(g => ({ label: g.name, value: g.id }))]"
            optionLabel="label"
            optionValue="value"
            :placeholder="t('accounts.groupPlaceholder')"
            @update:model-value="(val: number | null) => accountStore.setFilter('group_id', val || undefined)"
            class="filter-chip"
            showClear
          />
          <Select
            :model-value="accountStore.filters.status"
            :options="statusOptions"
            optionLabel="label"
            optionValue="value"
            :placeholder="t('common.status')"
            @update:model-value="setStatusFilter"
            class="filter-chip"
            showClear
          />
          <Select
            :model-value="accountStore.filters.proxy_id"
            :options="proxyFilterOptions"
            optionLabel="label"
            optionValue="value"
            :placeholder="t('accounts.proxy')"
            @update:model-value="(val: number | null) => accountStore.setFilter('proxy_id', val || undefined)"
            class="filter-chip"
            showClear
            filter
          />
          <Select
            :model-value="accountStore.filters.tag_id"
            :options="[...tagStore.tags.map(tg => ({ label: tg.name, value: tg.id }))]"
            optionLabel="label"
            optionValue="value"
            :placeholder="t('accounts.tagPlaceholder')"
            @update:model-value="(val: number | null) => accountStore.setFilter('tag_id', val || undefined)"
            class="filter-chip"
            showClear
          />
        </div>
        <div class="search-box">
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
        </div>
        <Menu ref="bulkMenu" :model="bulkMenuItems" :popup="true" />
      </div>

      <!-- Accounts Table -->
      <div class="table-card">
        <DataTable
          v-model:selection="selectedRows"
          :value="accountStore.filteredAccounts"
          :loading="accountStore.loading"
          paginator
          :rows="25"
          :rowsPerPageOptions="[25, 50, 100]"
          dataKey="id"
          class="custom-table"
          scrollable
          scrollHeight="flex"
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

          <Column selectionMode="multiple" headerStyle="width: 2.5rem"></Column>

          <Column header="" style="width: 36px">
            <template #body="{ data }">
              <div class="account-avatar">
                {{ (data.first_name || data.username || '?')[0].toUpperCase() }}
              </div>
            </template>
          </Column>

          <Column :header="t('accounts.accountColumn')" sortable field="phone" style="min-width: 140px">
            <template #body="{ data }">
              <div class="account-info-cell">
                <div class="phone-row">
                  <span class="phone-text">{{ data.phone || data.telegram_id || '—' }}</span>
                  <span v-if="data.is_premium" class="premium-badge" v-tooltip.top="'Telegram Premium'">⭐</span>
                </div>
                <span v-if="data.username" class="account-username-sub">@{{ data.username }}</span>
                <span v-else class="account-name-sub" :title="getFullName(data)">{{ getFullName(data) }}</span>
              </div>
            </template>
          </Column>

          <Column :header="t('accounts.geoColumn')" style="width: 42px" sortable field="geo">
            <template #body="{ data }">
              <span v-if="data.geo" class="geo-flag" v-tooltip.top="data.geo?.toUpperCase()">{{ countryFlag(data.geo) }}</span>
              <span v-else class="no-data">—</span>
            </template>
          </Column>

          <Column field="status" :header="t('common.status')" sortable style="min-width: 90px">
            <template #body="{ data }">
              <div v-if="data.status === 'checking'" class="checking-status">
                <i class="pi pi-spin pi-spinner"></i>
              </div>
              <div v-else class="status-cell">
                <Tag :value="t(`accounts.status.${data.status}`)" :severity="getStatusSeverity(data.status)" class="status-pill" />
                <i
                  v-if="data.last_check_error_code || data.last_check_error"
                  class="pi pi-info-circle status-error-icon"
                  v-tooltip.top="getCheckErrorTooltip(data)"
                ></i>
              </div>
            </template>
          </Column>

          <Column :header="t('accounts.proxyColumn')" style="min-width: 160px">
            <template #body="{ data }">
              <Select
                :model-value="data.proxy_id"
                :options="proxyOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="—"
                @update:model-value="(val: number | null) => updateAccountProxy(data, val)"
                class="inline-proxy-dropdown"
              >
                <template #value="{ value }">
                  <div v-if="value && proxyMap.get(value)" class="inline-proxy-value">
                    <i class="pi pi-circle-fill proxy-dot" :class="'proxy-dot--' + proxyMap.get(value)!.status"></i>
                    <span v-if="proxyMap.get(value)!.geo" class="proxy-geo-flag">{{ countryFlag(proxyMap.get(value)!.geo) }}</span>
                    <span class="proxy-addr">{{ proxyMap.get(value)!.host }}:{{ proxyMap.get(value)!.port }}</span>
                  </div>
                  <span v-else class="no-data">—</span>
                </template>
                <template #option="{ option }">
                  <div v-if="option.value" class="inline-proxy-option">
                    <i class="pi pi-circle-fill proxy-dot" :class="'proxy-dot--' + option.status"></i>
                    <span class="proxy-option-addr">{{ option.host }}:{{ option.port }}</span>
                    <span class="proxy-option-type">{{ option.type }}</span>
                    <span v-if="option.geo" class="proxy-option-geo">{{ option.geo }}</span>
                  </div>
                  <span v-else class="no-data">—</span>
                </template>
              </Select>
            </template>
          </Column>

          <Column :header="t('accounts.agingColumn')" style="min-width: 70px" sortable field="register_time">
            <template #body="{ data }">
              <span class="aging-text">{{ formatAging(data.register_time) }}</span>
            </template>
          </Column>

          <Column :header="t('accounts.groupColumn')" style="min-width: 110px">
            <template #body="{ data }">
              <Select
                :model-value="data.group_id"
                :options="groupOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="—"
                @update:model-value="(val: number | null) => updateAccountGroup(data, val)"
                class="inline-group-dropdown"
              >
                <template #value="{ value }">
                  <div class="inline-group-value">
                    <span
                      v-if="value && groupMap.get(value)"
                      class="group-dot"
                      :style="{ background: groupMap.get(value)?.color || '#8b8f9a' }"
                    ></span>
                    <span>{{ value ? (groupMap.get(value)?.name || '—') : '—' }}</span>
                  </div>
                </template>
                <template #option="{ option }">
                  <div class="inline-group-option">
                    <span v-if="option.color" class="group-dot" :style="{ background: option.color }"></span>
                    <span>{{ option.label }}</span>
                  </div>
                </template>
              </Select>
            </template>
          </Column>

          <Column :header="t('accounts.tagsColumn')" style="min-width: 120px">
            <template #body="{ data }">
              <MultiSelect
                :model-value="data.tags?.map((tg: any) => tg.id) || []"
                :options="tagOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="—"
                :maxSelectedLabels="1"
                @update:model-value="(val: number[]) => updateAccountTags(data, val)"
                class="inline-tag-select"
              >
                <template #value="{ value }">
                  <div v-if="value && value.length > 0" class="inline-tags-value">
                    <span
                      v-for="tagId in value.slice(0, 1)"
                      :key="tagId"
                      class="inline-tag-chip"
                      :style="{ background: (tagMap.get(tagId)?.color || '#8b8f9a') + '22', color: tagMap.get(tagId)?.color || '#8b8f9a', borderColor: (tagMap.get(tagId)?.color || '#8b8f9a') + '44' }"
                    >{{ tagMap.get(tagId)?.name }}</span>
                    <span v-if="value.length > 1" class="inline-tag-more">+{{ value.length - 1 }}</span>
                  </div>
                  <span v-else class="no-data">—</span>
                </template>
                <template #option="{ option }">
                  <div class="inline-tag-option">
                    <span class="tag-color-dot" :style="{ background: option.color }"></span>
                    <span>{{ option.label }}</span>
                  </div>
                </template>
              </MultiSelect>
            </template>
          </Column>

          <Column :header="t('accounts.twoFAColumn')" style="min-width: 100px" sortable field="has_2fa">
            <template #body="{ data }">
              <div class="twofa-cell">
                <i :class="data.has_2fa ? 'pi pi-lock' : 'pi pi-lock-open'" :style="{ color: data.has_2fa ? '#22c55e' : '#4b5563', fontSize: '12px' }"></i>
                <span v-if="data.two_fa_password" class="twofa-password" @click="copyToClipboard(data.two_fa_password)" v-tooltip.top="t('common.copy')">
                  {{ data.two_fa_password }}
                </span>
                <span v-else class="twofa-none">—</span>
              </div>
            </template>
          </Column>

          <Column :header="t('accounts.lastUsedColumn')" style="min-width: 80px" sortable field="last_used_at">
            <template #body="{ data }">
              <span class="last-used-text">{{ formatLastUsed(data.last_used_at) }}</span>
            </template>
          </Column>

          <Column header="" style="width: 180px">
            <template #body="{ data }">
              <div class="actions-cell">
                <button class="action-icon" @click="checkAccount(data)" v-tooltip.top="t('common.check')">
                  <i class="pi pi-refresh"></i>
                </button>
                <button class="action-icon" @click="openWebViewer(data)" :disabled="data.status !== 'valid' || !data.proxy || !data.telegram_id || !['working', 'slow', 'very_slow', 'unchecked'].includes(data.proxy?.status)" v-tooltip.top="'WebK'">
                  <i class="pi pi-external-link"></i>
                </button>
                <button class="action-icon" @click="openProfileDialog(data)" v-tooltip.top="t('accounts.profile.title')">
                  <i class="pi pi-user-edit"></i>
                </button>
                <button class="action-icon" @click="openTwoFADialog(data)" v-tooltip.top="'2FA'">
                  <i :class="data.has_2fa ? 'pi pi-lock' : 'pi pi-lock-open'"></i>
                </button>
                <button class="action-icon" @click="handleTerminateSessions(data)" v-tooltip.top="t('accounts.sessions.terminate')">
                  <i class="pi pi-sign-out"></i>
                </button>
                <button class="action-icon delete" @click="confirmDelete(data)" v-tooltip.top="t('common.delete')">
                  <i class="pi pi-trash"></i>
                </button>
              </div>
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Import Dialog -->
      <Dialog
        v-model:visible="showImportDialog"
        :header="t('accounts.importDialog.title')"
        modal
        :style="{ width: '1200px' }"
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
          <Select
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
                  {{ proxyMap.get(value)?.host }}:{{ proxyMap.get(value)?.port }}
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
          </Select>
          <Button
            :label="t('accounts.importFlow.distributeExisting')"
            icon="pi pi-sync"
            severity="info"
            :outlined="true"
            :disabled="parsedAccounts.length === 0 || proxyStore.proxies.length === 0"
            @click="distributeExistingProxies"
            v-tooltip.top="t('accounts.importFlow.distributeExistingHint', { count: proxyStore.proxies.length })"
          />
          <Button
            :label="t('accounts.importFlow.proxyPool') + (proxyPoolCount > 0 ? ` (${proxyPoolCount})` : ` (${t('common.optional')})`)"
            :icon="showProxyPool ? 'pi pi-chevron-up' : 'pi pi-list'"
            :severity="showProxyPool ? 'info' : 'secondary'"
            :outlined="!showProxyPool"
            @click="showProxyPool = !showProxyPool"
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

        <!-- Proxy Pool Section -->
        <div v-if="showProxyPool" class="proxy-pool-section">
          <textarea
            v-model="proxyPoolText"
            class="proxy-pool-textarea"
            rows="6"
            placeholder="1.2.3.4:8000:user:pass
5.6.7.8:1080:user:pass
socks5://user:pass@proxy.example.com:10000
http://9.9.9.9:8080
login:pass:1.2.3.4:8080"
          ></textarea>
          <div class="proxy-pool-actions">
            <Button
              :label="t('accounts.importFlow.distributeFromPool')"
              icon="pi pi-arrow-down"
              severity="info"
              size="small"
              :disabled="proxyPoolCount === 0 || parsedAccounts.length === 0"
              :loading="distributingPool"
              @click="distributeFromPool"
            />
            <Button
              icon="pi pi-times"
              severity="secondary"
              text
              size="small"
              :disabled="!proxyPoolText.trim()"
              @click="proxyPoolText = ''; showProxyPool = false"
              v-tooltip.top="t('accounts.importFlow.clearPool')"
            />
          </div>
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
                <Select
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
                      {{ proxyMap.get(value)?.type }}://{{ proxyMap.get(value)?.host }}:{{ proxyMap.get(value)?.port }}
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
                </Select>
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
            :label="showLogs ? t('accounts.importFlow.hideLogs') : t('accounts.importFlow.showLogs', { count: importLogs.length })"
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
            v-tooltip.top="t('accounts.importFlow.clearLogs')"
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

      <!-- Bulk 2FA Dialog -->
      <Dialog
        v-model:visible="showBulk2FADialog"
        :header="t('accounts.bulk.set2FATitle')"
        modal
        :style="{ width: '420px' }"
        class="custom-dialog"
      >
        <div class="form-field">
          <p class="description">{{ t('accounts.bulk.set2FADescription', { count: selectedIds.length }) }}</p>
        </div>
        <div class="form-field">
          <label class="form-label">{{ t('accounts.twoFA.password') }}</label>
          <InputText
            v-model="bulk2FAPassword"
            :placeholder="t('accounts.twoFA.enterPassword')"
            class="w-full"
          />
        </div>
        <div class="form-field">
          <label class="form-label">{{ t('accounts.twoFA.passwordHint') }}</label>
          <InputText
            v-model="bulk2FAHint"
            :placeholder="t('accounts.twoFA.hintPlaceholder')"
            class="w-full"
          />
        </div>
        <div class="hint-box">
          <i class="pi pi-info-circle"></i>
          <span>{{ t('accounts.bulk.set2FANote') }}</span>
        </div>

        <template #footer>
          <Button :label="t('common.cancel')" severity="secondary" @click="showBulk2FADialog = false" />
          <Button
            :label="t('accounts.bulk.set2FA')"
            icon="pi pi-lock"
            :loading="bulk2FALoading"
            :disabled="!bulk2FAPassword.trim()"
            @click="handleBulk2FASet"
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

      <!-- Profile Edit Dialog (single account) -->
      <ProfileEditDialog
        v-model:visible="showProfileDialog"
        :account="profileAccount"
        @updated="accountStore.fetchAccounts"
      />

      <!-- Bulk Profile Update Dialog -->
      <Dialog
        v-model:visible="showBulkProfileDialog"
        :header="t('accounts.bulk.editProfileTitle')"
        modal
        :style="{ width: '460px' }"
        class="custom-dialog"
      >
        <div class="form-field">
          <p class="description">{{ t('accounts.bulk.editProfileDescription', { count: selectedIds.length }) }}</p>
        </div>

        <!-- Mode Toggle -->
        <div class="mode-toggle">
          <button
            :class="['mode-btn', { active: bulkProfileMode === 'auto' }]"
            @click="bulkProfileMode = 'auto'"
          >
            <i class="pi pi-sparkles"></i>
            {{ t('accounts.bulk.autoGenerate') }}
          </button>
          <button
            :class="['mode-btn', { active: bulkProfileMode === 'manual' }]"
            @click="bulkProfileMode = 'manual'"
          >
            <i class="pi pi-pencil"></i>
            {{ t('accounts.bulk.manual') }}
          </button>
        </div>

        <!-- Auto mode -->
        <template v-if="bulkProfileMode === 'auto'">
          <div class="form-field">
            <label class="form-label">{{ t('accounts.profile.gender') }}</label>
            <div class="gender-options">
              <button
                :class="['gender-btn', { active: bulkProfileGender === undefined }]"
                @click="bulkProfileGender = undefined"
              >{{ t('accounts.profile.genderRandom') }}</button>
              <button
                :class="['gender-btn', { active: bulkProfileGender === 'male' }]"
                @click="bulkProfileGender = 'male'"
              >{{ t('accounts.profile.genderMale') }}</button>
              <button
                :class="['gender-btn', { active: bulkProfileGender === 'female' }]"
                @click="bulkProfileGender = 'female'"
              >{{ t('accounts.profile.genderFemale') }}</button>
            </div>
          </div>
          <div class="hint-box">
            <i class="pi pi-info-circle"></i>
            <span>{{ t('accounts.bulk.autoGenerateNote') }}</span>
          </div>
        </template>

        <!-- Manual mode -->
        <template v-else>
          <div class="form-field">
            <label class="form-label">{{ t('accounts.profile.firstName') }}</label>
            <InputText
              v-model="bulkProfileFirstName"
              :placeholder="t('accounts.profile.firstNamePlaceholder')"
              class="w-full"
            />
          </div>
          <div class="form-field">
            <label class="form-label">{{ t('accounts.profile.lastName') }}</label>
            <InputText
              v-model="bulkProfileLastName"
              :placeholder="t('accounts.profile.lastNamePlaceholder')"
              class="w-full"
            />
          </div>
          <div class="form-field">
            <label class="form-label">{{ t('accounts.profile.bio') }}</label>
            <InputText
              v-model="bulkProfileBio"
              :placeholder="t('accounts.profile.bioPlaceholder')"
              class="w-full"
            />
          </div>
          <div class="hint-box">
            <i class="pi pi-info-circle"></i>
            <span>{{ t('accounts.bulk.manualNote') }}</span>
          </div>
        </template>

        <template #footer>
          <Button :label="t('common.cancel')" severity="secondary" @click="showBulkProfileDialog = false" />
          <Button
            :label="t('accounts.bulk.applyProfile')"
            icon="pi pi-check"
            :loading="bulkProfileLoading"
            @click="handleBulkProfileUpdate"
          />
        </template>
      </Dialog>

      <!-- WebK Viewer -->
      <WebViewer
        v-model:visible="showWebViewer"
        :account="webViewerAccount"
        @close="showWebViewer = false"
      />
    </div>

    <!-- Floating Selection Bar -->
    <Transition name="slide-up">
      <div v-if="hasSelection" class="selection-bar">
        <div class="selection-bar-inner">
          <div class="selection-info">
            <Checkbox
              :model-value="allSelected"
              binary
              @update:model-value="allSelected ? accountStore.clearSelection() : accountStore.selectAll()"
            />
            <span class="selection-count">
              {{ t('accounts.selected', { count: selectedIds.length }) }}
            </span>
          </div>
          <div class="selection-actions">
            <Button
              :label="t('accounts.bulk.checkAccounts')"
              icon="pi pi-user-edit"
              severity="secondary"
              size="small"
              :loading="batchChecking"
              @click="showBatchCheckDialog = true"
            />
            <Button
              :label="t('accounts.bulk.checkProxies')"
              icon="pi pi-globe"
              severity="secondary"
              size="small"
              :loading="bulkProxyChecking"
              @click="checkBulkProxies"
            />
            <Button
              :label="t('accounts.bulk.set2FA')"
              icon="pi pi-lock"
              severity="secondary"
              size="small"
              @click="showBulk2FADialog = true"
            />
            <Button
              :label="t('accounts.bulk.editProfile')"
              icon="pi pi-user-edit"
              severity="secondary"
              size="small"
              @click="showBulkProfileDialog = true"
            />
            <Button
              :label="t('accounts.bulk.terminateSessions')"
              icon="pi pi-sign-out"
              severity="secondary"
              size="small"
              :loading="bulkTerminateLoading"
              @click="handleBulkTerminateSessions"
            />
            <Button
              :label="t('accounts.bulk.actions')"
              icon="pi pi-chevron-down"
              iconPos="right"
              severity="secondary"
              size="small"
              @click="toggleBulkMenu"
            />
            <Button
              icon="pi pi-trash"
              severity="danger"
              size="small"
              rounded
              text
              v-tooltip.top="t('accounts.bulk.delete')"
              @click="confirmBulkDelete"
            />
          </div>
          <Button
            icon="pi pi-times"
            severity="secondary"
            text
            rounded
            size="small"
            v-tooltip.top="t('accounts.bulk.clearSelection')"
            @click="accountStore.clearSelection"
          />
        </div>
      </div>
    </Transition>
  </MainLayout>
</template>

<style scoped>
.accounts-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Stats Cards */
.stats-row {
  display: flex;
  gap: 12px;
}

.stat-card {
  flex: 1;
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 10px;
  padding: 10px 14px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 0;
}

.stat-card:hover {
  border-color: rgba(255, 255, 255, 0.12);
  background: linear-gradient(145deg, #1a1a1a 0%, #141414 100%);
}

.stat-card.active {
  border-color: rgba(99, 102, 241, 0.4);
  background: linear-gradient(145deg, #1a1a2e 0%, #141428 100%);
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #e5e7eb;
  line-height: 1.2;
}

.stat-value.accent {
  color: #6366f1;
}

.stat-label {
  font-size: 12px;
  color: #8b8f9a;
  margin-top: 4px;
}

/* Toolbar */
.toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toolbar-actions {
  display: flex;
  gap: 4px;
}

.toolbar-btn {
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 10px;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.toolbar-btn--primary {
  width: 44px;
  height: 44px;
  background: linear-gradient(145deg, #a855f7 0%, #7c3aed 100%);
  border-color: rgba(168, 85, 247, 0.4);
  color: #fff;
  font-size: 18px;
  box-shadow: 0 0 12px rgba(168, 85, 247, 0.3);
}

.toolbar-btn--primary:hover {
  background: linear-gradient(145deg, #b86af8 0%, #8b5cf6 100%);
  color: #fff;
  border-color: rgba(168, 85, 247, 0.6);
  box-shadow: 0 0 18px rgba(168, 85, 247, 0.4);
}

.toolbar-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.13);
  color: #e5e7eb;
  border-color: rgba(255, 255, 255, 0.15);
}

.toolbar-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.toolbar-divider {
  width: 1px;
  height: 24px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0 4px;
}

.shown-count {
  font-size: 13px;
  color: #8b8f9a;
}

/* Filters Row */
.filters-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-chips {
  display: flex;
  gap: 8px;
  flex: 1;
}

.search-box {
  width: 240px;
  flex-shrink: 0;
}

.search-input {
  width: 100%;
}

:deep(.filter-chip) {
  min-width: 100px;
}

:deep(.filter-chip .p-dropdown) {
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 20px;
  min-height: 34px;
}

:deep(.filter-chip .p-dropdown:hover) {
  border-color: rgba(255, 255, 255, 0.15);
}

:deep(.filter-chip .p-dropdown .p-dropdown-label) {
  padding: 5px 12px;
  font-size: 13px;
  color: #d1d5db;
}

:deep(.filter-chip .p-dropdown .p-dropdown-trigger) {
  width: 28px;
}

/* Table */
.table-card {
  flex: 1;
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 12px;
  padding: 0;
  overflow: hidden;
  min-height: 0;
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
  color: #8b8f9a;
  margin-bottom: 20px;
  font-size: 15px;
}

/* Row index */
.row-index {
  font-size: 13px;
  color: #8b8f9a;
}

/* Avatar */
.account-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: white;
  flex-shrink: 0;
}

/* Account info cell (phone + name) */
.account-info-cell {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-width: 0;
}

/* Phone */
.phone-text {
  font-size: 12px;
  color: #e5e7eb;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.account-name-sub {
  font-size: 10px;
  color: #8b8f9a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}

.account-username-sub {
  font-size: 10px;
  color: #8b5cf6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}

/* Premium badge */
.phone-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.premium-badge {
  font-size: 12px;
  line-height: 1;
  cursor: default;
}

/* Geo */
.geo-flag {
  font-size: 14px;
  line-height: 1;
  cursor: default;
}

/* Status */
:deep(.status-pill) {
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 10px;
  white-space: nowrap;
}

.status-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-error-icon {
  font-size: 11px;
  color: #f59e0b;
  cursor: help;
}

.checking-status {
  display: inline-flex;
  align-items: center;
  color: #60a5fa;
}

.checking-status i {
  font-size: 13px;
}

/* Aging */
.aging-text {
  font-size: 11px;
  color: #9ca3af;
  white-space: nowrap;
}

/* Proxy dropdown */
.proxy-dot {
  font-size: 6px;
  flex-shrink: 0;
}

.proxy-dot--working { color: #22c55e; }
.proxy-dot--slow { color: #f59e0b; }
.proxy-dot--very_slow { color: #f59e0b; }
.proxy-dot--not_working { color: #ef4444; }
.proxy-dot--timeout { color: #ef4444; }
.proxy-dot--unchecked { color: #8b8f9a; }

.proxy-addr {
  font-size: 11px;
  color: #9ca3af;
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.proxy-geo-flag {
  font-size: 13px;
  line-height: 1;
  flex-shrink: 0;
}

.inline-proxy-value {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.inline-proxy-option {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.proxy-option-addr {
  font-family: monospace;
  font-size: 11px;
  color: #d1d5db;
}

.proxy-option-type {
  font-size: 10px;
  color: #8b8f9a;
  text-transform: uppercase;
}

.proxy-option-geo {
  font-size: 10px;
  color: #8b8f9a;
  margin-left: auto;
}

:deep(.inline-proxy-dropdown) {
  width: 100%;
  max-width: 160px;
}

:deep(.inline-proxy-dropdown .p-select) {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 0;
  transition: all 0.15s;
}

:deep(.inline-proxy-dropdown .p-select:hover) {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.1);
}

:deep(.inline-proxy-dropdown .p-select .p-select-label) {
  padding: 3px 6px;
  font-size: 12px;
  color: #d1d5db;
}

:deep(.inline-proxy-dropdown .p-select .p-select-dropdown) {
  width: 24px;
  color: #4b5563;
}

:deep(.inline-proxy-dropdown .p-select:hover .p-select-dropdown) {
  color: #9ca3af;
}

/* Inline group dropdown */
:deep(.inline-group-dropdown) {
  width: 100%;
  max-width: 120px;
}

:deep(.inline-group-dropdown .p-dropdown) {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  min-height: 30px;
  transition: all 0.15s;
}

:deep(.inline-group-dropdown .p-dropdown:hover) {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.1);
}

:deep(.inline-group-dropdown .p-dropdown .p-dropdown-label) {
  padding: 3px 6px;
  font-size: 12px;
  color: #d1d5db;
}

:deep(.inline-group-dropdown .p-dropdown .p-dropdown-trigger) {
  width: 24px;
  color: #4b5563;
}

:deep(.inline-group-dropdown .p-dropdown:hover .p-dropdown-trigger) {
  color: #9ca3af;
}

.inline-group-value {
  display: flex;
  align-items: center;
  gap: 6px;
}

.inline-group-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Inline tag multiselect */
:deep(.inline-tag-select) {
  width: 100%;
  max-width: 130px;
}

:deep(.inline-tag-select .p-multiselect) {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  min-height: 30px;
  transition: all 0.15s;
}

:deep(.inline-tag-select .p-multiselect:hover) {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.1);
}

:deep(.inline-tag-select .p-multiselect .p-multiselect-label) {
  padding: 3px 6px;
  font-size: 12px;
}

:deep(.inline-tag-select .p-multiselect .p-multiselect-trigger) {
  width: 24px;
  color: #4b5563;
}

:deep(.inline-tag-select .p-multiselect:hover .p-multiselect-trigger) {
  color: #9ca3af;
}

.inline-tags-value {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
  overflow: hidden;
}

.inline-tag-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  border: 1px solid;
  white-space: nowrap;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80px;
}

.inline-tag-more {
  font-size: 11px;
  color: #8b8f9a;
  white-space: nowrap;
}

.inline-tag-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tag-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Role (kept for backward compat) */
.role-text {
  font-size: 13px;
  color: #d1d5db;
}

/* Last used */
.twofa-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.twofa-password {
  font-size: 12px;
  color: #d1d5db;
  cursor: pointer;
  font-family: monospace;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.06);
  transition: background 0.15s;
}

.twofa-password:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.twofa-none {
  font-size: 12px;
  color: #4b5563;
}

.last-used-text {
  font-size: 11px;
  color: #9ca3af;
  white-space: nowrap;
}

/* Name */
.name-text {
  font-size: 12px;
  color: #e5e7eb;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
  display: block;
}

/* Actions */
.actions-cell {
  display: flex;
  align-items: center;
  gap: 1px;
}

.action-icon {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #8b8f9a;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 12px;
  padding: 0;
}

.action-icon:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.13);
  color: #d1d5db;
}

.action-icon:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.action-icon.delete:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.no-data {
  color: #4b5563;
  font-size: 12px;
}

/* Floating Selection Bar */
.selection-bar {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
}

.selection-bar-inner {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(145deg, #1e1e2e 0%, #181825 100%);
  border: 1px solid rgba(168, 85, 247, 0.3);
  border-radius: 14px;
  padding: 10px 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(168, 85, 247, 0.1);
  backdrop-filter: blur(12px);
}

.selection-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-right: 16px;
  border-right: 1px solid rgba(255, 255, 255, 0.1);
}

.selection-count {
  font-size: 13px;
  color: #a855f7;
  font-weight: 600;
  white-space: nowrap;
}

.selection-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Slide-up transition */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.25s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(20px);
}

/* Table styles */
:deep(.custom-table .p-datatable) {
  background: transparent;
}

:deep(.custom-table .p-datatable-thead > tr > th) {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.10);
  color: #8b8f9a;
  font-weight: 600;
  font-size: 11px;
  letter-spacing: 0.3px;
  padding: 6px 8px;
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
  padding: 5px 8px;
}

:deep(.custom-table .p-datatable-tbody > tr.p-highlight) {
  background: rgba(168, 85, 247, 0.08);
}

:deep(.custom-table .p-datatable-tbody > tr.p-highlight > td) {
  border-color: rgba(168, 85, 247, 0.12);
}

:deep(.custom-table .p-datatable-thead > tr > th .p-checkbox .p-checkbox-box.p-highlight) {
  background: #a855f7;
  border-color: #a855f7;
}

:deep(.p-checkbox .p-checkbox-box) {
  background: rgba(255, 255, 255, 0.13);
  border-color: rgba(255, 255, 255, 0.4);
}

:deep(.p-checkbox .p-checkbox-box.p-highlight) {
  background: #a855f7;
  border-color: #a855f7;
}

:deep(.p-checkbox .p-checkbox-box .p-checkbox-icon) {
  color: #fff;
}

/* Dialog styles */
:deep(.custom-dialog .p-dialog-header) {
  background: #161616;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
}

:deep(.custom-dialog .p-dialog-content) {
  background: #161616;
}

:deep(.custom-dialog .p-dialog-footer) {
  background: #161616;
  border-top: 1px solid rgba(255, 255, 255, 0.10);
}

/* Form fields */
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
  color: #8b8f9a;
}

.description {
  color: #9ca3af;
  margin-bottom: 16px;
  font-size: 14px;
}

.hint-text {
  font-size: 12px;
  color: #f59e0b;
  margin-top: 4px;
}

.hint-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(168, 85, 247, 0.08);
  border: 1px solid rgba(168, 85, 247, 0.2);
  border-radius: 8px;
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.hint-box i {
  color: #a855f7;
  margin-top: 1px;
}

.mode-toggle {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #9ca3af;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.mode-btn:hover {
  background: rgba(255, 255, 255, 0.08);
}

.mode-btn.active {
  background: rgba(168, 85, 247, 0.12);
  border-color: #a855f7;
  color: #e5e7eb;
}

.gender-options {
  display: flex;
  gap: 8px;
}

.gender-btn {
  flex: 1;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #9ca3af;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.gender-btn:hover {
  background: rgba(255, 255, 255, 0.08);
}

.gender-btn.active {
  background: rgba(59, 130, 246, 0.12);
  border-color: #3b82f6;
  color: #e5e7eb;
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

/* Checkbox */
.checkbox-field {
  display: flex;
  align-items: center;
}

:deep(.p-slider .p-slider-handle) {
  background: #a855f7;
  border-color: #a855f7;
}

:deep(.p-slider .p-slider-range) {
  background: #a855f7;
}

/* TabView */
:deep(.p-tabview .p-tabview-nav) {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.10);
}

:deep(.p-tabview .p-tabview-nav li .p-tabview-nav-link) {
  background: transparent;
  border-color: transparent;
  color: #8b8f9a;
}

:deep(.p-tabview .p-tabview-nav li.p-highlight .p-tabview-nav-link) {
  color: #a855f7;
  border-color: #a855f7;
  background: transparent;
}

:deep(.p-tabview .p-tabview-panels) {
  background: transparent;
}

/* Import Dialog Unified */
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

/* Proxy Pool */
.proxy-pool-section {
  margin-bottom: 16px;
  border: 1px dashed rgba(96, 165, 250, 0.3);
  border-radius: 10px;
  padding: 12px;
  background: rgba(96, 165, 250, 0.04);
}

.proxy-pool-textarea {
  width: 100%;
  min-height: 120px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: #e5e7eb;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  line-height: 1.5;
  padding: 10px 12px;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
}

.proxy-pool-textarea:focus {
  border-color: rgba(96, 165, 250, 0.5);
}

.proxy-pool-textarea::placeholder {
  color: #6b7280;
  font-style: italic;
}

.proxy-pool-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.import-stats-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.stat-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #9ca3af;
  background: rgba(255, 255, 255, 0.08);
  padding: 4px 10px;
  border-radius: 8px;
}

.stat-badge i {
  font-size: 12px;
}

.stat-proxy {
  color: #a855f7;
}

.stat-verified {
  color: #22c55e;
}

.import-table-container {
  margin-bottom: 12px;
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
  color: #8b8f9a;
}

.account-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #d1d5db;
}

.format-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #9ca3af;
  font-size: 12px;
}

.format-cell i {
  color: #8b8f9a;
}

.empty-table-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px;
  color: #8b8f9a;
  font-size: 14px;
}

.empty-table-message i {
  font-size: 28px;
  color: #4b5563;
}

.import-action-buttons {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

:deep(.import-dialog-unified .p-dialog-content) {
  padding: 20px 24px !important;
  background: var(--color-bg-elevated, #1a1a1e) !important;
}

:deep(.import-dialog-unified .p-dialog-header) {
  background: var(--color-bg-elevated, #1a1a1e) !important;
}

/* Proxy option in dropdown */
.proxy-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.proxy-status-tag {
  font-size: 10px;
  padding: 2px 6px;
}

/* Drop Zone */
.hidden-input {
  display: none;
}

/* Logs */
.logs-toggle-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

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
  background: rgba(255, 255, 255, 0.06);
}

.log-time {
  color: #8b8f9a;
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
  background: rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.10);
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

.format-hint {
  font-size: 13px;
  color: #8b8f9a;
}

.dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.tag-option {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
