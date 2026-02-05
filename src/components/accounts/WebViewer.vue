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
const webviewRef = ref<HTMLWebViewElement | null>(null)
const webviewReady = ref(false)
const injecting = ref(false)

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
  preloadPath,
  canOpen,
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
  webviewReady.value = false

  try {
    // Initialize webview session with proxy
    const initialized = await initializeWebView()
    if (!initialized) {
      return
    }

    // Fetch session data from backend
    const response = await fetchSessionData()
    if (!response) {
      return
    }

    // Wait for webview to be ready
    await nextTick()

    // Set webview ready for rendering
    webviewReady.value = true
  } catch (error) {
    state.value.error = error instanceof Error ? error.message : 'Unknown error'
    console.error('[WebViewer] Start failed:', error)
  } finally {
    state.value.loading = false
  }
}

function stopViewer() {
  webviewReady.value = false
  cleanup()
}

function handleClose() {
  stopViewer()
  emit('close')
  emit('update:visible', false)
}

async function handleReload() {
  if (webviewRef.value) {
    webviewRef.value.reload()
  }
}

async function injectSessionToWebview(data: WebKSessionData) {
  if (!webviewRef.value) return

  injecting.value = true

  try {
    // Execute injection script in webview
    const script = `
      (function() {
        try {
          // Clear existing session data
          const keysToRemove = [];
          for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && (key.startsWith('dc') || key.startsWith('user_auth') || key.startsWith('account'))) {
              keysToRemove.push(key);
            }
          }
          keysToRemove.forEach(key => localStorage.removeItem(key));

          // Inject new session data
          const sessionData = ${JSON.stringify(data)};
          for (const [key, value] of Object.entries(sessionData)) {
            if (value !== undefined && value !== null) {
              if (typeof value === 'object') {
                localStorage.setItem(key, JSON.stringify(value));
              } else {
                localStorage.setItem(key, String(value));
              }
            }
          }

          console.log('[Nexus] Session injected successfully');
          return { success: true };
        } catch (error) {
          console.error('[Nexus] Session injection failed:', error);
          return { success: false, error: error.message };
        }
      })();
    `

    await webviewRef.value.executeJavaScript(script)
    state.value.sessionInjected = true
  } catch (error) {
    console.error('[WebViewer] Injection failed:', error)
    state.value.error = 'Session injection failed'
  } finally {
    injecting.value = false
  }
}

// Webview event handlers
function onWebviewDidFinishLoad() {
  console.log('[WebViewer] Webview loaded')

  // Inject session after page loads
  if (sessionData.value && !state.value.sessionInjected) {
    injectSessionToWebview(sessionData.value).then(() => {
      // Reload after injection
      if (webviewRef.value) {
        webviewRef.value.reload()
      }
    })
  }
}

function onWebviewDidFailLoad(event: Event) {
  const e = event as unknown as { errorCode: number; errorDescription: string }
  console.error('[WebViewer] Load failed:', e.errorCode, e.errorDescription)
  // Ignore -3 (aborted) errors
  if (e.errorCode !== -3) {
    state.value.error = `Load failed: ${e.errorDescription}`
  }
}

function onWebviewConsoleMessage(event: Event) {
  const e = event as unknown as { message: string; level: number }
  console.log('[WebK]', e.message)
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
              <span>{{ t('webviewer.cannotOpen') }}</span>
            </div>

            <!-- Webview -->
            <webview
              v-else-if="webviewReady && state.partition"
              ref="webviewRef"
              :src="webkUrl"
              :partition="state.partition"
              :preload="preloadPath || undefined"
              class="webviewer-webview"
              allowpopups
              @did-finish-load="onWebviewDidFinishLoad"
              @did-fail-load="onWebviewDidFailLoad"
              @console-message="onWebviewConsoleMessage"
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
  width: 420px;
  height: 680px;
  max-height: 90vh;
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
