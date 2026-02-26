/**
 * Preload script for Telegram WebK webview
 *
 * This script runs in the webview context and handles:
 * - Session injection into WebK's localStorage
 * - Health status reporting back to main process
 * - Communication with parent window via IPC
 */

import { contextBridge, ipcRenderer } from 'electron'

export interface WebKSessionData {
  dc: number
  [key: string]: unknown // dc2_auth_key, dc2_server_salt, etc.
  user_auth?: {
    dcID: number
    id: number
  }
  account1?: Record<string, unknown>
  auth_key_fingerprint?: string
}

export interface WebKHealthStatus {
  sessionPresent: boolean
  connected: boolean
  dcId: number | null
  userId: number | null
  timestamp: number
}

// Track health status
let healthStatus: WebKHealthStatus = {
  sessionPresent: false,
  connected: false,
  dcId: null,
  userId: null,
  timestamp: Date.now(),
}

/**
 * Inject session data into WebK's localStorage
 */
function injectSession(sessionData: WebKSessionData): boolean {
  try {
    console.log('[WebKPreload] Injecting session data')

    // Clear existing session data first
    const keysToRemove: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && (key.startsWith('dc') || key.startsWith('user_auth') || key.startsWith('account'))) {
        keysToRemove.push(key)
      }
    }
    keysToRemove.forEach((key) => localStorage.removeItem(key))

    // Inject new session data
    for (const [key, value] of Object.entries(sessionData)) {
      if (value !== undefined && value !== null) {
        if (typeof value === 'object') {
          localStorage.setItem(key, JSON.stringify(value))
        } else {
          localStorage.setItem(key, String(value))
        }
      }
    }

    healthStatus.sessionPresent = true
    healthStatus.dcId = sessionData.dc
    healthStatus.userId = sessionData.user_auth?.id || null
    healthStatus.timestamp = Date.now()

    console.log(`[WebKPreload] Session injected for DC${sessionData.dc}`)

    // Notify main process
    ipcRenderer.send('webview:session-injected', {
      success: true,
      dcId: sessionData.dc,
      userId: healthStatus.userId,
    })

    return true
  } catch (error) {
    console.error('[WebKPreload] Session injection failed:', error)
    ipcRenderer.send('webview:session-injected', {
      success: false,
      error: String(error),
    })
    return false
  }
}

/**
 * Clear all session data from localStorage
 */
function clearSession(): void {
  try {
    console.log('[WebKPreload] Clearing session data...')

    const keysToRemove: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key) {
        keysToRemove.push(key)
      }
    }
    keysToRemove.forEach((key) => localStorage.removeItem(key))

    healthStatus = {
      sessionPresent: false,
      connected: false,
      dcId: null,
      userId: null,
      timestamp: Date.now(),
    }

    console.log('[WebKPreload] Session cleared')
  } catch (error) {
    console.error('[WebKPreload] Clear session failed:', error)
  }
}

/**
 * Get current health status
 */
function getHealthStatus(): WebKHealthStatus {
  // Try to detect connection status from WebK's state
  try {
    // WebK stores connection state in various places
    const mtState = localStorage.getItem('mt_state')
    if (mtState) {
      const state = JSON.parse(mtState)
      healthStatus.connected = state.connected || false
    }
  } catch {
    // Ignore parsing errors
  }

  healthStatus.timestamp = Date.now()
  return { ...healthStatus }
}

/**
 * Monitor WebK's connection status
 */
let healthIntervalId: ReturnType<typeof setInterval> | null = null

function startHealthMonitoring(intervalMs: number = 5000): void {
  if (healthIntervalId !== null) {
    clearInterval(healthIntervalId)
  }
  healthIntervalId = setInterval(() => {
    const status = getHealthStatus()
    ipcRenderer.send('webview:health-update', status)
  }, intervalMs)
}

// Expose API to webview
contextBridge.exposeInMainWorld('nexusWebK', {
  injectSession,
  clearSession,
  getHealthStatus,
  startHealthMonitoring,

  // Report ready
  ready: () => {
    console.log('[WebKPreload] WebK preload ready')
    ipcRenderer.send('webview:ready')
  },
})

// Listen for commands from main process
ipcRenderer.on('webview:inject', (_event, sessionData: WebKSessionData) => {
  injectSession(sessionData)
  // Reload page after injection
  setTimeout(() => {
    window.location.reload()
  }, 100)
})

ipcRenderer.on('webview:clear', () => {
  clearSession()
})

ipcRenderer.on('webview:reload', () => {
  window.location.reload()
})

// Auto-start health monitoring when page loads
window.addEventListener('DOMContentLoaded', () => {
  console.log('[WebKPreload] DOM loaded, starting health monitoring')
  startHealthMonitoring()
})

// Log ready state
console.log('[WebKPreload] Preload script loaded')
