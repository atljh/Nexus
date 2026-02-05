/**
 * WebView Manager for Telegram WebK viewer
 *
 * Manages isolated webview sessions with per-account proxy configuration
 * and device fingerprint spoofing.
 */

import { session, Session } from 'electron'

export interface ProxyConfig {
  type: string // socks5, socks4, http, https
  host: string
  port: number
  username?: string | null
  password?: string | null
}

export interface DeviceFingerprint {
  device_model?: string
  system_version?: string
  app_version?: string
  lang_code?: string
  system_lang_code?: string
}

export interface WebViewSession {
  accountId: number
  partition: string
  session: Session
  proxyConfig?: ProxyConfig
  deviceFingerprint?: DeviceFingerprint
}

class WebViewManager {
  private sessions: Map<number, WebViewSession> = new Map()

  /**
   * Get partition name for account
   */
  getPartitionName(accountId: number): string {
    return `persist:webk-account-${accountId}`
  }

  /**
   * Create or get isolated session for account with proxy configuration
   */
  async createSession(
    accountId: number,
    proxyConfig?: ProxyConfig,
    deviceFingerprint?: DeviceFingerprint
  ): Promise<WebViewSession> {
    // Check if session already exists
    const existing = this.sessions.get(accountId)
    if (existing) {
      // Update proxy if changed
      if (proxyConfig) {
        await this.setupProxy(existing.session, proxyConfig)
        existing.proxyConfig = proxyConfig
      }
      return existing
    }

    const partition = this.getPartitionName(accountId)
    const sess = session.fromPartition(partition)

    // Setup proxy
    if (proxyConfig) {
      await this.setupProxy(sess, proxyConfig)
    }

    // Setup user agent based on device fingerprint
    if (deviceFingerprint) {
      this.setupUserAgent(sess, deviceFingerprint)
    }

    const webViewSession: WebViewSession = {
      accountId,
      partition,
      session: sess,
      proxyConfig,
      deviceFingerprint,
    }

    this.sessions.set(accountId, webViewSession)
    console.log(`[WebViewManager] Created session for account ${accountId}`)

    return webViewSession
  }

  /**
   * Setup proxy for session
   */
  private async setupProxy(sess: Session, proxy: ProxyConfig): Promise<void> {
    let proxyRules: string

    const proxyType = proxy.type.toLowerCase()

    // Build proxy URL with optional credentials
    const authPart = proxy.username && proxy.password
      ? `${encodeURIComponent(proxy.username)}:${encodeURIComponent(proxy.password)}@`
      : ''

    if (proxyType === 'socks5' || proxyType === 'socks4') {
      // SOCKS proxy - credentials in URL for SOCKS5
      proxyRules = `socks5://${authPart}${proxy.host}:${proxy.port}`
    } else {
      // HTTP/HTTPS proxy - credentials in URL
      proxyRules = `http://${authPart}${proxy.host}:${proxy.port}`
    }

    console.log(`[WebViewManager] Setting proxy: ${proxyType}://${proxy.host}:${proxy.port} (auth: ${!!proxy.username})`)

    await sess.setProxy({
      proxyRules,
      proxyBypassRules: '<local>',
    })

    // Also handle proxy authentication via 'login' event as fallback
    // (some proxies send 407 challenge instead of accepting credentials in URL)
    if (proxy.username && proxy.password) {
      // Remove any existing listeners to avoid duplicates
      sess.removeAllListeners('login')

      sess.on('login', (event, _webContents, details, authInfo, callback) => {
        console.log(`[WebViewManager] Login event: isProxy=${authInfo.isProxy}, host=${authInfo.host}, url=${details.url}`)
        if (authInfo.isProxy) {
          console.log(`[WebViewManager] Providing proxy credentials for ${authInfo.host}`)
          event.preventDefault()
          callback(proxy.username!, proxy.password!)
        }
      })
    }

    console.log(`[WebViewManager] Proxy configured successfully`)
  }

  /**
   * Setup user agent based on device fingerprint
   */
  private setupUserAgent(sess: Session, fingerprint: DeviceFingerprint): void {
    // Build user agent from fingerprint
    const deviceModel = fingerprint.device_model || 'Desktop'
    const systemVersion = fingerprint.system_version || '10.0'

    // Generate a realistic Chrome user agent
    const userAgent = `Mozilla/5.0 (${deviceModel}; ${systemVersion}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36`

    sess.setUserAgent(userAgent)

    // Set accept-language based on lang_code
    const langCode = fingerprint.lang_code || 'en'
    sess.webRequest.onBeforeSendHeaders({ urls: ['*://*/*'] }, (details, callback) => {
      callback({
        requestHeaders: {
          ...details.requestHeaders,
          'Accept-Language': `${langCode},en;q=0.9`,
        },
      })
    })

    console.log(`[WebViewManager] User agent set: ${deviceModel}`)
  }

  /**
   * Get existing session for account
   */
  getSession(accountId: number): WebViewSession | undefined {
    return this.sessions.get(accountId)
  }

  /**
   * Clear session storage and cookies for account
   */
  async clearSession(accountId: number): Promise<void> {
    const webViewSession = this.sessions.get(accountId)
    if (webViewSession) {
      const sess = webViewSession.session
      await sess.clearStorageData()
      await sess.clearCache()
      console.log(`[WebViewManager] Cleared session data for account ${accountId}`)
    }
  }

  /**
   * Destroy session for account
   */
  async destroySession(accountId: number): Promise<void> {
    const webViewSession = this.sessions.get(accountId)
    if (webViewSession) {
      await this.clearSession(accountId)
      this.sessions.delete(accountId)
      console.log(`[WebViewManager] Destroyed session for account ${accountId}`)
    }
  }

  /**
   * Get all active sessions
   */
  getAllSessions(): WebViewSession[] {
    return Array.from(this.sessions.values())
  }

  /**
   * Destroy all sessions
   */
  async destroyAllSessions(): Promise<void> {
    for (const accountId of this.sessions.keys()) {
      await this.destroySession(accountId)
    }
  }
}

// Singleton instance
export const webViewManager = new WebViewManager()
