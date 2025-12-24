import { contextBridge, ipcRenderer } from 'electron'

export interface ApiRequest {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  endpoint: string
  data?: unknown
}

const api = {
  // API requests to Python backend
  request: (params: ApiRequest) => ipcRenderer.invoke('api:request', params),

  // Shortcuts
  get: (endpoint: string) => ipcRenderer.invoke('api:request', { method: 'GET', endpoint }),
  post: (endpoint: string, data: unknown) => ipcRenderer.invoke('api:request', { method: 'POST', endpoint, data }),
  put: (endpoint: string, data: unknown) => ipcRenderer.invoke('api:request', { method: 'PUT', endpoint, data }),
  delete: (endpoint: string) => ipcRenderer.invoke('api:request', { method: 'DELETE', endpoint }),

  // App info
  getVersion: () => ipcRenderer.invoke('app:getVersion')
}

contextBridge.exposeInMainWorld('api', api)

// Type declarations for renderer
declare global {
  interface Window {
    api: typeof api
  }
}
