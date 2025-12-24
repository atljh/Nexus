<script setup lang="ts">
import { ref } from 'vue'
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

interface Account {
  id: number
  username: string
  phone: string
  status: string
  proxy: string | null
  group: string | null
}

const accounts = ref<Account[]>([])
const showImportDialog = ref(false)
const loading = ref(false)

const statusOptions = [
  { label: 'All', value: null },
  { label: 'Valid', value: 'valid' },
  { label: 'Banned', value: 'banned' },
  { label: 'Spamblock', value: 'spamblock' }
]

async function loadAccounts() {
  loading.value = true
  try {
    const response = await window.api.get('/api/accounts')
    accounts.value = response.data
  } catch (error) {
    console.error('Failed to load accounts:', error)
  } finally {
    loading.value = false
  }
}

function getStatusClass(status: string) {
  switch (status) {
    case 'valid': return 'status-valid'
    case 'banned': return 'status-banned'
    default: return 'status-warning'
  }
}
</script>

<template>
  <MainLayout>
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
          filterDisplay="row"
          class="p-datatable-dark"
        >
          <template #empty>
            <div class="text-center py-8 text-gray-500">
              <i class="pi pi-users text-4xl mb-3"></i>
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
          <Column field="username" header="Username" sortable />
          <Column field="phone" header="Phone" sortable />
          <Column field="status" header="Status" sortable>
            <template #body="{ data }">
              <span :class="getStatusClass(data.status)">
                {{ data.status }}
              </span>
            </template>
          </Column>
          <Column field="proxy" header="Proxy" />
          <Column field="group" header="Group" />
          <Column header="Actions" style="width: 120px">
            <template #body>
              <div class="flex gap-1">
                <Button icon="pi pi-eye" severity="secondary" text rounded />
                <Button icon="pi pi-trash" severity="danger" text rounded />
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
      >
        <TabView>
          <TabPanel header="tdata">
            <div class="p-4">
              <p class="text-gray-400 mb-4">
                Import accounts from Telegram Desktop (tdata folder)
              </p>
              <FileUpload
                mode="basic"
                accept=".zip"
                :maxFileSize="100000000"
                chooseLabel="Select tdata.zip"
              />
            </div>
          </TabPanel>

          <TabPanel header="JSON Session">
            <div class="p-4">
              <p class="text-gray-400 mb-4">
                Import Telethon/Pyrogram session files
              </p>
              <FileUpload
                mode="basic"
                accept=".json,.session"
                :multiple="true"
                chooseLabel="Select session files"
              />
            </div>
          </TabPanel>

          <TabPanel header="Manual">
            <div class="p-4">
              <p class="text-gray-400 mb-4">
                Add account manually by phone number
              </p>
              <div class="flex flex-col gap-4">
                <div>
                  <label class="block text-sm text-gray-400 mb-1">Phone Number</label>
                  <InputText placeholder="+1234567890" class="w-full" />
                </div>
                <Button label="Send Code" icon="pi pi-send" />
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
</style>
