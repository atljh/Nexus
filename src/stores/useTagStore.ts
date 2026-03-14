import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AccountTag, TagCreate } from '@/types'

interface TagsResponse {
  data: AccountTag[]
}

export const useTagStore = defineStore('tags', () => {
  // State
  const tags = ref<AccountTag[]>([])
  const loading = ref(false)

  // Getters
  const tagOptions = computed(() =>
    tags.value.map(t => ({
      id: t.id,
      name: t.name,
      color: t.color
    }))
  )

  // Actions
  let _lastFetchedAt = 0
  const CACHE_TTL = 5000

  async function fetchTags(force = false) {
    if (!force && tags.value.length > 0 && Date.now() - _lastFetchedAt < CACHE_TTL) {
      return
    }
    loading.value = true
    try {
      const response = await window.api.get('/api/tags') as TagsResponse
      tags.value = response.data || []
      _lastFetchedAt = Date.now()
    } finally {
      loading.value = false
    }
  }

  async function createTag(data: TagCreate): Promise<AccountTag> {
    const result = await window.api.post('/api/tags', data) as AccountTag
    await fetchTags(true)
    return result
  }

  async function updateTag(id: number, data: Partial<TagCreate>): Promise<AccountTag> {
    const result = await window.api.put(`/api/tags/${id}`, data) as AccountTag
    const index = tags.value.findIndex(t => t.id === id)
    if (index !== -1) {
      tags.value[index] = result
    }
    return result
  }

  async function deleteTag(id: number) {
    await window.api.delete(`/api/tags/${id}`)
    tags.value = tags.value.filter(t => t.id !== id)
  }

  function getById(id: number): AccountTag | undefined {
    return tags.value.find(t => t.id === id)
  }

  // Preset colors for tags
  const presetColors = [
    '#ef4444', // red
    '#f97316', // orange
    '#eab308', // yellow
    '#22c55e', // green
    '#14b8a6', // teal
    '#3b82f6', // blue
    '#8b5cf6', // violet
    '#ec4899', // pink
    '#a855f7', // purple (default)
    '#6366f1'  // indigo
  ]

  return {
    // State
    tags,
    loading,
    presetColors,
    // Getters
    tagOptions,
    // Actions
    fetchTags,
    createTag,
    updateTag,
    deleteTag,
    getById
  }
})
