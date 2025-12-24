import { app, BrowserWindow, ipcMain } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'

let mainWindow: BrowserWindow | null = null
let pythonProcess: ChildProcess | null = null

const isDev = !app.isPackaged

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
  })

  pythonProcess.stderr?.on('data', (data) => {
    console.error(`[Python Error] ${data}`)
  })

  pythonProcess.on('close', (code) => {
    console.log(`[Python] Process exited with code ${code}`)
  })
}

function stopPythonBackend() {
  if (pythonProcess) {
    pythonProcess.kill()
    pythonProcess = null
  }
}

// IPC Handlers
ipcMain.handle('api:request', async (_event, { method, endpoint, data }) => {
  try {
    const response = await fetch(`http://127.0.0.1:8000${endpoint}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined
    })
    return await response.json()
  } catch (error) {
    console.error('API request failed:', error)
    throw error
  }
})

ipcMain.handle('app:getVersion', () => app.getVersion())

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
