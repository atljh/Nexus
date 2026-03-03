<script setup lang="ts">
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWebKSession } from '@/composables/useWebKSession'
import type { Account, WebKSessionData } from '@/types'

import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'

const props = defineProps<{
  visible: boolean
  account: Account | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

const { t } = useI18n()

// Refs
const accountRef = ref<Account | null>(null)
const webviewReady = ref(false)
const loadCount = ref(0)
let webviewEl: any = null // Direct DOM reference, not Vue ref

// Watch account prop
watch(
  () => props.account,
  (acc) => {
    accountRef.value = acc
  },
  { immediate: true }
)

// WebK session composable
const {
  state,
  sessionData,
  canOpen,
  cannotOpenReason,
  webkUrl,
  fetchSessionData,
  initializeWebView,
  cleanup,
} = useWebKSession(accountRef)

// Computed
const headerTitle = computed(() => {
  const acc = accountRef.value
  if (!acc) return ''

  const phone = acc.phone || acc.telegram_id?.toString() || 'Unknown'
  const proxy = acc.proxy
    ? `${acc.proxy.host}:${acc.proxy.port} (${acc.proxy.type})`
    : 'No proxy'

  return `${phone} | ${proxy}`
})

// Watch dialog visibility
watch(
  () => props.visible,
  async (visible) => {
    if (visible && accountRef.value) {
      await startViewer()
    } else {
      stopViewer()
    }
  }
)

// Methods
async function startViewer() {
  if (!canOpen.value) {
    state.value.error = t('webviewer.cannotOpen')
    return
  }

  state.value.loading = true
  state.value.error = null
  state.value.sessionInjected = false
  webviewReady.value = false
  loadCount.value = 0

  try {
    // Fetch session data from backend FIRST
    // (the webk-session response includes proxy with password,
    //  which the accounts API does not return)
    const response = await fetchSessionData()
    if (!response) {
      return
    }

    console.log('[WebViewer] Session data fetched, initializing webview with proxy credentials...')

    // Initialize webview session using proxy from webk-session response (has password)
    const initialized = await initializeWebView(response.proxy)
    if (!initialized) {
      return
    }

    // Set webview ready for rendering
    webviewReady.value = true

    // Wait for Vue to render the webview element
    await nextTick()

    // Get webview element directly from DOM (Vue ref may not work for custom elements)
    await waitForWebviewAndAttach()
  } catch (error) {
    state.value.error = error instanceof Error ? error.message : 'Unknown error'
    console.error('[WebViewer] Start failed:', error)
  } finally {
    state.value.loading = false
  }
}

/**
 * Poll for the webview element in DOM and attach event listeners.
 * Vue's template ref may not reliably trigger for Electron's <webview> custom element.
 */
async function waitForWebviewAndAttach(): Promise<void> {
  for (let i = 0; i < 20; i++) {
    const el = document.querySelector('.webviewer-webview') as any
    if (el) {
      webviewEl = el
      console.log('[WebViewer] Found webview element in DOM, attaching listeners')
      el.addEventListener('dom-ready', onDomReady)
      el.addEventListener('did-finish-load', onDidFinishLoad)
      el.addEventListener('did-fail-load', onDidFailLoad)
      el.addEventListener('console-message', onConsoleMessage)
      return
    }
    await new Promise(r => setTimeout(r, 100))
  }
  console.error('[WebViewer] Webview element not found in DOM after polling')
  state.value.error = 'Webview element not found'
}

function stopViewer() {
  if (webviewEl) {
    webviewEl.removeEventListener('dom-ready', onDomReady)
    webviewEl.removeEventListener('did-finish-load', onDidFinishLoad)
    webviewEl.removeEventListener('did-fail-load', onDidFailLoad)
    webviewEl.removeEventListener('console-message', onConsoleMessage)
    webviewEl = null
  }
  webviewReady.value = false
  loadCount.value = 0
  cleanup()
}

function handleClose() {
  stopViewer()
  emit('close')
  emit('update:visible', false)
}

async function handleReload() {
  if (webviewEl) {
    state.value.sessionInjected = false
    loadCount.value = 0
    webviewEl.reload()
  }
}

async function injectSessionToWebview(data: WebKSessionData): Promise<boolean> {
  if (!webviewEl) {
    console.error('[WebViewer] No webview element for injection')
    return false
  }

  try {
    const script = `
      (function() {
        try {
          // Step 1: Clear ALL localStorage (clean slate for WebK)
          localStorage.clear();

          // Step 2: Delete all IndexedDB databases to remove stale state
          if (indexedDB.databases) {
            indexedDB.databases().then(dbs => {
              dbs.forEach(db => {
                if (db.name) {
                  indexedDB.deleteDatabase(db.name);
                  console.log('[Nexus] Deleted IDB:', db.name);
                }
              });
            });
          }

          // Step 3: Inject session data using JSON.stringify for ALL values
          // (WebK internally stores everything via JSON.stringify)
          const sessionData = ${JSON.stringify(data)};
          for (const [key, value] of Object.entries(sessionData)) {
            if (value !== undefined && value !== null) {
              localStorage.setItem(key, JSON.stringify(value));
            }
          }

          // Verify injection
          const dc = localStorage.getItem('dc');
          const account1 = localStorage.getItem('account1');
          const allKeys = [];
          for (let i = 0; i < localStorage.length; i++) {
            allKeys.push(localStorage.key(i));
          }
          console.log('[Nexus] Session injected OK: dc=' + dc + ', account1_len=' + (account1 ? account1.length : 0) + ', keys=' + allKeys.join(','));
          return { success: true, dc: dc, keys: allKeys };
        } catch (error) {
          console.error('[Nexus] Session injection failed:', error);
          return { success: false, error: error.message };
        }
      })();
    `

    const result = await webviewEl.executeJavaScript(script)
    console.log('[WebViewer] Injection result:', JSON.stringify(result))
    state.value.sessionInjected = true
    return true
  } catch (error) {
    console.error('[WebViewer] executeJavaScript failed:', error)
    state.value.error = `Injection failed: ${error instanceof Error ? error.message : error}`
    return false
  }
}

// Native webview event handlers

function onDomReady() {
  loadCount.value++
  console.log(`[WebViewer] dom-ready (load #${loadCount.value})`)

  if (loadCount.value === 1 && sessionData.value && !state.value.sessionInjected) {
    console.log('[WebViewer] First load — injecting session...')
    injectSessionToWebview(sessionData.value).then((success) => {
      if (success && webviewEl) {
        console.log('[WebViewer] Injection done, reloading...')
        webviewEl.reload()
      }
    })
  } else if (loadCount.value === 2) {
    // Verify session persisted after reload
    webviewEl?.executeJavaScript(`
      (function() {
        const dc = localStorage.getItem('dc');
        const ua = localStorage.getItem('user_auth');
        const keys = [];
        for (let i = 0; i < localStorage.length; i++) keys.push(localStorage.key(i));
        console.log('[Nexus] After reload: dc=' + dc + ', user_auth=' + ua + ', keys=' + keys.join(','));
        return { dc, ua, keys };
      })();
    `).then((r: any) => console.log('[WebViewer] Post-reload localStorage:', JSON.stringify(r)))
      .catch((e: any) => console.error('[WebViewer] Post-reload check failed:', e))
  }
}

function onDidFinishLoad() {
  console.log(`[WebViewer] did-finish-load (load #${loadCount.value})`)
}

function onDidFailLoad(event: any) {
  const errorCode = event?.errorCode ?? 'unknown'
  const errorDesc = event?.errorDescription ?? 'unknown'
  console.error(`[WebViewer] did-fail-load: code=${errorCode} desc=${errorDesc}`)
  // Ignore -3 (aborted/cancelled) — happens during reload
  if (errorCode !== -3) {
    state.value.error = `Load failed: ${errorDesc} (code: ${errorCode})`
  }
}

function onConsoleMessage(event: any) {
  const msg = event?.message ?? ''
  const level = event?.level ?? 0
  const prefix = level === 2 ? 'ERROR' : level === 1 ? 'WARN' : 'LOG'
  console.log(`[WebK:${prefix}] ${msg}`)
}

// Cleanup
onUnmounted(() => {
  stopViewer()
})
</script>

<template>
  <Teleport to="body">
    <Transition name="webviewer">
      <div v-if="visible" class="webviewer-overlay" @click.self="handleClose">
        <div class="webviewer-popup">
          <!-- Header -->
          <div class="webviewer-header">
            <span class="webviewer-title">{{ headerTitle }}</span>
            <div class="webviewer-controls">
              <Button
                icon="pi pi-refresh"
                text
                rounded
                size="small"
                :disabled="state.loading || !webviewReady"
                @click="handleReload"
                v-tooltip.bottom="t('webviewer.reload')"
              />
              <Button
                icon="pi pi-times"
                text
                rounded
                size="small"
                severity="secondary"
                @click="handleClose"
              />
            </div>
          </div>

          <!-- Content -->
          <div class="webviewer-content">
            <!-- Loading state -->
            <div v-if="state.loading && !webviewReady" class="webviewer-loading">
              <ProgressSpinner style="width: 40px; height: 40px" />
              <span>{{ t('webviewer.initializing') }}</span>
            </div>

            <!-- Error state -->
            <div v-else-if="state.error" class="webviewer-error">
              <i class="pi pi-exclamation-triangle" style="font-size: 2rem; color: var(--red-500)"></i>
              <span>{{ state.error }}</span>
              <Button
                :label="t('webviewer.reload')"
                icon="pi pi-refresh"
                size="small"
                @click="startViewer"
              />
            </div>

            <!-- Cannot open state -->
            <div v-else-if="!canOpen" class="webviewer-error">
              <i class="pi pi-info-circle" style="font-size: 2rem; color: var(--yellow-500)"></i>
              <span>{{ cannotOpenReason ? t(`webviewer.${cannotOpenReason}`) : t('webviewer.cannotOpen') }}</span>
            </div>

            <!-- Webview -->
            <webview
              v-else-if="webviewReady && state.partition"
              :src="webkUrl"
              :partition="state.partition"
              class="webviewer-webview"
              allowpopups
            />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.webviewer-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.webviewer-popup {
  width: 90vw;
  max-width: 1200px;
  height: 85vh;
  background: var(--surface-ground);
  border-radius: 12px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--surface-border);
}

.webviewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--surface-section);
  border-bottom: 1px solid var(--surface-border);
  flex-shrink: 0;
}

.webviewer-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  margin-right: 8px;
}

.webviewer-controls {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.webviewer-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
}

.webviewer-loading,
.webviewer-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-color-secondary);
  font-size: 14px;
  text-align: center;
  padding: 20px;
}

.webviewer-webview {
  flex: 1;
  width: 100%;
  height: 100%;
  border: none;
}

/* Transitions */
.webviewer-enter-active,
.webviewer-leave-active {
  transition: opacity 0.2s ease;
}

.webviewer-enter-active .webviewer-popup,
.webviewer-leave-active .webviewer-popup {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.webviewer-enter-from,
.webviewer-leave-to {
  opacity: 0;
}

.webviewer-enter-from .webviewer-popup,
.webviewer-leave-to .webviewer-popup {
  transform: scale(0.95);
  opacity: 0;
}
</style>
