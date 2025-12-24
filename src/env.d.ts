/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface Window {
  api: {
    request: (params: { method: string; endpoint: string; data?: unknown }) => Promise<unknown>
    get: (endpoint: string) => Promise<unknown>
    post: (endpoint: string, data: unknown) => Promise<unknown>
    put: (endpoint: string, data: unknown) => Promise<unknown>
    delete: (endpoint: string) => Promise<unknown>
    getVersion: () => Promise<string>
  }
}
