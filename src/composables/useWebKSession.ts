/**
 * Composable for managing Telegram WebK session in Electron webview
 */

import { ref, computed, onUnmounted, type Ref } from 'vue'
import type {
  Account,
  DeviceFingerprint,
  WebKSessionData,
  WebKSessionResponse,
  WebViewState,
} from '@/types'

export function useWebKSession(accountRef: Ref<Account | null>) {
  const state = ref<WebViewState>({
    loading: false,
    error: null,
    sessionInjected: false,
    connected: false,
    partition: null,
  })

  const sessionData = ref<WebKSessionData | null>(null)
  const sessionDeviceFingerprint = ref<DeviceFingerprint | null>(null)
  const healthStatus = ref<WebViewHealthStatus | null>(null)
  const preloadPath = ref<string | null>(null)

  const account = computed(() => accountRef.value)

  const WORKING_PROXY_STATUSES = ['working', 'slow', 'very_slow', 'unchecked']

  const canOpen = computed(() => {
    const acc = account.value
    if (!acc) return false
    return (
      acc.telegram_id !== null &&
      acc.proxy !== null &&
      WORKING_PROXY_STATUSES.includes(acc.proxy.status) &&
      acc.status === 'valid'
    )
  })

  const cannotOpenReason = computed(() => {
    const acc = account.value
    if (!acc) return null
    if (!acc.telegram_id) return 'noTelegramId'
    if (!acc.proxy) return 'noProxy'
    if (!WORKING_PROXY_STATUSES.includes(acc.proxy.status)) return 'proxyNotWorking'
    if (acc.status !== 'valid') return 'notValid'
    return null
  })

  const webkUrl = 'https://web.telegram.org/k/'

  /**
   * Fetch WebK session data from backend
   */
  async function fetchSessionData(): Promise<WebKSessionResponse | null> {
    const acc = account.value
    if (!acc) {
      state.value.error = 'No account selected'
      return null
    }

    state.value.loading = true
    state.value.error = null

    try {
      const response = (await window.api.get(
        `/api/accounts/${acc.id}/webk-session?fetch_real_salt=true`
      )) as WebKSessionResponse

      if (response.success) {
        sessionData.value = response.session_data
        sessionDeviceFingerprint.value = response.device_fingerprint
        return response
      } else {
        throw new Error('Failed to get session data')
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error'
      state.value.error = message
      console.error('[useWebKSession] Failed to fetch session:', error)
      return null
    } finally {
      state.value.loading = false
    }
  }

  /**
   * Initialize webview session with proxy.
   * Accepts proxy config with credentials (from webk-session response),
   * because the accounts API does not return the proxy password.
   */
  async function initializeWebView(proxyWithCredentials?: { type: string; host: string; port: number; username?: string | null; password?: string | null }): Promise<boolean> {
    const acc = account.value
    if (!acc) {
      state.value.error = 'Account not available'
      return false
    }

    const proxy = proxyWithCredentials || acc.proxy
    if (!proxy) {
      state.value.error = 'No proxy available'
      return false
    }

    state.value.loading = true
    state.value.error = null

    try {
      // Get preload path
      preloadPath.value = await window.api.webview.getPreloadPath()

      // Prepare proxy config with credentials
      const proxyConfig: WebViewProxyConfig = {
        type: proxy.type,
        host: proxy.host,
        port: proxy.port,
        username: proxy.username ?? undefined,
        password: proxy.password ?? undefined,
      }

      // Use the backend-provided device fingerprint for WebK.
      // Account metadata may not contain the normalized fingerprint at all.
      const deviceFingerprint = (sessionDeviceFingerprint.value ?? undefined) as
        | WebViewDeviceFingerprint
        | undefined

      // Clear previous session data to avoid stale IDB state
      await window.api.webview.clearSession(acc.id).catch(() => {})

      // Create isolated session with proxy
      const result = await window.api.webview.createSession(acc.id, proxyConfig, deviceFingerprint)

      if (!result.success) {
        throw new Error(result.error || 'Failed to create webview session')
      }

      state.value.partition = result.partition || null

      // Clear previous health listener before registering new one
      window.api.webview.removeHealthListener()
      window.api.webview.onHealthStatus((status: WebViewHealthStatus) => {
        healthStatus.value = status
        state.value.connected = status.connected
      })

      return true
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error'
      state.value.error = message
      console.error('[useWebKSession] Failed to initialize webview:', error)
      return false
    } finally {
      state.value.loading = false
    }
  }

  /**
   * Get partition name for webview
   */
  async function getPartition(): Promise<string | null> {
    const acc = account.value
    if (!acc) return null

    try {
      const partition = await window.api.webview.getPartition(acc.id)
      state.value.partition = partition
      return partition
    } catch (error) {
      console.error('[useWebKSession] Failed to get partition:', error)
      return null
    }
  }

  /**
   * Refresh session with new salt from Telegram
   */
  async function refreshSession(): Promise<boolean> {
    const acc = account.value
    if (!acc) return false

    state.value.loading = true
    state.value.error = null

    try {
      const response = (await window.api.post(
        `/api/accounts/${acc.id}/webk-session/refresh`,
        {}
      )) as WebKSessionResponse

      if (response.success) {
        sessionData.value = response.session_data
        return true
      }
      return false
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error'
      state.value.error = message
      return false
    } finally {
      state.value.loading = false
    }
  }

  /**
   * Clear session data
   */
  async function clearSession(): Promise<void> {
    const acc = account.value
    if (!acc) return

    try {
      await window.api.webview.clearSession(acc.id)
      state.value.sessionInjected = false
      state.value.connected = false
    } catch (error) {
      console.error('[useWebKSession] Failed to clear session:', error)
    }
  }

  /**
   * Cleanup on unmount
   */
  function cleanup(): void {
    const acc = account.value
    if (acc) {
      window.api.webview.destroySession(acc.id).catch(console.error)
    }
    window.api.webview.removeHealthListener()
    sessionData.value = null
    sessionDeviceFingerprint.value = null
    healthStatus.value = null
    state.value = {
      loading: false,
      error: null,
      sessionInjected: false,
      connected: false,
      partition: null,
    }
  }

  // Cleanup on unmount
  onUnmounted(() => {
    cleanup()
  })

  return {
    state,
    sessionData,
    healthStatus,
    preloadPath,
    canOpen,
    cannotOpenReason,
    webkUrl,
    fetchSessionData,
    initializeWebView,
    getPartition,
    refreshSession,
    clearSession,
    cleanup,
  }
}
