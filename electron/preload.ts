import { contextBridge, ipcRenderer } from 'electron'

export interface ApiRequest {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  endpoint: string
  data?: unknown
}

export interface UploadFile {
  name: string
  data: ArrayBuffer
  filename: string
}

export interface UploadRequest {
  endpoint: string
  files: UploadFile[]
  fields: Record<string, string>
}

export interface ProxyConfig {
  type: string
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

const api = {
  // API requests to Python backend
  request: (params: ApiRequest) => ipcRenderer.invoke('api:request', params),

  // Shortcuts
  get: (endpoint: string) => ipcRenderer.invoke('api:request', { method: 'GET', endpoint }),
  post: (endpoint: string, data: unknown) => ipcRenderer.invoke('api:request', { method: 'POST', endpoint, data }),
  put: (endpoint: string, data: unknown) => ipcRenderer.invoke('api:request', { method: 'PUT', endpoint, data }),
  delete: (endpoint: string) => ipcRenderer.invoke('api:request', { method: 'DELETE', endpoint }),

  // File upload - accepts pre-serialized data (files must be converted to ArrayBuffer in renderer)
  upload: (endpoint: string, files: UploadFile[], fields: Record<string, string> = {}) => {
    return ipcRenderer.invoke('api:upload', { endpoint, files, fields })
  },

  // App info
  getVersion: () => ipcRenderer.invoke('app:getVersion'),

  // Backend status
  getBackendStatus: () => ipcRenderer.invoke('backend:status'),

  // WebView management
  webview: {
    // Get preload script path for webview
    getPreloadPath: () => ipcRenderer.invoke('webview:getPreloadPath'),

    // Create isolated session with proxy for account
    createSession: (accountId: number, proxy?: ProxyConfig, deviceFingerprint?: DeviceFingerprint) =>
      ipcRenderer.invoke('webview:createSession', { accountId, proxy, deviceFingerprint }),

    // Get existing session info
    getSession: (accountId: number) => ipcRenderer.invoke('webview:getSession', { accountId }),

    // Get partition name for account
    getPartition: (accountId: number) => ipcRenderer.invoke('webview:getPartition', { accountId }),

    // Clear session storage
    clearSession: (accountId: number) => ipcRenderer.invoke('webview:clearSession', { accountId }),

    // Destroy session completely
    destroySession: (accountId: number) => ipcRenderer.invoke('webview:destroySession', { accountId }),

    // Listen for health status updates
    onHealthStatus: (callback: (status: unknown) => void) => {
      ipcRenderer.on('webview:health-status', (_event, status) => callback(status))
    },

    // Remove health status listener
    removeHealthListener: () => {
      ipcRenderer.removeAllListeners('webview:health-status')
    },
  },
}

contextBridge.exposeInMainWorld('api', api)
