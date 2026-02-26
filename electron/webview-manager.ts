/**
 * WebView Manager for Telegram WebK viewer
 *
 * Manages isolated webview sessions with per-account proxy configuration
 * and device fingerprint spoofing.
 *
 * For SOCKS5 proxies with auth: Chromium doesn't support SOCKS5 authentication,
 * so we spin up a local SOCKS5 relay (no-auth on localhost) that forwards
 * traffic to the remote SOCKS5 proxy with username/password authentication.
 */

import { app, session, Session } from 'electron'
import * as net from 'net'

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

/**
 * Local SOCKS5 relay that accepts unauthenticated connections from Chromium
 * and forwards them to a remote SOCKS5 proxy with username/password auth.
 */
class SocksRelay {
  private server: net.Server | null = null
  public localPort = 0

  constructor(
    private remoteHost: string,
    private remotePort: number,
    private username: string,
    private password: string
  ) {}

  /**
   * Start the local relay server on a random port
   */
  start(): Promise<number> {
    return new Promise((resolve, reject) => {
      this.server = net.createServer((clientSocket) => {
        this.handleClient(clientSocket)
      })

      this.server.on('error', (err) => {
        console.error('[SocksRelay] Server error:', err.message)
        reject(err)
      })

      this.server.listen(0, '127.0.0.1', () => {
        const addr = this.server!.address() as net.AddressInfo
        this.localPort = addr.port
        console.log(`[SocksRelay] Listening on 127.0.0.1:${this.localPort}`)
        resolve(this.localPort)
      })
    })
  }

  /**
   * Handle an incoming client connection (from Chromium).
   * 1. Do SOCKS5 no-auth handshake with client
   * 2. Read CONNECT request from client
   * 3. Connect to remote SOCKS5, authenticate, send CONNECT
   * 4. Pipe data bidirectionally
   */
  private handleClient(client: net.Socket): void {
    client.setTimeout(30000, () => client.destroy())
    client.once('error', () => client.destroy())

    // Step 1: Read client greeting
    client.once('data', (greeting) => {
      if (greeting[0] !== 0x05) {
        client.destroy()
        return
      }

      // Reply: SOCKS5, no auth required
      client.write(Buffer.from([0x05, 0x00]))

      // Step 2: Read CONNECT request
      client.once('data', (request) => {
        if (request[0] !== 0x05 || request[1] !== 0x01) {
          // Not a CONNECT command
          client.write(Buffer.from([0x05, 0x07, 0x00, 0x01, 0, 0, 0, 0, 0, 0]))
          client.destroy()
          return
        }

        // Forward to remote SOCKS5 with auth
        this.connectRemote(client, request)
      })
    })
  }

  /**
   * Connect to remote SOCKS5, authenticate, and relay the CONNECT request
   */
  private connectRemote(client: net.Socket, connectRequest: Buffer): void {
    const remote = net.createConnection(this.remotePort, this.remoteHost, () => {
      // Step 3: Send SOCKS5 greeting with user/pass auth method
      remote.write(Buffer.from([0x05, 0x01, 0x02]))
    })

    remote.once('error', (err) => {
      console.error(`[SocksRelay] Remote connection error: ${err.message}`)
      // Send general failure to client
      client.write(Buffer.from([0x05, 0x01, 0x00, 0x01, 0, 0, 0, 0, 0, 0]))
      client.destroy()
      remote.destroy()
    })

    client.once('error', () => {
      remote.destroy()
    })

    // Step 3: Handle auth negotiation with remote
    remote.once('data', (authMethodResponse) => {
      if (authMethodResponse[0] !== 0x05 || authMethodResponse[1] !== 0x02) {
        // Server doesn't support user/pass auth
        console.error('[SocksRelay] Remote proxy rejected user/pass auth')
        client.write(Buffer.from([0x05, 0x01, 0x00, 0x01, 0, 0, 0, 0, 0, 0]))
        client.destroy()
        remote.destroy()
        return
      }

      // Send username/password (RFC 1929: max 255 bytes each)
      const uBuf = Buffer.from(this.username.slice(0, 255), 'utf8')
      const pBuf = Buffer.from(this.password.slice(0, 255), 'utf8')
      const authBuf = Buffer.alloc(3 + uBuf.length + pBuf.length)
      authBuf[0] = 0x01 // auth version
      authBuf[1] = uBuf.length
      uBuf.copy(authBuf, 2)
      authBuf[2 + uBuf.length] = pBuf.length
      pBuf.copy(authBuf, 3 + uBuf.length)
      remote.write(authBuf)

      // Step 4: Read auth result
      remote.once('data', (authResult) => {
        if (authResult[1] !== 0x00) {
          console.error('[SocksRelay] Remote proxy auth failed')
          client.write(Buffer.from([0x05, 0x01, 0x00, 0x01, 0, 0, 0, 0, 0, 0]))
          client.destroy()
          remote.destroy()
          return
        }

        // Step 5: Forward the original CONNECT request
        remote.write(connectRequest)

        // Step 6: Read remote's CONNECT response and forward to client
        remote.once('data', (connectResponse) => {
          client.write(connectResponse)

          if (connectResponse[1] !== 0x00) {
            // CONNECT failed
            client.destroy()
            remote.destroy()
            return
          }

          // Step 7: Pipe bidirectionally
          client.pipe(remote)
          remote.pipe(client)
        })
      })
    })
  }

  /**
   * Stop the relay server
   */
  stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.server.close(() => {
          console.log(`[SocksRelay] Stopped (port ${this.localPort})`)
          resolve()
        })
        // Destroy any remaining connections
        this.server.unref()
      } else {
        resolve()
      }
    })
  }
}

class WebViewManager {
  private sessions: Map<number, WebViewSession> = new Map()
  private proxyCredentials: Map<string, { username: string; password: string }> = new Map()
  private socksRelays: Map<number, SocksRelay> = new Map()
  private loginHandlerRegistered = false

  /**
   * Get partition name for account
   */
  getPartitionName(accountId: number): string {
    return `persist:webk-account-${accountId}`
  }

  /**
   * Register global app login handler for HTTP proxy authentication.
   */
  private registerGlobalLoginHandler(): void {
    if (this.loginHandlerRegistered) return
    this.loginHandlerRegistered = true

    app.on('login', (event, webContents, _details, authInfo, callback) => {
      if (!authInfo.isProxy) return

      for (const [partition, creds] of this.proxyCredentials.entries()) {
        const sess = this.getSessionByPartition(partition)
        if (sess && webContents.session === sess.session) {
          console.log(`[WebViewManager] Providing proxy credentials for ${authInfo.host} (account ${sess.accountId})`)
          event.preventDefault()
          callback(creds.username, creds.password)
          return
        }
      }
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
    const existing = this.sessions.get(accountId)
    if (existing) {
      if (proxyConfig) {
        await this.setupProxy(accountId, existing.session, existing.partition, proxyConfig)
        existing.proxyConfig = proxyConfig
      }
      return existing
    }

    const partition = this.getPartitionName(accountId)
    const sess = session.fromPartition(partition)

    if (proxyConfig) {
      await this.setupProxy(accountId, sess, partition, proxyConfig)
    }

    if (deviceFingerprint) {
      this.setupUserAgent(sess, deviceFingerprint)
    }

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
   * Setup proxy for session.
   * For SOCKS5 with auth: starts a local relay since Chromium can't auth SOCKS5.
   * For HTTP with auth: uses app.on('login') event.
   */
  private async setupProxy(accountId: number, sess: Session, partition: string, proxy: ProxyConfig): Promise<void> {
    let proxyRules: string

    const proxyType = proxy.type.toLowerCase()
    const hasAuth = !!(proxy.username && proxy.password)
    const isSocks = proxyType === 'socks5' || proxyType === 'socks4'

    if (isSocks && hasAuth) {
      // Chromium can't do SOCKS5 auth — use local relay
      await this.stopRelay(accountId)

      const relay = new SocksRelay(proxy.host, proxy.port, proxy.username!, proxy.password!)
      const localPort = await relay.start()
      this.socksRelays.set(accountId, relay)

      proxyRules = `socks5://127.0.0.1:${localPort}`
      console.log(`[WebViewManager] SOCKS5 auth relay: ${proxy.host}:${proxy.port} → 127.0.0.1:${localPort}`)
    } else if (isSocks) {
      proxyRules = `socks5://${proxy.host}:${proxy.port}`
    } else {
      proxyRules = `http://${proxy.host}:${proxy.port}`
    }

    console.log(`[WebViewManager] Setting proxy: ${proxyType}://${proxy.host}:${proxy.port} (auth: ${hasAuth})`)

    await sess.setProxy({
      proxyRules,
      proxyBypassRules: '<local>',
    })

    // HTTP proxy auth via login event
    if (hasAuth && !isSocks) {
      this.proxyCredentials.set(partition, {
        username: proxy.username!,
        password: proxy.password!,
      })
      this.registerGlobalLoginHandler()
    }

    console.log(`[WebViewManager] Proxy configured successfully`)
  }

  /**
   * Stop relay for account if it exists
   */
  private async stopRelay(accountId: number): Promise<void> {
    const existing = this.socksRelays.get(accountId)
    if (existing) {
      await existing.stop()
      this.socksRelays.delete(accountId)
    }
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
   * Combines Accept-Language and Proxy-Authorization in a single handler.
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
      await this.stopRelay(accountId)
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
