/**
 * WebView Manager for Telegram WebK viewer
 *
 * Manages isolated webview sessions with per-account proxy configuration
 * and device fingerprint spoofing.
 */

import { app, session, Session } from 'electron'

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
  private proxyCredentials: Map<string, { username: string; password: string }> = new Map()
  private loginHandlerRegistered = false

  /**
   * Get partition name for account
   */
  getPartitionName(accountId: number): string {
    return `persist:webk-account-${accountId}`
  }

  /**
   * Register global app login handler for proxy authentication.
   * Session objects do NOT have a 'login' event — only app does.
   */
  private registerGlobalLoginHandler(): void {
    if (this.loginHandlerRegistered) return
    this.loginHandlerRegistered = true

    app.on('login', (event, webContents, details, authInfo, callback) => {
      if (!authInfo.isProxy) return

      // Check all registered proxy credentials
      for (const [partition, creds] of this.proxyCredentials.entries()) {
        // Match by checking if the webContents uses a session we manage
        const sess = this.getSessionByPartition(partition)
        if (sess && webContents.session === sess.session) {
          console.log(`[WebViewManager] Providing proxy credentials for ${authInfo.host} (account ${sess.accountId})`)
          event.preventDefault()
          callback(creds.username, creds.password)
          return
        }
      }

      console.log(`[WebViewManager] Login event for unknown session: isProxy=${authInfo.isProxy}, host=${authInfo.host}`)
    })

    console.log('[WebViewManager] Global login handler registered')
  }

  /**
   * Find session by partition name
   */
  private getSessionByPartition(partition: string): WebViewSession | undefined {
    for (const sess of this.sessions.values()) {
      if (sess.partition === partition) return sess
    }
    return undefined
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
        await this.setupProxy(existing.session, existing.partition, proxyConfig)
        existing.proxyConfig = proxyConfig
      }
      return existing
    }

    const partition = this.getPartitionName(accountId)
    const sess = session.fromPartition(partition)

    // Setup proxy
    if (proxyConfig) {
      await this.setupProxy(sess, partition, proxyConfig)
    }

    // Setup user agent based on device fingerprint
    if (deviceFingerprint) {
      this.setupUserAgent(sess, deviceFingerprint)
    }

    // Setup unified request interceptors (Accept-Language + Proxy-Authorization)
    this.setupRequestInterceptors(sess, proxyConfig, deviceFingerprint)

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
  private async setupProxy(sess: Session, partition: string, proxy: ProxyConfig): Promise<void> {
    let proxyRules: string

    const proxyType = proxy.type.toLowerCase()

    // Build proxy URL without credentials.
    // Chromium does not support user:pass@ in HTTP proxy URLs.
    // Auth is handled via app.on('login') event.
    if (proxyType === 'socks5' || proxyType === 'socks4') {
      proxyRules = `socks5://${proxy.host}:${proxy.port}`
    } else {
      proxyRules = `http://${proxy.host}:${proxy.port}`
    }

    console.log(`[WebViewManager] Setting proxy: ${proxyType}://${proxy.host}:${proxy.port} (auth: ${!!proxy.username})`)

    await sess.setProxy({
      proxyRules,
      proxyBypassRules: '<local>',
    })

    // Store credentials and register auth handlers
    if (proxy.username && proxy.password) {
      this.proxyCredentials.set(partition, {
        username: proxy.username,
        password: proxy.password,
      })
      this.registerGlobalLoginHandler()
    }

    console.log(`[WebViewManager] Proxy configured successfully`)
  }

  /**
   * Setup user agent based on device fingerprint
   */
  private setupUserAgent(sess: Session, fingerprint: DeviceFingerprint): void {
    const deviceModel = fingerprint.device_model || 'Desktop'
    const systemVersion = fingerprint.system_version || '10.0'

    const userAgent = `Mozilla/5.0 (${deviceModel}; ${systemVersion}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36`
    sess.setUserAgent(userAgent)

    console.log(`[WebViewManager] User agent set: ${deviceModel}`)
  }

  /**
   * Setup unified request header interceptor.
   * Combines Accept-Language and Proxy-Authorization in a single handler
   * (Electron only allows one onBeforeSendHeaders handler per session).
   */
  private setupRequestInterceptors(
    sess: Session,
    proxy?: ProxyConfig,
    fingerprint?: DeviceFingerprint
  ): void {
    const langCode = fingerprint?.lang_code || 'en'
    const proxyType = proxy?.type?.toLowerCase()
    const needsProxyAuth = proxy?.username && proxy?.password && (proxyType === 'http' || proxyType === 'https')

    let proxyAuthHeader: string | null = null
    if (needsProxyAuth) {
      proxyAuthHeader = `Basic ${Buffer.from(`${proxy!.username}:${proxy!.password}`).toString('base64')}`
    }

    sess.webRequest.onBeforeSendHeaders({ urls: ['*://*/*'] }, (details, callback) => {
      const headers: Record<string, string> = {
        ...details.requestHeaders,
        'Accept-Language': `${langCode},en;q=0.9`,
      }

      if (proxyAuthHeader) {
        headers['Proxy-Authorization'] = proxyAuthHeader
      }

      callback({ requestHeaders: headers })
    })

    console.log(`[WebViewManager] Request interceptors configured (proxyAuth: ${!!proxyAuthHeader})`)
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
      this.proxyCredentials.delete(webViewSession.partition)
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
