import { app, BrowserWindow, ipcMain } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import { webViewManager, ProxyConfig, DeviceFingerprint } from './webview-manager'

let mainWindow: BrowserWindow | null = null
let pythonProcess: ChildProcess | null = null
let backendReady = false

const isDev = !app.isPackaged

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
    ? path.join(__dirname, '../../backend/.venv/bin/python')
    : path.join(process.resourcesPath, 'backend/main')

  const scriptPath = isDev
    ? path.join(__dirname, '../../backend/main.py')
    : null

  if (isDev && scriptPath) {
    pythonProcess = spawn(pythonPath, [scriptPath], {
      cwd: path.join(__dirname, '../../backend'),
      env: { ...process.env, PYTHONUNBUFFERED: '1' }
    })
  } else {
    pythonProcess = spawn(pythonPath, [], {
      env: { ...process.env }
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
  })
}

function stopPythonBackend() {
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

app.on('before-quit', () => {
  stopPythonBackend()
})
