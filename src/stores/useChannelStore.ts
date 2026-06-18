import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  SavedChannel,
  ChannelMembership,
  ChannelMembershipStatus,
  CreateSavedChannelParams
} from '@/types'

interface ChannelMembershipsResponse {
  channel: SavedChannel
  memberships: ChannelMembership[]
}

interface SubscribeResult {
  success: boolean
  task_id: number | null
  total: number
  message?: string
}

const CACHE_TTL = 5000

export const useChannelStore = defineStore('channel', () => {
  const channels = ref<SavedChannel[]>([])
  const currentChannel = ref<SavedChannel | null>(null)
  const memberships = ref<ChannelMembership[]>([])
  const loading = ref(false)
  const membershipsLoading = ref(false)
  const error = ref<string | null>(null)

  let channelsFetchedAt = 0
  let channelsFetchedKey = ''

  async function fetchChannels(search = '', force = false): Promise<SavedChannel[]> {
    const cacheKey = search.trim().toLowerCase()
    if (!force && channels.value.length > 0 && cacheKey === channelsFetchedKey && Date.now() - channelsFetchedAt < CACHE_TTL) {
      return channels.value
    }

    loading.value = true
    error.value = null
    try {
      let endpoint = '/api/channels'
      if (cacheKey) {
        endpoint += `?search=${encodeURIComponent(search.trim())}`
      }
      const response = await window.api.get(endpoint) as SavedChannel[]
      channels.value = Array.isArray(response) ? response : []
      channelsFetchedAt = Date.now()
      channelsFetchedKey = cacheKey
      return channels.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch saved channels'
      console.error('Failed to fetch saved channels:', e)
      return []
    } finally {
      loading.value = false
    }
  }

  async function fetchChannel(channelId: number): Promise<SavedChannel | null> {
    try {
      const response = await window.api.get(`/api/channels/${channelId}`) as SavedChannel
      currentChannel.value = response
      const index = channels.value.findIndex(channel => channel.id === channelId)
      if (index >= 0) {
        channels.value[index] = response
      }
      return response
    } catch (e) {
      console.error('Failed to fetch saved channel:', e)
      return null
    }
  }

  async function fetchMemberships(channelId: number, status?: ChannelMembershipStatus): Promise<ChannelMembership[]> {
    membershipsLoading.value = true
    try {
      let endpoint = `/api/channels/${channelId}/memberships`
      if (status) {
        endpoint += `?status=${status}`
      }
      const response = await window.api.get(endpoint) as ChannelMembershipsResponse
      currentChannel.value = response.channel
      memberships.value = Array.isArray(response.memberships) ? response.memberships : []

      const index = channels.value.findIndex(channel => channel.id === channelId)
      if (index >= 0) {
        channels.value[index] = response.channel
      }
      return memberships.value
    } catch (e) {
      console.error('Failed to fetch channel memberships:', e)
      memberships.value = []
      return []
    } finally {
      membershipsLoading.value = false
    }
  }

  async function createChannel(payload: CreateSavedChannelParams): Promise<SavedChannel | null> {
    try {
      const response = await window.api.post('/api/channels', payload) as SavedChannel
      const existingIndex = channels.value.findIndex(channel => channel.id === response.id)
      if (existingIndex >= 0) {
        channels.value[existingIndex] = response
      } else {
        channels.value.unshift(response)
      }
      channelsFetchedAt = Date.now()
      channelsFetchedKey = ''
      return response
    } catch (e) {
      console.error('Failed to create saved channel:', e)
      return null
    }
  }

  async function updateChannel(channelId: number, payload: CreateSavedChannelParams): Promise<SavedChannel | null> {
    try {
      const response = await window.api.put(`/api/channels/${channelId}`, payload) as SavedChannel
      const index = channels.value.findIndex(channel => channel.id === channelId)
      if (index >= 0) {
        channels.value[index] = response
      } else {
        channels.value.unshift(response)
      }
      if (currentChannel.value?.id === channelId) {
        currentChannel.value = response
      }
      channelsFetchedAt = Date.now()
      channelsFetchedKey = ''
      return response
    } catch (e) {
      console.error('Failed to update saved channel:', e)
      return null
    }
  }

  async function deleteChannel(channelId: number): Promise<boolean> {
    try {
      await window.api.delete(`/api/channels/${channelId}`)
      channels.value = channels.value.filter(channel => channel.id !== channelId)
      if (currentChannel.value?.id === channelId) {
        currentChannel.value = null
        memberships.value = []
      }
      return true
    } catch (e) {
      console.error('Failed to delete saved channel:', e)
      return false
    }
  }

  function clearMemberships(): void {
    currentChannel.value = null
    memberships.value = []
  }

  async function subscribeUnsubscribed(channelId: number): Promise<SubscribeResult | null> {
    try {
      return await window.api.post(`/api/channels/${channelId}/subscribe`, {}) as SubscribeResult
    } catch (e) {
      console.error('Failed to subscribe accounts to channel:', e)
      return null
    }
  }

  return {
    channels,
    currentChannel,
    memberships,
    loading,
    membershipsLoading,
    error,
    fetchChannels,
    fetchChannel,
    fetchMemberships,
    createChannel,
    updateChannel,
    deleteChannel,
    clearMemberships,
    subscribeUnsubscribed
  }
})
