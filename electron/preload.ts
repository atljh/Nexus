import { contextBridge, ipcRenderer } from 'electron'

export interface ApiRequest {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  endpoint: string
  data?: unknown
}

export interface UploadRequest {
  endpoint: string
  files: Array<{ name: string; data: ArrayBuffer; filename: string }>
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

  // File upload
  upload: async (endpoint: string, formData: FormData) => {
    const files: Array<{ name: string; data: ArrayBuffer; filename: string }> = []
    const fields: Record<string, string> = {}

    // Convert FormData to serializable format
    for (const [key, value] of formData.entries()) {
      if (value instanceof File) {
        const buffer = await value.arrayBuffer()
        files.push({
          name: key,
          data: buffer,
          filename: value.name
        })
      } else {
        fields[key] = value as string
      }
    }

    return ipcRenderer.invoke('api:upload', { endpoint, files, fields })
  },

  // App info
  getVersion: () => ipcRenderer.invoke('app:getVersion'),

  // Backend status
  getBackendStatus: () => ipcRenderer.invoke('backend:status')
}

contextBridge.exposeInMainWorld('api', api)

// Type declarations for renderer
declare global {
  interface Window {
    api: typeof api
  }
}
