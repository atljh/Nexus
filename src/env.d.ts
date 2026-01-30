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

interface Window {
  api: {
    request: (params: { method: string; endpoint: string; data?: unknown }) => Promise<unknown>
    get: (endpoint: string) => Promise<unknown>
    post: (endpoint: string, data: unknown) => Promise<unknown>
    put: (endpoint: string, data: unknown) => Promise<unknown>
    delete: (endpoint: string) => Promise<unknown>
    upload: (endpoint: string, files: UploadFile[], fields?: Record<string, string>) => Promise<unknown>
    getVersion: () => Promise<string>
    getBackendStatus: () => Promise<{ ready: boolean; running: boolean }>
  }
}
