<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import Toast from 'primevue/toast'
import { useThemeStore } from '@/stores/useThemeStore'

const themeStore = useThemeStore()

const appVersion = ref('')
const backendStatus = ref<'connecting' | 'connected' | 'error'>('connecting')

const themeClass = computed(() => themeStore.resolvedTheme)

onMounted(async () => {
  // Get app version
  try {
    appVersion.value = await window.api.getVersion()
  } catch {
    appVersion.value = '1.0.0'
  }

  // Check backend connection
  checkBackend()
})

async function checkBackend() {
  try {
    await window.api.get('/health')
    backendStatus.value = 'connected'
  } catch {
    backendStatus.value = 'error'
    // Retry in 2 seconds
    setTimeout(checkBackend, 2000)
  }
}
</script>

<template>
  <div class="app-container" :class="themeClass">
    <Toast />

    <!-- Loading screen while connecting to backend -->
    <div v-if="backendStatus === 'connecting'" class="loading-screen">
      <div class="loading-content">
        <div class="loading-logo">
          <div class="loading-icon">
            <i class="pi pi-bolt"></i>
          </div>
          <span class="loading-brand">Nexus</span>
        </div>
        <div class="loading-spinner">
          <div class="spinner"></div>
        </div>
        <p class="loading-text">Connecting to backend...</p>
      </div>
    </div>

    <!-- Error screen if backend fails -->
    <div v-else-if="backendStatus === 'error'" class="loading-screen">
      <div class="loading-content">
        <div class="loading-logo">
          <div class="loading-icon loading-icon-error">
            <i class="pi pi-exclamation-triangle"></i>
          </div>
        </div>
        <p class="loading-text">Failed to connect to backend</p>
        <p class="loading-subtext">Retrying...</p>
      </div>
    </div>

    <!-- Main app -->
    <router-view v-else />

    <!-- Version badge -->
    <div class="version-badge">
      v{{ appVersion }}
    </div>
  </div>
</template>

<style>
.app-container {
  min-height: 100vh;
  background: var(--color-bg-base, #09090b);
  color: var(--color-text-primary, #e5e5e5);
  transition: background-color 0.2s ease, color 0.2s ease;
}

.app-container.dark {
  background: #09090b;
  color: #e5e5e5;
}

.app-container.light {
  background: #f8fafc;
  color: #0f172a;
}

.loading-screen {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.loading-logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.loading-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
  box-shadow: 0 4px 20px rgba(168, 85, 247, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
}

.loading-icon-error {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  box-shadow: 0 4px 20px rgba(239, 68, 68, 0.35);
}

.loading-brand {
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, #c084fc, #a855f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.3px;
}

.loading-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(168, 85, 247, 0.15);
  border-top-color: #a855f7;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 14px;
  color: #8b8f9a;
}

.loading-subtext {
  font-size: 13px;
  color: #4b5563;
  margin-top: -12px;
}

.version-badge {
  position: fixed;
  bottom: 8px;
  right: 12px;
  font-size: 11px;
  color: #55555e;
  font-variant-numeric: tabular-nums;
}

.light .version-badge {
  color: #94a3b8;
}
</style>
