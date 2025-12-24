import { app, BrowserWindow, ipcMain } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import FormData from 'form-data'

let mainWindow: BrowserWindow | null = null
let pythonProcess: ChildProcess | null = null
let backendReady = false

const isDev = !app.isPackaged
const BACKEND_URL = 'http://127.0.0.1:8000'

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      nodeIntegration: false,
      contextIsolation: true
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

// IPC Handlers
ipcMain.handle('api:request', async (_event, { method, endpoint, data }) => {
  try {
    const options: RequestInit = {
      method,
      headers: { 'Content-Type': 'application/json' }
    }

    if (data && method !== 'GET') {
      options.body = JSON.stringify(data)
    }

    const response = await fetch(`${BACKEND_URL}${endpoint}`, options)

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }

    return await response.json()
  } catch (error: any) {
    console.error('API request failed:', error)
    throw new Error(error.message || 'Request failed')
  }
})

// File upload handler
ipcMain.handle('api:upload', async (_event, { endpoint, files, fields }) => {
  try {
    const formData = new FormData()

    // Add files
    for (const file of files) {
      formData.append(file.name, Buffer.from(file.data), {
        filename: file.filename,
        contentType: 'application/octet-stream'
      })
    }

    // Add other fields
    for (const [key, value] of Object.entries(fields)) {
      formData.append(key, value as string)
    }

    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
      method: 'POST',
      body: formData as any,
      headers: formData.getHeaders()
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }

    return await response.json()
  } catch (error: any) {
    console.error('Upload failed:', error)
    throw new Error(error.message || 'Upload failed')
  }
})

ipcMain.handle('app:getVersion', () => app.getVersion())

ipcMain.handle('backend:status', () => ({
  ready: backendReady,
  running: pythonProcess !== null
}))

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
