<script setup lang="ts">
import { ref, onMounted } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import FileUpload from 'primevue/fileupload'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'

interface Proxy {
  id: number
  host: string
  port: number
  type: string
}

interface Account {
  id: number
  telegram_id: number | null
  username: string | null
  phone: string | null
  first_name: string | null
  last_name: string | null
  status: string
  proxy: Proxy | null
  proxy_id: number | null
  group: { id: number; name: string } | null
  group_id: number | null
  tags: { id: number; name: string; color: string }[]
}

const toast = useToast()
const accounts = ref<Account[]>([])
const proxies = ref<Proxy[]>([])
const showImportDialog = ref(false)
const loading = ref(false)
const importing = ref(false)
const selectedProxy = ref<number | null>(null)
const sessionStringInput = ref('')

onMounted(() => {
  loadAccounts()
  loadProxies()
})

async function loadAccounts() {
  loading.value = true
  try {
    const response = await window.api.get('/api/accounts')
    accounts.value = response.data || []
  } catch (error) {
    console.error('Failed to load accounts:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load accounts',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

async function loadProxies() {
  try {
    const response = await window.api.get('/api/proxy')
    proxies.value = response.data || []
  } catch (error) {
    console.error('Failed to load proxies:', error)
  }
}

async function importTdata(event: any) {
  const file = event.files[0]
  if (!file) return

  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    if (selectedProxy.value) {
      formData.append('proxy_id', selectedProxy.value.toString())
    }

    const response = await window.api.upload('/api/accounts/import/tdata', formData)

    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: response.message || 'Account imported successfully',
      life: 3000
    })

    showImportDialog.value = false
    loadAccounts()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Import Failed',
      detail: error.message || 'Failed to import tdata',
      life: 5000
    })
  } finally {
    importing.value = false
  }
}

async function importJson(event: any) {
  const file = event.files[0]
  if (!file) return

  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    if (selectedProxy.value) {
      formData.append('proxy_id', selectedProxy.value.toString())
    }

    const response = await window.api.upload('/api/accounts/import/json', formData)

    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: `Imported ${response.imported} accounts`,
      life: 3000
    })

    if (response.errors?.length > 0) {
      toast.add({
        severity: 'warn',
        summary: 'Some imports failed',
        detail: `${response.errors.length} accounts failed to import`,
        life: 5000
      })
    }

    showImportDialog.value = false
    loadAccounts()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Import Failed',
      detail: error.message || 'Failed to import JSON sessions',
      life: 5000
    })
  } finally {
    importing.value = false
  }
}

async function importSessionString() {
  if (!sessionStringInput.value.trim()) {
    toast.add({
      severity: 'warn',
      summary: 'Warning',
      detail: 'Please enter a session string',
      life: 3000
    })
    return
  }

  importing.value = true
  try {
    await window.api.post('/api/accounts/import/session-string', {
      session_string: sessionStringInput.value.trim(),
      proxy_id: selectedProxy.value
    })

    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Account imported successfully',
      life: 3000
    })

    sessionStringInput.value = ''
    showImportDialog.value = false
    loadAccounts()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Import Failed',
      detail: error.message || 'Failed to import session',
      life: 5000
    })
  } finally {
    importing.value = false
  }
}

async function checkAccount(account: Account) {
  try {
    const response = await window.api.post(`/api/accounts/${account.id}/check`)

    if (response.valid) {
      toast.add({
        severity: 'success',
        summary: 'Account Valid',
        detail: `@${response.user_info?.username || account.telegram_id} is working`,
        life: 3000
      })
    } else {
      toast.add({
        severity: 'error',
        summary: 'Account Invalid',
        detail: response.error || 'Session is not valid',
        life: 5000
      })
    }

    loadAccounts()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Check Failed',
      detail: error.message || 'Failed to check account',
      life: 3000
    })
  }
}

async function deleteAccount(account: Account) {
  if (!confirm(`Delete account @${account.username || account.telegram_id}?`)) {
    return
  }

  try {
    await window.api.delete(`/api/accounts/${account.id}`)
    toast.add({
      severity: 'success',
      summary: 'Deleted',
      detail: 'Account deleted successfully',
      life: 3000
    })
    loadAccounts()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.message || 'Failed to delete account',
      life: 3000
    })
  }
}

async function checkAllAccounts() {
  toast.add({
    severity: 'info',
    summary: 'Checking...',
    detail: 'Checking all accounts in background',
    life: 3000
  })

  for (const account of accounts.value) {
    if (account.status !== 'valid') {
      await checkAccount(account)
    }
  }
}

function getStatusSeverity(status: string): "success" | "info" | "warn" | "danger" | "secondary" | "contrast" | undefined {
  switch (status) {
    case 'valid': return 'success'
    case 'invalid': return 'danger'
    case 'banned': return 'danger'
    case 'spamblock': return 'warn'
    case 'session_expired': return 'warn'
    case 'checking': return 'info'
    default: return 'secondary'
  }
}

function getDisplayName(account: Account): string {
  if (account.username) return `@${account.username}`
  if (account.first_name) return account.first_name
  if (account.telegram_id) return `ID: ${account.telegram_id}`
  if (account.phone) return account.phone
  return 'Unknown'
}
</script>

<template>
  <MainLayout>
    <Toast />
    <div class="accounts-page">
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl font-semibold">Accounts</h1>
        <div class="flex gap-2">
          <Button
            label="Import"
            icon="pi pi-upload"
            severity="secondary"
            @click="showImportDialog = true"
          />
          <Button
            label="Check All"
            icon="pi pi-refresh"
            severity="secondary"
            @click="checkAllAccounts"
            :disabled="accounts.length === 0"
          />
        </div>
      </div>

      <!-- Accounts table -->
      <div class="card-dashed">
        <DataTable
          :value="accounts"
          :loading="loading"
          paginator
          :rows="20"
          dataKey="id"
          class="p-datatable-dark"
        >
          <template #empty>
            <div class="text-center py-8 text-gray-500">
              <i class="pi pi-users text-4xl mb-3 block"></i>
              <p>No accounts yet</p>
              <Button
                label="Import Accounts"
                icon="pi pi-upload"
                class="mt-3"
                @click="showImportDialog = true"
              />
            </div>
          </template>

          <Column field="id" header="ID" sortable style="width: 80px" />
          <Column header="Account" sortable>
            <template #body="{ data }">
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center text-sm font-medium">
                  {{ (data.first_name || data.username || '?')[0].toUpperCase() }}
                </div>
                <div>
                  <div class="font-medium">{{ getDisplayName(data) }}</div>
                  <div v-if="data.phone" class="text-xs text-gray-500">{{ data.phone }}</div>
                </div>
              </div>
            </template>
          </Column>
          <Column field="status" header="Status" sortable style="width: 120px">
            <template #body="{ data }">
              <Tag :value="data.status" :severity="getStatusSeverity(data.status)" />
            </template>
          </Column>
          <Column header="Proxy" style="width: 180px">
            <template #body="{ data }">
              <span v-if="data.proxy" class="text-sm">
                {{ data.proxy.host }}:{{ data.proxy.port }}
              </span>
              <span v-else class="text-gray-500 text-sm">No proxy</span>
            </template>
          </Column>
          <Column header="Group" style="width: 150px">
            <template #body="{ data }">
              <span v-if="data.group" class="text-sm">{{ data.group.name }}</span>
              <span v-else class="text-gray-500 text-sm">—</span>
            </template>
          </Column>
          <Column header="Tags" style="width: 180px">
            <template #body="{ data }">
              <div class="flex gap-1 flex-wrap">
                <Tag
                  v-for="tag in data.tags"
                  :key="tag.id"
                  :value="tag.name"
                  :style="{ backgroundColor: tag.color }"
                />
              </div>
            </template>
          </Column>
          <Column header="Actions" style="width: 120px">
            <template #body="{ data }">
              <div class="flex gap-1">
                <Button
                  icon="pi pi-refresh"
                  severity="secondary"
                  text
                  rounded
                  v-tooltip="'Check'"
                  @click="checkAccount(data)"
                />
                <Button
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  v-tooltip="'Delete'"
                  @click="deleteAccount(data)"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Import Dialog -->
      <Dialog
        v-model:visible="showImportDialog"
        header="Import Accounts"
        modal
        :style="{ width: '600px' }"
        :closable="!importing"
      >
        <!-- Proxy Selection -->
        <div class="mb-4">
          <label class="block text-sm text-gray-400 mb-2">Use Proxy (optional)</label>
          <Dropdown
            v-model="selectedProxy"
            :options="proxies"
            optionLabel="host"
            optionValue="id"
            placeholder="Select proxy"
            class="w-full"
            showClear
          >
            <template #value="{ value }">
              <span v-if="value">
                {{ proxies.find(p => p.id === value)?.host }}:{{ proxies.find(p => p.id === value)?.port }}
              </span>
              <span v-else class="text-gray-500">No proxy (direct connection)</span>
            </template>
            <template #option="{ option }">
              {{ option.host }}:{{ option.port }} ({{ option.type }})
            </template>
          </Dropdown>
        </div>

        <ProgressBar v-if="importing" mode="indeterminate" style="height: 4px" class="mb-4" />

        <TabView>
          <TabPanel header="tdata">
            <div class="p-4">
              <p class="text-gray-400 mb-4">
                Import from Telegram Desktop (tdata folder as .zip)
              </p>
              <ol class="text-sm text-gray-500 mb-4 list-decimal ml-4 space-y-1">
                <li>Close Telegram Desktop</li>
                <li>Find tdata folder in app data</li>
                <li>Create a .zip archive of tdata folder</li>
                <li>Upload the .zip file below</li>
              </ol>
              <FileUpload
                mode="basic"
                accept=".zip"
                :maxFileSize="100000000"
                chooseLabel="Select tdata.zip"
                :auto="true"
                :disabled="importing"
                @uploader="importTdata"
                customUpload
              />
            </div>
          </TabPanel>

          <TabPanel header="JSON Session">
            <div class="p-4">
              <p class="text-gray-400 mb-4">
                Import Telethon/Pyrogram session files (.json format)
              </p>
              <p class="text-sm text-gray-500 mb-4">
                JSON should contain: <code class="bg-gray-800 px-1 rounded">{"session_string": "..."}</code>
              </p>
              <FileUpload
                mode="basic"
                accept=".json"
                :maxFileSize="10000000"
                chooseLabel="Select session.json"
                :auto="true"
                :disabled="importing"
                @uploader="importJson"
                customUpload
              />
            </div>
          </TabPanel>

          <TabPanel header="Session String">
            <div class="p-4">
              <p class="text-gray-400 mb-4">
                Paste Telethon session string directly
              </p>
              <div class="flex flex-col gap-4">
                <div>
                  <label class="block text-sm text-gray-400 mb-1">Session String</label>
                  <InputText
                    v-model="sessionStringInput"
                    placeholder="1BQANOTEuMTA4L..."
                    class="w-full font-mono text-sm"
                    :disabled="importing"
                  />
                </div>
                <Button
                  label="Import Session"
                  icon="pi pi-check"
                  :loading="importing"
                  @click="importSessionString"
                />
              </div>
            </div>
          </TabPanel>
        </TabView>
      </Dialog>
    </div>
  </MainLayout>
</template>

<style scoped>
:deep(.p-datatable) {
  background: transparent;
}

:deep(.p-datatable-header) {
  background: transparent;
  border: none;
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
