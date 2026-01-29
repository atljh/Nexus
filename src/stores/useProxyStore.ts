import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Proxy, ProxyCreate, ProxyStatus, ProxyCheckBatchResult } from '@/types'

interface ProxiesResponse {
  data: Proxy[]
}

interface CheckResult {
  status: ProxyStatus
  ping_ms: number | null
  external_ip: string | null
  geo: string | null
}

export const useProxyStore = defineStore('proxies', () => {
  // State
  const proxies = ref<Proxy[]>([])
  const loading = ref(false)

  // Getters
  const validProxies = computed(() =>
    proxies.value.filter(p => p.status === 'working' || p.status === 'slow')
  )

  const workingProxies = computed(() =>
    proxies.value.filter(p => ['working', 'slow', 'very_slow'].includes(p.status))
  )

  const proxyOptions = computed(() =>
    proxies.value.map(p => ({
      id: p.id,
      label: `${p.host}:${p.port} (${p.type})${p.geo ? ` [${p.geo}]` : ''}${p.ping_ms ? ` ${p.ping_ms}ms` : ''}`,
      value: p.id
    }))
  )

  const statusCounts = computed(() => {
    const counts: Record<ProxyStatus, number> = {
      unchecked: 0,
      working: 0,
      slow: 0,
      very_slow: 0,
      not_working: 0,
      timeout: 0
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

  async function checkProxy(id: number): Promise<CheckResult> {
    const proxy = proxies.value.find(p => p.id === id)

    try {
      const result = await window.api.post(`/api/proxy/${id}/check`, {}) as CheckResult
      if (proxy) {
        proxy.status = result.status
        proxy.ping_ms = result.ping_ms
        proxy.external_ip = result.external_ip
        proxy.geo = result.geo
        proxy.last_checked_at = new Date().toISOString()
      }
      return result
    } catch (error) {
      if (proxy) {
        proxy.status = 'not_working'
      }
      throw error
    }
  }

  async function checkBatchProxies(proxyIds: number[], lookupGeo: boolean = true): Promise<ProxyCheckBatchResult> {
    const result = await window.api.post('/api/proxy/check-batch', {
      proxy_ids: proxyIds,
      lookup_geo: lookupGeo
    }) as ProxyCheckBatchResult

    // Update proxies with results
    result.results.forEach(r => {
      const proxy = proxies.value.find(p => p.id === r.id)
      if (proxy) {
        proxy.status = r.status
        proxy.ping_ms = r.ping_ms
        proxy.external_ip = r.external_ip
        proxy.geo = r.geo
        proxy.last_checked_at = new Date().toISOString()
      }
    })

    return result
  }

  async function checkAllProxies(): Promise<ProxyCheckBatchResult> {
    const allIds = proxies.value.map(p => p.id)
    return checkBatchProxies(allIds)
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

  /**
   * Create a single proxy from a string like "type://user:pass@host:port" or "host:port:user:pass"
   */
  async function createFromString(proxyString: string): Promise<Proxy | null> {
    const trimmed = proxyString.trim()
    if (!trimmed) return null

    let type: Proxy['type'] = 'socks5'
    let host = ''
    let port = 0
    let username: string | undefined
    let password: string | undefined

    // Try URL format first: type://user:pass@host:port
    const urlMatch = trimmed.match(/^(socks5|socks4|http|https):\/\/(?:([^:]+):([^@]+)@)?([^:]+):(\d+)$/i)
    if (urlMatch) {
      type = urlMatch[1].toLowerCase() as Proxy['type']
      username = urlMatch[2] || undefined
      password = urlMatch[3] || undefined
      host = urlMatch[4]
      port = parseInt(urlMatch[5])
    } else {
      // Try simple format: host:port or host:port:user:pass
      const parts = trimmed.split(':')
      if (parts.length >= 2) {
        host = parts[0]
        port = parseInt(parts[1])
        username = parts[2] || undefined
        password = parts[3] || undefined
      } else {
        throw new Error('Invalid proxy format')
      }
    }

    if (!host || !port || isNaN(port)) {
      throw new Error('Invalid proxy format')
    }

    return createProxy({ type, host, port, username, password })
  }

  return {
    // State
    proxies,
    loading,
    // Getters
    validProxies,
    workingProxies,
    proxyOptions,
    statusCounts,
    // Actions
    fetchProxies,
    createProxy,
    updateProxy,
    deleteProxy,
    checkProxy,
    checkBatchProxies,
    checkAllProxies,
    importProxies,
    getById,
    createFromString
  }
})
