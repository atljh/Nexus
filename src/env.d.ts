/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface UploadFile {
  name: string
  data: Uint8Array
  filename: string
}

interface WebViewProxyConfig {
  type: string
  host: string
  port: number
  username?: string | null
  password?: string | null
}

interface WebViewDeviceFingerprint {
  device_model?: string
  system_version?: string
  app_version?: string
  lang_code?: string
  system_lang_code?: string
}

interface WebViewHealthStatus {
  sessionPresent: boolean
  connected: boolean
  dcId: number | null
  userId: number | null
  timestamp: number
}

// Electron webview element type
interface HTMLWebViewElement extends HTMLElement {
  src: string
  partition: string
  preload: string
  allowpopups: boolean
  reload: () => void
  executeJavaScript: (script: string) => Promise<unknown>
}

interface Window {
  api: {
    request: (params: { method: string; endpoint: string; data?: unknown }) => Promise<unknown>
    get: (endpoint: string) => Promise<unknown>
    post: (endpoint: string, data?: unknown) => Promise<unknown>
    put: (endpoint: string, data: unknown) => Promise<unknown>
    delete: (endpoint: string) => Promise<unknown>
    upload: (endpoint: string, files: UploadFile[], fields?: Record<string, string>) => Promise<unknown>
    getVersion: () => Promise<string>
    getBackendStatus: () => Promise<{ ready: boolean; running: boolean }>
    webview: {
      getPreloadPath: () => Promise<string>
      createSession: (
        accountId: number,
        proxy?: WebViewProxyConfig,
        deviceFingerprint?: WebViewDeviceFingerprint
      ) => Promise<{ success: boolean; partition?: string; error?: string }>
      getSession: (accountId: number) => Promise<{ exists: boolean; partition?: string }>
      getPartition: (accountId: number) => Promise<string>
      clearSession: (accountId: number) => Promise<{ success: boolean; error?: string }>
      destroySession: (accountId: number) => Promise<{ success: boolean; error?: string }>
      onHealthStatus: (callback: (status: WebViewHealthStatus) => void) => void
      removeHealthListener: () => void
    }
  }
}
