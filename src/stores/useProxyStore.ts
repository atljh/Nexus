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
  let _lastFetchedAt = 0
  let _pendingFetch: Promise<void> | null = null
  const CACHE_TTL = 5000

  async function fetchProxies(force = false) {
    if (!force && proxies.value.length > 0 && Date.now() - _lastFetchedAt < CACHE_TTL) {
      return
    }
    if (_pendingFetch) return _pendingFetch
    loading.value = true
    _pendingFetch = (async () => {
      try {
        const response = await window.api.get('/api/proxy') as ProxiesResponse
        proxies.value = response.data || []
        _lastFetchedAt = Date.now()
      } finally {
        loading.value = false
        _pendingFetch = null
      }
    })()
    return _pendingFetch
  }

  async function createProxy(data: ProxyCreate): Promise<Proxy> {
    const result = await window.api.post('/api/proxy', data) as Proxy
    await fetchProxies(true)
    return result
  }

  async function bulkCreateProxies(proxyList: ProxyCreate[]): Promise<{ created: number; skipped: number }> {
    const lines = proxyList.map(p => {
      let line = `${p.host}:${p.port}`
      if (p.username) line += `:${p.username}`
      if (p.password) line += `:${p.password}`
      return line
    })
    // Group by type and send bulk requests
    const byType = new Map<string, string[]>()
    proxyList.forEach((p, i) => {
      const type = p.type || 'socks5'
      if (!byType.has(type)) byType.set(type, [])
      byType.get(type)!.push(lines[i])
    })

    let totalCreated = 0
    let totalSkipped = 0

    for (const [type, typeLines] of byType) {
      const result = await window.api.post('/api/proxy/bulk', {
        proxies: typeLines,
        type
      }) as { created: number; skipped: number }
      totalCreated += result.created
      totalSkipped += result.skipped
    }

    await fetchProxies(true)
    return { created: totalCreated, skipped: totalSkipped }
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
    const lines = text.split('\n').filter(l => l.trim()).map(l => l.trim())
    if (lines.length === 0) return { success: 0, failed: 0 }

    const result = await window.api.post('/api/proxy/bulk', {
      proxies: lines,
      type
    }) as { created: number; skipped: number }

    await fetchProxies(true)
    return { success: result.created, failed: result.skipped }
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
    bulkCreateProxies,
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
