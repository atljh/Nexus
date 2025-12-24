<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Toast from 'primevue/toast'

const appVersion = ref('')
const backendStatus = ref<'connecting' | 'connected' | 'error'>('connecting')

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
  <div class="app-container dark">
    <Toast />

    <!-- Loading screen while connecting to backend -->
    <div v-if="backendStatus === 'connecting'" class="loading-screen">
      <div class="loading-content">
        <i class="pi pi-spin pi-spinner text-4xl text-purple-500"></i>
        <p class="mt-4 text-gray-400">Connecting to backend...</p>
      </div>
    </div>

    <!-- Error screen if backend fails -->
    <div v-else-if="backendStatus === 'error'" class="loading-screen">
      <div class="loading-content">
        <i class="pi pi-exclamation-triangle text-4xl text-red-500"></i>
        <p class="mt-4 text-gray-400">Failed to connect to backend</p>
        <p class="text-sm text-gray-500">Retrying...</p>
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
  background: #0f0f0f;
  color: #e5e5e5;
}

.loading-screen {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}

.loading-content {
  text-align: center;
}

.version-badge {
  position: fixed;
  bottom: 8px;
  right: 12px;
  font-size: 11px;
  color: #666;
}
</style>
