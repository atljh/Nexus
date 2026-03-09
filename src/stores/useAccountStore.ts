import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  Account,
  AccountFilters,
  AccountStatus,
  BulkAction,
  CheckResult,
  CheckBatchResult,
  CheckBatchOptions,
  AssignProxiesRequest,
  SessionJsonImportResult,
  TwoFAStatus,
  TwoFASetRequest,
  TwoFAChangeRequest,
  TwoFARemoveRequest,
  TwoFAResult,
  AuthStartRequest,
  AuthStartResponse,
  AuthVerifyResponse,
  AuthStep,
  AuthSessionInfo
} from '@/types'

interface AccountsResponse {
  data: Account[]
}

interface ImportResponse {
  success: boolean
  imported?: number
  message?: string
  errors?: { index: number; error: string }[]
  account?: Account
}

type FileWithRelativePath = File & { webkitRelativePath?: string }

function resolveFilePath(file: File): string {
  return (file as FileWithRelativePath).webkitRelativePath || file.name
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === 'object' && error !== null && 'detail' in error) {
    const detail = (error as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail) return detail
  }
  return fallback
}

// Helper to convert File to serializable format for IPC
async function fileToUpload(name: string, file: File, customFilename?: string): Promise<UploadFile> {
  const buffer = await file.arrayBuffer()
  // Convert to Uint8Array for IPC serialization (ArrayBuffer can't be cloned)
  const data = new Uint8Array(buffer)
  // Use webkitRelativePath for folder uploads, or custom filename, or just file.name
  const filename = customFilename || resolveFilePath(file)
  return { name, data, filename }
}

export const useAccountStore = defineStore('accounts', () => {
  // State
  const accounts = ref<Account[]>([])
  const loading = ref(false)
  const filters = ref<AccountFilters>({})
  const selectedIds = ref<number[]>([])

  // Auth flow state
  const authSessionId = ref<string | null>(null)
  const authPhone = ref('')
  const authStep = ref<AuthStep>('phone')
  const authLoading = ref(false)
  const authError = ref<string | null>(null)

  // Getters
  const filteredAccounts = computed(() => {
    let result = accounts.value

    if (filters.value.status) {
      result = result.filter(a => a.status === filters.value.status)
    }

    if (filters.value.group_id) {
      result = result.filter(a => a.group_id === filters.value.group_id)
    }

    if (filters.value.tag_id) {
      result = result.filter(a => a.tags.some(t => t.id === filters.value.tag_id))
    }

    if (filters.value.proxy_id) {
      result = result.filter(a => a.proxy_id === filters.value.proxy_id)
    }

    if (filters.value.search) {
      const search = filters.value.search.toLowerCase()
      result = result.filter(a =>
        a.username?.toLowerCase().includes(search) ||
        a.phone?.includes(search) ||
        a.first_name?.toLowerCase().includes(search) ||
        a.telegram_id?.toString().includes(search) ||
        (a.proxy && `${a.proxy.host}:${a.proxy.port}`.includes(search))
      )
    }

    return result
  })

  const selectedAccounts = computed(() =>
    accounts.value.filter(a => selectedIds.value.includes(a.id))
  )

  const statusCounts = computed(() => {
    const counts: Record<AccountStatus, number> = {
      unchecked: 0,
      checking: 0,
      valid: 0,
      invalid: 0,
      banned: 0,
      muted: 0,
      spamblock: 0,
      frozen: 0,
      session_expired: 0,
      deactivated: 0,
      needs_reauth: 0,
      connection_failed: 0
    }

    accounts.value.forEach(a => {
      if (counts[a.status] !== undefined) {
        counts[a.status]++
      }
    })

    return counts
  })

  // Actions
  async function fetchAccounts() {
    loading.value = true
    try {
      const response = await window.api.get('/api/accounts') as AccountsResponse
      accounts.value = response.data || []
    } finally {
      loading.value = false
    }
  }

  async function checkAccount(id: number): Promise<CheckResult> {
    const account = accounts.value.find(a => a.id === id)
    if (account) {
      account.status = 'checking'
    }

    try {
      const result = await window.api.post(`/api/accounts/${id}/check`, {}) as CheckResult

      if (account) {
        account.status = result.status || (result.valid ? 'valid' : 'invalid')
        if (result.user_info) {
          account.telegram_id = result.user_info.telegram_id
          account.username = result.user_info.username
          account.first_name = result.user_info.first_name
          account.last_name = result.user_info.last_name
          if (result.user_info.phone) {
            account.phone = result.user_info.phone
          }
        }
        account.last_check_error_code = result.error_code || null
        account.last_check_error = result.error || null
      }

      return result
    } catch (error) {
      if (account) {
        account.status = 'invalid'
        account.last_check_error_code = 'unknown_error'
        account.last_check_error = getErrorMessage(error, 'Unknown error')
      }
      throw error
    }
  }

  async function deleteAccount(id: number) {
    await window.api.delete(`/api/accounts/${id}`)
    accounts.value = accounts.value.filter(a => a.id !== id)
    selectedIds.value = selectedIds.value.filter(i => i !== id)
  }

  async function updateAccount(id: number, data: { proxy_id?: number; group_id?: number; tag_ids?: number[] }) {
    const result = await window.api.put(`/api/accounts/${id}`, data) as Account
    const index = accounts.value.findIndex(a => a.id === id)
    if (index !== -1) {
      accounts.value[index] = result
    }
    return result
  }

  async function bulkAction(action: BulkAction, value?: number) {
    if (selectedIds.value.length === 0) return

    if (action === 'check') {
      for (const id of selectedIds.value) {
        try {
          await checkAccount(id)
        } catch {
          // Continue checking other accounts
        }
      }
      return
    }

    await window.api.post('/api/accounts/bulk-action', {
      action,
      account_ids: selectedIds.value,
      value
    })

    await fetchAccounts()
    if (action === 'delete') {
      selectedIds.value = []
    }
  }

  async function importTdata(file: File, proxyId?: number): Promise<ImportResponse> {
    const files = [await fileToUpload('file', file)]
    const fields: Record<string, string> = {}
    if (proxyId) {
      fields.proxy_id = proxyId.toString()
    }

    const result = await window.api.upload('/api/accounts/import/tdata', files, fields) as ImportResponse
    await fetchAccounts()
    return result
  }

  async function importJson(file: File, proxyId?: number): Promise<ImportResponse> {
    const files = [await fileToUpload('file', file)]
    const fields: Record<string, string> = {}
    if (proxyId) {
      fields.proxy_id = proxyId.toString()
    }

    const result = await window.api.upload('/api/accounts/import/json', files, fields) as ImportResponse
    await fetchAccounts()
    return result
  }

  async function importSessionString(sessionString: string, proxyId?: number): Promise<ImportResponse> {
    const result = await window.api.post('/api/accounts/import/session-string', {
      session_string: sessionString,
      proxy_id: proxyId
    }) as ImportResponse
    await fetchAccounts()
    return result
  }

  function setFilter<K extends keyof AccountFilters>(key: K, value: AccountFilters[K]) {
    filters.value[key] = value
  }

  function clearFilters() {
    filters.value = {}
  }

  function toggleSelection(id: number) {
    const index = selectedIds.value.indexOf(id)
    if (index === -1) {
      selectedIds.value.push(id)
    } else {
      selectedIds.value.splice(index, 1)
    }
  }

  function selectAll() {
    selectedIds.value = filteredAccounts.value.map(a => a.id)
  }

  function clearSelection() {
    selectedIds.value = []
  }

  async function checkBatchAccounts(
    accountIds: number[],
    options: CheckBatchOptions = { checkSpamblock: false, maxConcurrent: 3 }
  ): Promise<CheckBatchResult> {
    // Mark accounts as checking
    accountIds.forEach(id => {
      const account = accounts.value.find(a => a.id === id)
      if (account) {
        account.status = 'checking'
      }
    })

    const result = await window.api.post('/api/accounts/check-batch', {
      account_ids: accountIds,
      check_spamblock: options.checkSpamblock,
      max_concurrent: options.maxConcurrent
    }) as CheckBatchResult

    // Update accounts with results
    result.results.forEach(r => {
      const account = accounts.value.find(a => a.id === r.id)
      if (account) {
        account.status = r.status
        if (r.telegram_id) account.telegram_id = r.telegram_id
        if (r.username) account.username = r.username
        if (r.spamblock !== null) account.spamblock = r.spamblock
        account.last_check_error_code = r.error_code || null
        account.last_check_error = r.error || null
      }
    })

    return result
  }

  async function assignProxies(request: AssignProxiesRequest): Promise<{ success: boolean; updated: number }> {
    const result = await window.api.post('/api/accounts/assign-proxies', request) as { success: boolean; updated: number }
    await fetchAccounts()
    return result
  }

  async function importSessionJsonPairs(
    sessionFiles: File[],
    jsonFiles: File[],
    proxyId?: number
  ): Promise<SessionJsonImportResult> {
    const files: UploadFile[] = []

    for (const file of sessionFiles) {
      files.push(await fileToUpload('session_files', file))
    }

    for (const file of jsonFiles) {
      files.push(await fileToUpload('json_files', file))
    }

    const fields: Record<string, string> = {}
    if (proxyId) {
      fields.proxy_id = proxyId.toString()
    }

    const result = await window.api.upload('/api/accounts/import/session-json', files, fields) as SessionJsonImportResult
    await fetchAccounts()
    return result
  }

  // ============================================================
  // New Import Flow: Parse -> Verify -> Save
  // ============================================================

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
    status?: string
    error?: string
  }

  interface ParseResult {
    accounts: ParsedAccount[]
    errors: { file: string; error: string }[]
    total_parsed: number
    total_errors: number
  }

  interface VerifyResult {
    results: { temp_id: string; status: string; error?: string; telegram_id?: number; username?: string; phone?: string; first_name?: string; last_name?: string }[]
    total_valid: number
    total_invalid: number
  }

  interface SaveResult {
    saved: { temp_id: string; account_id: number; telegram_id?: number }[]
    errors: { temp_id: string; error: string }[]
    total_saved: number
    total_errors: number
  }

  async function parseImportFiles(
    sessionFiles: File[],
    jsonFiles: File[],
    tdataFile?: File
  ): Promise<ParseResult> {
    const files: UploadFile[] = []

    for (const file of sessionFiles) {
      files.push(await fileToUpload('session_files', file))
    }

    for (const file of jsonFiles) {
      files.push(await fileToUpload('json_files', file))
    }

    if (tdataFile) {
      files.push(await fileToUpload('tdata_file', tdataFile))
    }

    return await window.api.upload('/api/accounts/import/parse', files, {}) as ParseResult
  }

  async function parseTdataFiles(tdataFiles: File[]): Promise<ParseResult> {
    const files: UploadFile[] = []

    for (const file of tdataFiles) {
      files.push(await fileToUpload('tdata_files', file))
    }

    // Send paths as fields for folder structure reconstruction
    const fields: Record<string, string> = {}
    tdataFiles.forEach((file, index) => {
      const filePath = resolveFilePath(file)
      fields[`path_${index}`] = filePath
    })

    return await window.api.upload('/api/accounts/import/parse-tdata', files, fields) as ParseResult
  }

  async function verifyParsedAccounts(
    accounts: { session_string: string; proxy_id: number; temp_id: string }[]
  ): Promise<VerifyResult> {
    return await window.api.post('/api/accounts/import/verify', { accounts }) as VerifyResult
  }

  async function saveParsedAccounts(
    accounts: ParsedAccount[]
  ): Promise<SaveResult> {
    const result = await window.api.post('/api/accounts/import/save', { accounts }) as SaveResult
    await fetchAccounts()
    return result
  }

  // ============================================================
  // 2FA Methods
  // ============================================================

  async function check2FAStatus(accountId: number): Promise<TwoFAStatus> {
    const result = await window.api.get(`/api/accounts/${accountId}/2fa/status`) as TwoFAStatus

    // Update local account
    const account = accounts.value.find(a => a.id === accountId)
    if (account) {
      account.has_2fa = result.has_2fa
      account.password_hint = result.password_hint
    }

    return result
  }

  async function set2FA(accountId: number, data: TwoFASetRequest): Promise<TwoFAResult> {
    const result = await window.api.post(`/api/accounts/${accountId}/2fa/set`, data) as TwoFAResult

    if (result.success) {
      const account = accounts.value.find(a => a.id === accountId)
      if (account) {
        account.has_2fa = true
        account.password_hint = data.hint || null
        account.two_fa_set_at = new Date().toISOString()
      }
    }

    return result
  }

  async function change2FA(accountId: number, data: TwoFAChangeRequest): Promise<TwoFAResult> {
    const result = await window.api.post(`/api/accounts/${accountId}/2fa/change`, data) as TwoFAResult

    if (result.success) {
      const account = accounts.value.find(a => a.id === accountId)
      if (account) {
        account.password_hint = data.new_hint || null
        account.two_fa_set_at = new Date().toISOString()
      }
    }

    return result
  }

  async function remove2FA(accountId: number, data: TwoFARemoveRequest): Promise<TwoFAResult> {
    const result = await window.api.post(`/api/accounts/${accountId}/2fa/remove`, data) as TwoFAResult

    if (result.success) {
      const account = accounts.value.find(a => a.id === accountId)
      if (account) {
        account.has_2fa = false
        account.password_hint = null
        account.two_fa_set_at = null
      }
    }

    return result
  }

  async function bulkSet2FA(accountIds: number[], password: string, hint?: string, maxConcurrent: number = 3) {
    const result = await window.api.post('/api/accounts/2fa/bulk-set', {
      account_ids: accountIds,
      password,
      hint: hint || '',
      max_concurrent: maxConcurrent,
    }) as { success: boolean; results: { id: number; success: boolean; error?: string }[]; succeeded: number; failed: number }

    // Update local accounts
    for (const r of result.results) {
      if (r.success) {
        const account = accounts.value.find(a => a.id === r.id)
        if (account) {
          account.has_2fa = true
          account.password_hint = hint || null
          account.two_fa_password = password
          account.two_fa_set_at = new Date().toISOString()
        }
      }
    }

    return result
  }

  // ============================================================
  // Account Authorization Methods
  // ============================================================

  async function startAuth(data: AuthStartRequest): Promise<AuthStartResponse> {
    authLoading.value = true
    authError.value = null

    try {
      const result = await window.api.post('/api/accounts/auth/start', data) as AuthStartResponse
      authSessionId.value = result.session_id
      authPhone.value = data.phone
      authStep.value = 'code'
      return result
    } catch (e: unknown) {
      authError.value = getErrorMessage(e, 'Failed to start authentication')
      throw e
    } finally {
      authLoading.value = false
    }
  }

  async function verifyAuthCode(code: string, password?: string): Promise<AuthVerifyResponse> {
    if (!authSessionId.value) {
      throw new Error('No active session')
    }

    authLoading.value = true
    authError.value = null

    try {
      const result = await window.api.post('/api/accounts/auth/verify', {
        session_id: authSessionId.value,
        code,
        password,
      }) as AuthVerifyResponse

      if (result.status === 'password_required') {
        authStep.value = 'password'
        authError.value = '2FA password required'
        return result
      }

      if (result.status === 'success') {
        authStep.value = 'success'
        await fetchAccounts() // Refresh account list
      }

      return result
    } catch (e: unknown) {
      authError.value = getErrorMessage(e, 'Verification failed')
      throw e
    } finally {
      authLoading.value = false
    }
  }

  async function resendAuthCode(): Promise<AuthStartResponse> {
    if (!authSessionId.value) {
      throw new Error('No active session')
    }

    authLoading.value = true
    authError.value = null

    try {
      const result = await window.api.post('/api/accounts/auth/resend', {
        session_id: authSessionId.value,
      }) as AuthStartResponse
      return result
    } catch (e: unknown) {
      authError.value = getErrorMessage(e, 'Failed to resend code')
      throw e
    } finally {
      authLoading.value = false
    }
  }

  async function cancelAuth(): Promise<void> {
    if (authSessionId.value) {
      try {
        await window.api.post('/api/accounts/auth/cancel', {
          session_id: authSessionId.value,
        })
      } catch {
        // Ignore errors on cancel
      }
    }
    resetAuth()
  }

  function resetAuth() {
    authSessionId.value = null
    authPhone.value = ''
    authStep.value = 'phone'
    authError.value = null
  }

  async function getAuthSessionInfo(): Promise<AuthSessionInfo | null> {
    if (!authSessionId.value) return null

    try {
      return await window.api.get(`/api/accounts/auth/session/${authSessionId.value}`) as AuthSessionInfo
    } catch {
      return null
    }
  }

  return {
    // State
    accounts,
    loading,
    filters,
    selectedIds,
    // Auth state
    authSessionId,
    authPhone,
    authStep,
    authLoading,
    authError,
    // Getters
    filteredAccounts,
    selectedAccounts,
    statusCounts,
    // Actions
    fetchAccounts,
    checkAccount,
    checkBatchAccounts,
    deleteAccount,
    updateAccount,
    bulkAction,
    assignProxies,
    importTdata,
    importJson,
    importSessionString,
    importSessionJsonPairs,
    // New import flow
    parseImportFiles,
    parseTdataFiles,
    verifyParsedAccounts,
    saveParsedAccounts,
    setFilter,
    clearFilters,
    toggleSelection,
    selectAll,
    clearSelection,
    // 2FA
    check2FAStatus,
    set2FA,
    change2FA,
    remove2FA,
    bulkSet2FA,
    // Auth
    startAuth,
    verifyAuthCode,
    resendAuthCode,
    cancelAuth,
    resetAuth,
    getAuthSessionInfo
  }
})
