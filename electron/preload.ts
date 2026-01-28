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
  getBackendStatus: () => ipcRenderer.invoke('backend:status')
}

contextBridge.exposeInMainWorld('api', api)
