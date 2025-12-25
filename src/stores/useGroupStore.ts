import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AccountGroup, GroupCreate } from '@/types'

interface GroupsResponse {
  data: AccountGroup[]
}

export const useGroupStore = defineStore('groups', () => {
  // State
  const groups = ref<AccountGroup[]>([])
  const loading = ref(false)
  const selectedGroupId = ref<number | null>(null)

  // Getters
  const groupOptions = computed(() => [
    { id: null, name: 'All Accounts', accounts_count: 0 },
    ...groups.value
  ])

  const selectedGroup = computed(() =>
    groups.value.find(g => g.id === selectedGroupId.value)
  )

  const totalAccounts = computed(() =>
    groups.value.reduce((sum, g) => sum + g.accounts_count, 0)
  )

  // Actions
  async function fetchGroups() {
    loading.value = true
    try {
      const response = await window.api.get('/api/groups') as GroupsResponse
      groups.value = response.data || []
    } finally {
      loading.value = false
    }
  }

  async function createGroup(data: GroupCreate): Promise<AccountGroup> {
    const result = await window.api.post('/api/groups', data) as AccountGroup
    await fetchGroups()
    return result
  }

  async function updateGroup(id: number, data: Partial<GroupCreate>): Promise<AccountGroup> {
    const result = await window.api.put(`/api/groups/${id}`, data) as AccountGroup
    const index = groups.value.findIndex(g => g.id === id)
    if (index !== -1) {
      groups.value[index] = result
    }
    return result
  }

  async function deleteGroup(id: number) {
    await window.api.delete(`/api/groups/${id}`)
    groups.value = groups.value.filter(g => g.id !== id)
    if (selectedGroupId.value === id) {
      selectedGroupId.value = null
    }
  }

  function selectGroup(id: number | null) {
    selectedGroupId.value = id
  }

  function getById(id: number): AccountGroup | undefined {
    return groups.value.find(g => g.id === id)
  }

  return {
    // State
    groups,
    loading,
    selectedGroupId,
    // Getters
    groupOptions,
    selectedGroup,
    totalAccounts,
    // Actions
    fetchGroups,
    createGroup,
    updateGroup,
    deleteGroup,
    selectGroup,
    getById
  }
})
