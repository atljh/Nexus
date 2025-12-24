<script setup lang="ts">
import { ref, onMounted } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import Textarea from 'primevue/textarea'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'

interface Proxy {
  id: number
  host: string
  port: number
  type: string
  username: string | null
  password?: string | null
  status: 'unchecked' | 'valid' | 'invalid'
  accounts_count: number
  last_checked_at: string | null
}

const toast = useToast()
const proxies = ref<Proxy[]>([])
const showAddDialog = ref(false)
const showEditDialog = ref(false)
const loading = ref(false)
const checking = ref(false)
const selectedProxies = ref<Proxy[]>([])

const proxyTypes = [
  { label: 'SOCKS5', value: 'socks5' },
  { label: 'SOCKS4', value: 'socks4' },
  { label: 'HTTP', value: 'http' },
  { label: 'HTTPS', value: 'https' }
]

const newProxy = ref({
  type: 'socks5',
  host: '',
  port: '',
  username: '',
  password: ''
})

const editProxy = ref<Proxy | null>(null)
const bulkProxies = ref('')

onMounted(() => {
  loadProxies()
})

async function loadProxies() {
  loading.value = true
  try {
    const response = await window.api.get('/api/proxy')
    proxies.value = response.data || []
  } catch (error) {
    console.error('Failed to load proxies:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load proxies',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

function getStatusSeverity(status: string): "success" | "danger" | "warn" | "secondary" {
  switch (status) {
    case 'valid': return 'success'
    case 'invalid': return 'danger'
    default: return 'secondary'
  }
}

async function checkProxy(proxy: Proxy) {
  try {
    const response = await window.api.post(`/api/proxy/${proxy.id}/check`)

    toast.add({
      severity: response.status === 'valid' ? 'success' : 'error',
      summary: response.status === 'valid' ? 'Proxy Valid' : 'Proxy Invalid',
      detail: `${proxy.host}:${proxy.port}`,
      life: 3000
    })

    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Check Failed',
      detail: error.message || 'Failed to check proxy',
      life: 3000
    })
  }
}

async function checkAllProxies() {
  checking.value = true
  toast.add({
    severity: 'info',
    summary: 'Checking...',
    detail: 'Checking all proxies',
    life: 2000
  })

  try {
    const response = await window.api.post('/api/proxy/check-all')

    toast.add({
      severity: 'success',
      summary: 'Complete',
      detail: `Checked ${response.checked} proxies`,
      life: 3000
    })

    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.message || 'Failed to check proxies',
      life: 3000
    })
  } finally {
    checking.value = false
  }
}

async function addProxy() {
  // Handle bulk import
  if (bulkProxies.value.trim()) {
    const lines = bulkProxies.value.trim().split('\n').filter(l => l.trim())

    try {
      const response = await window.api.post('/api/proxy/bulk', {
        proxies: lines,
        type: newProxy.value.type
      })

      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: `Added ${response.created} proxies`,
        life: 3000
      })

      resetForm()
      showAddDialog.value = false
      loadProxies()
    } catch (error: any) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: error.message || 'Failed to add proxies',
        life: 3000
      })
    }
    return
  }

  // Handle single proxy
  if (!newProxy.value.host || !newProxy.value.port) {
    toast.add({
      severity: 'warn',
      summary: 'Warning',
      detail: 'Please enter host and port',
      life: 3000
    })
    return
  }

  try {
    await window.api.post('/api/proxy', {
      type: newProxy.value.type,
      host: newProxy.value.host,
      port: parseInt(newProxy.value.port),
      username: newProxy.value.username || null,
      password: newProxy.value.password || null
    })

    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Proxy added',
      life: 3000
    })

    resetForm()
    showAddDialog.value = false
    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.message || 'Failed to add proxy',
      life: 3000
    })
  }
}

function openEditDialog(proxy: Proxy) {
  editProxy.value = { ...proxy }
  showEditDialog.value = true
}

async function saveEditProxy() {
  if (!editProxy.value) return

  try {
    await window.api.put(`/api/proxy/${editProxy.value.id}`, {
      type: editProxy.value.type,
      host: editProxy.value.host,
      port: editProxy.value.port,
      username: editProxy.value.username || null,
      password: editProxy.value.password || null
    })

    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Proxy updated',
      life: 3000
    })

    showEditDialog.value = false
    editProxy.value = null
    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.message || 'Failed to update proxy',
      life: 3000
    })
  }
}

async function deleteProxy(proxy: Proxy) {
  if (!confirm(`Delete proxy ${proxy.host}:${proxy.port}?`)) {
    return
  }

  try {
    await window.api.delete(`/api/proxy/${proxy.id}`)

    toast.add({
      severity: 'success',
      summary: 'Deleted',
      detail: 'Proxy deleted',
      life: 3000
    })

    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.message || 'Failed to delete proxy',
      life: 3000
    })
  }
}

function resetForm() {
  newProxy.value = {
    type: 'socks5',
    host: '',
    port: '',
    username: '',
    password: ''
  }
  bulkProxies.value = ''
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Never'
  return new Date(dateStr).toLocaleString()
}
</script>

<template>
  <MainLayout>
    <Toast />
    <div class="proxy-page">
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl font-semibold">Proxy</h1>
        <div class="flex gap-2">
          <Button
            label="Add Proxy"
            icon="pi pi-plus"
            @click="showAddDialog = true"
          />
          <Button
            label="Check All"
            icon="pi pi-refresh"
            severity="secondary"
            :loading="checking"
            @click="checkAllProxies"
            :disabled="proxies.length === 0"
          />
        </div>
      </div>

      <ProgressBar v-if="checking" mode="indeterminate" style="height: 4px" class="mb-4" />

      <!-- Proxy table -->
      <div class="card-dashed">
        <DataTable
          v-model:selection="selectedProxies"
          :value="proxies"
          :loading="loading"
          paginator
          :rows="20"
          dataKey="id"
          class="p-datatable-dark"
        >
          <template #empty>
            <div class="text-center py-8 text-gray-500">
              <i class="pi pi-globe text-4xl mb-3 block"></i>
              <p>No proxies yet</p>
              <Button
                label="Add Proxy"
                icon="pi pi-plus"
                class="mt-3"
                @click="showAddDialog = true"
              />
            </div>
          </template>

          <Column field="id" header="ID" sortable style="width: 80px" />
          <Column header="Proxy" sortable>
            <template #body="{ data }">
              <div class="flex items-center gap-2">
                <div class="font-mono">{{ data.host }}:{{ data.port }}</div>
                <Tag :value="data.type.toUpperCase()" severity="secondary" class="text-xs" />
              </div>
            </template>
          </Column>
          <Column header="Auth" style="width: 100px">
            <template #body="{ data }">
              <Tag
                :value="data.username ? 'Yes' : 'No'"
                :severity="data.username ? 'success' : 'secondary'"
              />
            </template>
          </Column>
          <Column field="status" header="Status" sortable style="width: 120px">
            <template #body="{ data }">
              <Tag :value="data.status" :severity="getStatusSeverity(data.status)" />
            </template>
          </Column>
          <Column header="Accounts" style="width: 100px">
            <template #body="{ data }">
              <span class="text-gray-400">{{ data.accounts_count }}</span>
            </template>
          </Column>
          <Column header="Last Check" style="width: 180px">
            <template #body="{ data }">
              <span class="text-sm text-gray-500">{{ formatDate(data.last_checked_at) }}</span>
            </template>
          </Column>
          <Column header="Actions" style="width: 150px">
            <template #body="{ data }">
              <div class="flex gap-1">
                <Button
                  icon="pi pi-refresh"
                  severity="secondary"
                  text
                  rounded
                  v-tooltip="'Check'"
                  @click="checkProxy(data)"
                />
                <Button
                  icon="pi pi-pencil"
                  severity="secondary"
                  text
                  rounded
                  v-tooltip="'Edit'"
                  @click="openEditDialog(data)"
                />
                <Button
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  v-tooltip="'Delete'"
                  @click="deleteProxy(data)"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Add Proxy Dialog -->
      <Dialog
        v-model:visible="showAddDialog"
        header="Add Proxy"
        modal
        :style="{ width: '500px' }"
      >
        <div class="flex flex-col gap-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1">Type</label>
            <Dropdown
              v-model="newProxy.type"
              :options="proxyTypes"
              optionLabel="label"
              optionValue="value"
              class="w-full"
            />
          </div>

          <div class="grid grid-cols-3 gap-3">
            <div class="col-span-2">
              <label class="block text-sm text-gray-400 mb-1">Host</label>
              <InputText v-model="newProxy.host" placeholder="127.0.0.1" class="w-full" />
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Port</label>
              <InputText v-model="newProxy.port" placeholder="1080" class="w-full" />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-sm text-gray-400 mb-1">Username (optional)</label>
              <InputText v-model="newProxy.username" class="w-full" />
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Password (optional)</label>
              <InputText v-model="newProxy.password" type="password" class="w-full" />
            </div>
          </div>

          <div class="border-t border-gray-700 pt-4 mt-2">
            <label class="block text-sm text-gray-400 mb-1">
              Bulk Import (one per line)
            </label>
            <p class="text-xs text-gray-500 mb-2">
              Format: host:port or host:port:user:pass
            </p>
            <Textarea
              v-model="bulkProxies"
              placeholder="192.168.1.1:1080&#10;192.168.1.2:1080:user:pass"
              rows="4"
              class="w-full font-mono text-sm"
            />
          </div>

          <div class="flex justify-end gap-2 mt-4">
            <Button label="Cancel" severity="secondary" @click="showAddDialog = false; resetForm()" />
            <Button label="Add" icon="pi pi-plus" @click="addProxy" />
          </div>
        </div>
      </Dialog>

      <!-- Edit Proxy Dialog -->
      <Dialog
        v-model:visible="showEditDialog"
        header="Edit Proxy"
        modal
        :style="{ width: '500px' }"
      >
        <div v-if="editProxy" class="flex flex-col gap-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1">Type</label>
            <Dropdown
              v-model="editProxy.type"
              :options="proxyTypes"
              optionLabel="label"
              optionValue="value"
              class="w-full"
            />
          </div>

          <div class="grid grid-cols-3 gap-3">
            <div class="col-span-2">
              <label class="block text-sm text-gray-400 mb-1">Host</label>
              <InputText v-model="editProxy.host" class="w-full" />
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Port</label>
              <InputText v-model="editProxy.port" class="w-full" />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-sm text-gray-400 mb-1">Username</label>
              <InputText v-model="editProxy.username" class="w-full" />
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Password</label>
              <InputText v-model="editProxy.password" type="password" class="w-full" />
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-4">
            <Button label="Cancel" severity="secondary" @click="showEditDialog = false" />
            <Button label="Save" icon="pi pi-check" @click="saveEditProxy" />
          </div>
        </div>
      </Dialog>
    </div>
  </MainLayout>
</template>

<style scoped>
:deep(.p-datatable) {
  background: transparent;
}

:deep(.p-datatable-thead > tr > th) {
  background: #1a1a1a;
  border-color: #333;
  color: #888;
}

:deep(.p-datatable-tbody > tr) {
  background: transparent;
  border-color: #222;
}

:deep(.p-datatable-tbody > tr:hover) {
  background: #1a1a1a;
}

:deep(.p-datatable-tbody > tr > td) {
  border-color: #222;
}

.card-dashed {
  border: 2px dashed rgba(148, 163, 184, 0.3);
  border-radius: 1rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.2);
}
</style>
