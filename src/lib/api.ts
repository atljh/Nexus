const BACKEND_URL = 'http://127.0.0.1:8000'

async function apiRequest(method: string, endpoint: string, data?: unknown): Promise<unknown> {
  const options: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' }
  }

  if (data !== undefined && data !== null && method !== 'GET') {
    options.body = JSON.stringify(data)
  }

  const response = await fetch(`${BACKEND_URL}${endpoint}`, options)
  const text = await response.text()

  if (!response.ok) {
    let errorMessage = response.statusText
    try {
      const errorData = JSON.parse(text)
      errorMessage = typeof errorData.detail === 'string'
        ? errorData.detail
        : JSON.stringify(errorData.detail)
    } catch {}
    throw new Error(errorMessage || `HTTP ${response.status}`)
  }

  return JSON.parse(text)
}

async function apiUpload(endpoint: string, files: UploadFile[], fields: Record<string, string> = {}): Promise<unknown> {
  const formData = new FormData()

  for (const file of files) {
    const blob = new Blob([file.data as BlobPart], { type: 'application/octet-stream' })
    formData.append(file.name, blob, file.filename)
  }

  for (const [key, value] of Object.entries(fields || {})) {
    formData.append(key, value)
  }

  const response = await fetch(`${BACKEND_URL}${endpoint}`, {
    method: 'POST',
    body: formData
  })
  const text = await response.text()

  if (!response.ok) {
    let errorMessage = response.statusText
    try {
      const errorData = JSON.parse(text)
      errorMessage = typeof errorData.detail === 'string'
        ? errorData.detail
        : JSON.stringify(errorData.detail)
    } catch {}
    throw new Error(errorMessage || `HTTP ${response.status}`)
  }

  return JSON.parse(text)
}

function getElectron(): Window['electron'] {
  return (window as Window & { electron: Window['electron'] }).electron
}

const fallbackWebview: Window['api']['webview'] = {
  getPreloadPath: () => Promise.resolve(''),
  createSession: () => Promise.resolve({ success: false, error: 'Not available' }),
  getSession: () => Promise.resolve({ exists: false }),
  getPartition: () => Promise.resolve(''),
  clearSession: () => Promise.resolve({ success: false }),
  destroySession: () => Promise.resolve({ success: false }),
  onHealthStatus: () => {},
  removeHealthListener: () => {},
}

// Direct fetch API — no IPC, no contextBridge, no structured clone
export function installApi() {
  const api: Window['api'] = {
    request: (params) => apiRequest(params.method, params.endpoint, params.data),
    get: (endpoint) => apiRequest('GET', endpoint),
    post: (endpoint, data) => apiRequest('POST', endpoint, data),
    put: (endpoint, data) => apiRequest('PUT', endpoint, data),
    delete: (endpoint) => apiRequest('DELETE', endpoint),
    upload: (endpoint, files, fields = {}) => apiUpload(endpoint, files, fields),

    // Electron APIs — lazy access to window.electron (set by preload)
    getVersion: () => getElectron().getVersion(),
    getBackendStatus: () => getElectron().getBackendStatus(),

    get webview() {
      return getElectron()?.webview ?? fallbackWebview
    },
  }

  ;(window as Window & { api: Window['api'] }).api = api
}
