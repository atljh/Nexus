import { contextBridge, ipcRenderer } from 'electron'

// Only expose Electron-specific APIs that require IPC
// HTTP API calls are handled directly in the renderer via fetch
const electron = {
  getVersion: () => ipcRenderer.invoke('app:getVersion'),
  getBackendStatus: () => ipcRenderer.invoke('backend:status'),

  webview: {
    getPreloadPath: () => ipcRenderer.invoke('webview:getPreloadPath'),

    createSession: (
      accountId: number,
      proxy?: WebViewProxyConfig,
      deviceFingerprint?: WebViewDeviceFingerprint
    ) =>
      ipcRenderer.invoke('webview:createSession', {
        accountId,
        proxy: proxy ? JSON.parse(JSON.stringify(proxy)) : undefined,
        deviceFingerprint: deviceFingerprint ? JSON.parse(JSON.stringify(deviceFingerprint)) : undefined,
      }),

    getSession: (accountId: number) =>
      ipcRenderer.invoke('webview:getSession', { accountId }),

    getPartition: (accountId: number) =>
      ipcRenderer.invoke('webview:getPartition', { accountId }),

    clearSession: (accountId: number) =>
      ipcRenderer.invoke('webview:clearSession', { accountId }),

    destroySession: (accountId: number) =>
      ipcRenderer.invoke('webview:destroySession', { accountId }),

    onHealthStatus: (callback: (status: unknown) => void) => {
      ipcRenderer.on('webview:health-status', (_event, status) => callback(status))
    },

    removeHealthListener: () => {
      ipcRenderer.removeAllListeners('webview:health-status')
    },
  },
}

contextBridge.exposeInMainWorld('electron', electron)
