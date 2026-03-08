import { app, BrowserWindow, ipcMain } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import * as fs from 'fs'
import path from 'path'
import { webViewManager, ProxyConfig, DeviceFingerprint } from './webview-manager'

let mainWindow: BrowserWindow | null = null
let pythonProcess: ChildProcess | null = null
let backendReady = false
let backendRestartCount = 0
let intentionalStop = false
const MAX_BACKEND_RESTARTS = 3

const isDev = !app.isPackaged

function resolveDevPythonPath(): string {
  const candidates = [
    path.join(__dirname, '../../backend/.venv/bin/python'),
    path.join(__dirname, '../../backend/.venv/Scripts/python.exe')
  ]
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate
  }
  return candidates[0]
}

function resolvePackagedBackendPath(): string {
  const base = path.join(process.resourcesPath, 'backend/main')
  const candidates = [
    path.join(base, 'main'),
    path.join(base, 'main.exe'),
    base,
    `${base}.exe`
  ]
  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
        return candidate
      }
    } catch (error) {
      console.warn('[Python] Failed to inspect backend candidate:', candidate, error)
    }
  }
  return base
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, '../preload/preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webviewTag: true
    },
    titleBarStyle: 'hiddenInset',
    show: false
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../../dist/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

function startPythonBackend() {
  const pythonPath = isDev
    ? resolveDevPythonPath()
    : resolvePackagedBackendPath()

  const scriptPath = isDev
    ? path.join(__dirname, '../../backend/main.py')
    : null

  if (isDev && scriptPath) {
    pythonProcess = spawn(pythonPath, [scriptPath], {
      cwd: path.join(__dirname, '../../backend'),
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        NEXUS_BACKEND_RELOAD: '1',
      }
    })
  } else {
    pythonProcess = spawn(pythonPath, [], {
      env: {
        ...process.env,
        NEXUS_BACKEND_RELOAD: '0',
      }
    })
  }

  pythonProcess.stdout?.on('data', (data) => {
    console.log(`[Python] ${data}`)
    if (data.toString().includes('Uvicorn running')) {
      backendReady = true
    }
  })

  pythonProcess.stderr?.on('data', (data) => {
    console.error(`[Python Error] ${data}`)
  })

  pythonProcess.on('close', (code) => {
    console.log(`[Python] Process exited with code ${code}`)
    backendReady = false
    pythonProcess = null

    if (!intentionalStop && code !== 0 && backendRestartCount < MAX_BACKEND_RESTARTS) {
      backendRestartCount++
      const delay = backendRestartCount * 2000
      console.log(`[Python] Restarting in ${delay}ms (attempt ${backendRestartCount}/${MAX_BACKEND_RESTARTS})`)
      setTimeout(() => startPythonBackend(), delay)
    }
  })
}

function stopPythonBackend() {
  intentionalStop = true
  if (pythonProcess) {
    pythonProcess.kill()
    pythonProcess = null
    backendReady = false
  }
}

// IPC Handlers (API calls are now handled directly in preload via fetch)
ipcMain.handle('app:getVersion', () => app.getVersion())

ipcMain.handle('backend:status', () => ({
  ready: backendReady,
  running: pythonProcess !== null
}))

// WebView IPC Handlers

// Get preload path for webview
ipcMain.handle('webview:getPreloadPath', () => {
  const preloadPath = path.join(__dirname, '../preload/webview-preload.js')
  // Webview preload requires file:// protocol
  return `file://${preloadPath}`
})

// Create webview session with proxy
ipcMain.handle(
  'webview:createSession',
  async (
    _event,
    {
      accountId,
      proxy,
      deviceFingerprint,
    }: {
      accountId: number
      proxy?: ProxyConfig
      deviceFingerprint?: DeviceFingerprint
    }
  ) => {
    try {
      const session = await webViewManager.createSession(accountId, proxy, deviceFingerprint)
      return {
        success: true,
        partition: session.partition,
      }
    } catch (error: unknown) {
      console.error('[WebView] Failed to create session:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      }
    }
  }
)

// Get session info
ipcMain.handle('webview:getSession', (_event, { accountId }: { accountId: number }) => {
  const session = webViewManager.getSession(accountId)
  if (session) {
    return {
      exists: true,
      partition: session.partition,
      accountId: session.accountId,
    }
  }
  return { exists: false }
})

// Clear session data
ipcMain.handle('webview:clearSession', async (_event, { accountId }: { accountId: number }) => {
  try {
    await webViewManager.clearSession(accountId)
    return { success: true }
  } catch (error: unknown) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
})

// Destroy session
ipcMain.handle('webview:destroySession', async (_event, { accountId }: { accountId: number }) => {
  try {
    await webViewManager.destroySession(accountId)
    return { success: true }
  } catch (error: unknown) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    }
  }
})

// Get partition name for account
ipcMain.handle('webview:getPartition', (_event, { accountId }: { accountId: number }) => {
  return webViewManager.getPartitionName(accountId)
})

// Listen for webview events from renderer
ipcMain.on('webview:ready', () => {
  console.log('[WebView] Webview ready')
})

ipcMain.on('webview:session-injected', (_event, data) => {
  console.log('[WebView] Session injected:', data)
})

ipcMain.on('webview:health-update', (_event, status) => {
  // Forward health updates to renderer if needed
  mainWindow?.webContents.send('webview:health-status', status)
})

// Global error handlers
process.on('uncaughtException', (error) => {
  console.error('[Main] Uncaught exception:', error)
})

process.on('unhandledRejection', (reason) => {
  console.error('[Main] Unhandled rejection:', reason)
})

// App lifecycle
app.whenReady().then(() => {
  startPythonBackend()
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  stopPythonBackend()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', async () => {
  await webViewManager.destroyAllSessions()
  stopPythonBackend()
})
