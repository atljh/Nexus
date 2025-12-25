import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  Account,
  AccountFilters,
  AccountStatus,
  BulkAction,
  CheckResult
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

export const useAccountStore = defineStore('accounts', () => {
  // State
  const accounts = ref<Account[]>([])
  const loading = ref(false)
  const filters = ref<AccountFilters>({})
  const selectedIds = ref<number[]>([])

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

    if (filters.value.search) {
      const search = filters.value.search.toLowerCase()
      result = result.filter(a =>
        a.username?.toLowerCase().includes(search) ||
        a.phone?.includes(search) ||
        a.first_name?.toLowerCase().includes(search) ||
        a.telegram_id?.toString().includes(search)
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
      spamblock: 0,
      session_expired: 0
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
        account.status = result.valid ? 'valid' : 'invalid'
        if (result.user_info) {
          account.telegram_id = result.user_info.telegram_id
          account.username = result.user_info.username
          account.first_name = result.user_info.first_name
          account.last_name = result.user_info.last_name
          if (result.user_info.phone) {
            account.phone = result.user_info.phone
          }
        }
      }

      return result
    } catch (error) {
      if (account) {
        account.status = 'invalid'
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
    const formData = new FormData()
    formData.append('file', file)
    if (proxyId) {
      formData.append('proxy_id', proxyId.toString())
    }

    const result = await window.api.upload('/api/accounts/import/tdata', formData) as ImportResponse
    await fetchAccounts()
    return result
  }

  async function importJson(file: File, proxyId?: number): Promise<ImportResponse> {
    const formData = new FormData()
    formData.append('file', file)
    if (proxyId) {
      formData.append('proxy_id', proxyId.toString())
    }

    const result = await window.api.upload('/api/accounts/import/json', formData) as ImportResponse
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

  function setFilter(key: keyof AccountFilters, value: any) {
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

  return {
    // State
    accounts,
    loading,
    filters,
    selectedIds,
    // Getters
    filteredAccounts,
    selectedAccounts,
    statusCounts,
    // Actions
    fetchAccounts,
    checkAccount,
    deleteAccount,
    updateAccount,
    bulkAction,
    importTdata,
    importJson,
    importSessionString,
    setFilter,
    clearFilters,
    toggleSelection,
    selectAll,
    clearSelection
  }
})
