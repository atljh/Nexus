<script setup lang="ts">
import { ref } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import Textarea from 'primevue/textarea'

interface Proxy {
  id: number
  host: string
  port: number
  type: string
  username: string | null
  status: 'unchecked' | 'valid' | 'invalid'
  accounts_count: number
}

const proxies = ref<Proxy[]>([])
const showAddDialog = ref(false)
const loading = ref(false)

const proxyTypes = [
  { label: 'SOCKS5', value: 'socks5' },
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

const bulkProxies = ref('')

function getStatusClass(status: string) {
  switch (status) {
    case 'valid': return 'status-valid'
    case 'invalid': return 'status-banned'
    default: return 'status-warning'
  }
}

async function checkProxy(proxy: Proxy) {
  // TODO: implement
}

async function addProxy() {
  // TODO: implement
}
</script>

<template>
  <MainLayout>
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
          />
        </div>
      </div>

      <!-- Proxy table -->
      <div class="card-dashed">
        <DataTable
          :value="proxies"
          :loading="loading"
          paginator
          :rows="20"
          dataKey="id"
        >
          <template #empty>
            <div class="text-center py-8 text-gray-500">
              <i class="pi pi-globe text-4xl mb-3"></i>
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
              {{ data.host }}:{{ data.port }}
            </template>
          </Column>
          <Column field="type" header="Type" sortable style="width: 100px" />
          <Column field="username" header="Auth" style="width: 120px">
            <template #body="{ data }">
              {{ data.username ? 'Yes' : 'No' }}
            </template>
          </Column>
          <Column field="status" header="Status" sortable style="width: 120px">
            <template #body="{ data }">
              <span :class="getStatusClass(data.status)">
                {{ data.status }}
              </span>
            </template>
          </Column>
          <Column field="accounts_count" header="Accounts" style="width: 100px" />
          <Column header="Actions" style="width: 150px">
            <template #body="{ data }">
              <div class="flex gap-1">
                <Button
                  icon="pi pi-refresh"
                  severity="secondary"
                  text
                  rounded
                  @click="checkProxy(data)"
                />
                <Button icon="pi pi-pencil" severity="secondary" text rounded />
                <Button icon="pi pi-trash" severity="danger" text rounded />
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
            <label class="block text-sm text-gray-400 mb-1">Bulk Import (one per line)</label>
            <Textarea
              v-model="bulkProxies"
              placeholder="host:port:user:pass&#10;host:port"
              rows="4"
              class="w-full"
            />
          </div>

          <div class="flex justify-end gap-2 mt-4">
            <Button label="Cancel" severity="secondary" @click="showAddDialog = false" />
            <Button label="Add" icon="pi pi-plus" @click="addProxy" />
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
</style>
