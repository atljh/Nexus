import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Proxy, ProxyCreate, ProxyStatus } from '@/types'

interface ProxiesResponse {
  data: Proxy[]
}

interface ValidateResult {
  valid: boolean
  error?: string
}

export const useProxyStore = defineStore('proxies', () => {
  // State
  const proxies = ref<Proxy[]>([])
  const loading = ref(false)

  // Getters
  const validProxies = computed(() =>
    proxies.value.filter(p => p.status === 'valid')
  )

  const proxyOptions = computed(() =>
    proxies.value.map(p => ({
      id: p.id,
      label: `${p.host}:${p.port} (${p.type})`,
      value: p.id
    }))
  )

  const statusCounts = computed(() => {
    const counts: Record<ProxyStatus, number> = {
      unchecked: 0,
      valid: 0,
      invalid: 0
    }

    proxies.value.forEach(p => {
      if (counts[p.status] !== undefined) {
        counts[p.status]++
      }
    })

    return counts
  })

  // Actions
  async function fetchProxies() {
    loading.value = true
    try {
      const response = await window.api.get('/api/proxy') as ProxiesResponse
      proxies.value = response.data || []
    } finally {
      loading.value = false
    }
  }

  async function createProxy(data: ProxyCreate): Promise<Proxy> {
    const result = await window.api.post('/api/proxy', data) as Proxy
    await fetchProxies()
    return result
  }

  async function updateProxy(id: number, data: Partial<ProxyCreate>): Promise<Proxy> {
    const result = await window.api.put(`/api/proxy/${id}`, data) as Proxy
    const index = proxies.value.findIndex(p => p.id === id)
    if (index !== -1) {
      proxies.value[index] = result
    }
    return result
  }

  async function deleteProxy(id: number) {
    await window.api.delete(`/api/proxy/${id}`)
    proxies.value = proxies.value.filter(p => p.id !== id)
  }

  async function validateProxy(id: number) {
    const proxy = proxies.value.find(p => p.id === id)
    if (proxy) {
      proxy.status = 'unchecked'
    }

    try {
      const result = await window.api.post(`/api/proxy/${id}/validate`, {}) as ValidateResult
      if (proxy) {
        proxy.status = result.valid ? 'valid' : 'invalid'
        proxy.last_checked_at = new Date().toISOString()
      }
      return result
    } catch (error) {
      if (proxy) {
        proxy.status = 'invalid'
      }
      throw error
    }
  }

  async function validateAllProxies() {
    for (const proxy of proxies.value) {
      try {
        await validateProxy(proxy.id)
      } catch {
        // Continue validating other proxies
      }
    }
  }

  async function importProxies(text: string, type: Proxy['type'] = 'socks5') {
    const lines = text.split('\n').filter(l => l.trim())
    const results = { success: 0, failed: 0 }

    for (const line of lines) {
      try {
        const parts = line.trim().split(':')
        if (parts.length >= 2) {
          const data: ProxyCreate = {
            type,
            host: parts[0],
            port: parseInt(parts[1]),
            username: parts[2] || undefined,
            password: parts[3] || undefined
          }

          await window.api.post('/api/proxy', data)
          results.success++
        }
      } catch {
        results.failed++
      }
    }

    await fetchProxies()
    return results
  }

  function getById(id: number): Proxy | undefined {
    return proxies.value.find(p => p.id === id)
  }

  return {
    // State
    proxies,
    loading,
    // Getters
    validProxies,
    proxyOptions,
    statusCounts,
    // Actions
    fetchProxies,
    createProxy,
    updateProxy,
    deleteProxy,
    validateProxy,
    validateAllProxies,
    importProxies,
    getById
  }
})
