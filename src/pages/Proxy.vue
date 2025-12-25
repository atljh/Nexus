<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()

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

interface ProxiesResponse { data: Proxy[] }

async function loadProxies() {
  loading.value = true
  try {
    const response = await window.api.get('/api/proxy') as ProxiesResponse
    proxies.value = response.data || []
  } catch (error) {
    console.error('Failed to load proxies:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('proxy.messages.loadError'),
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

interface CheckResult { status: string; valid?: boolean }
interface CheckAllResult { checked: number }

async function checkProxy(proxy: Proxy) {
  try {
    const response = await window.api.post(`/api/proxy/${proxy.id}/check`, {}) as CheckResult

    toast.add({
      severity: response.status === 'valid' ? 'success' : 'error',
      summary: response.status === 'valid' ? t('proxy.messages.proxyValid') : t('proxy.messages.proxyInvalid'),
      detail: `${proxy.host}:${proxy.port}`,
      life: 3000
    })

    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('proxy.messages.checkFailed'),
      detail: error.message || t('proxy.messages.checkFailed'),
      life: 3000
    })
  }
}

async function checkAllProxies() {
  checking.value = true
  toast.add({
    severity: 'info',
    summary: t('common.info'),
    detail: t('proxy.messages.checking'),
    life: 2000
  })

  try {
    const response = await window.api.post('/api/proxy/check-all', {}) as CheckAllResult

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('proxy.messages.checkComplete', { count: response.checked }),
      life: 3000
    })

    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.checkFailed'),
      life: 3000
    })
  } finally {
    checking.value = false
  }
}

interface BulkCreateResult { created: number }

async function addProxy() {
  // Handle bulk import
  if (bulkProxies.value.trim()) {
    const lines = bulkProxies.value.trim().split('\n').filter(l => l.trim())

    try {
      const response = await window.api.post('/api/proxy/bulk', {
        proxies: lines,
        type: newProxy.value.type
      }) as BulkCreateResult

      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('proxy.messages.addedCount', { count: response.created }),
        life: 3000
      })

      resetForm()
      showAddDialog.value = false
      loadProxies()
    } catch (error: any) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.message || t('proxy.messages.addFailed'),
        life: 3000
      })
    }
    return
  }

  // Handle single proxy
  if (!newProxy.value.host || !newProxy.value.port) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('proxy.messages.enterHostPort'),
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
      summary: t('common.success'),
      detail: t('proxy.messages.added'),
      life: 3000
    })

    resetForm()
    showAddDialog.value = false
    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.addFailed'),
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
      summary: t('common.success'),
      detail: t('proxy.messages.updated'),
      life: 3000
    })

    showEditDialog.value = false
    editProxy.value = null
    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.updateFailed'),
      life: 3000
    })
  }
}

async function deleteProxy(proxy: Proxy) {
  if (!confirm(t('proxy.deleteConfirm', { host: proxy.host, port: proxy.port }))) {
    return
  }

  try {
    await window.api.delete(`/api/proxy/${proxy.id}`)

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('proxy.messages.deleted'),
      life: 3000
    })

    loadProxies()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.messages.deleteFailed'),
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
  if (!dateStr) return t('common.never')
  return new Date(dateStr).toLocaleString()
}
</script>

<template>
  <MainLayout>
    <Toast />
    <div class="proxy-page">
      <div class="page-header">
        <h1 class="page-title">{{ t('proxy.title') }}</h1>
        <div class="header-actions">
          <Button
            :label="t('proxy.addProxy')"
            icon="pi pi-plus"
            @click="showAddDialog = true"
          />
          <Button
            :label="t('proxy.checkAll')"
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
      <div class="table-card">
        <DataTable
          v-model:selection="selectedProxies"
          :value="proxies"
          :loading="loading"
          paginator
          :rows="20"
          dataKey="id"
          class="custom-table"
        >
          <template #empty>
            <div class="empty-state">
              <div class="empty-icon">
                <i class="pi pi-globe"></i>
              </div>
              <p class="empty-text">{{ t('proxy.noProxies') }}</p>
              <Button
                :label="t('proxy.addProxy')"
                icon="pi pi-plus"
                @click="showAddDialog = true"
              />
            </div>
          </template>

          <Column field="id" header="ID" sortable style="width: 80px" />
          <Column :header="t('proxy.title')" sortable>
            <template #body="{ data }">
              <div class="proxy-cell">
                <span class="proxy-address">{{ data.host }}:{{ data.port }}</span>
                <Tag :value="data.type.toUpperCase()" severity="secondary" class="proxy-type" />
              </div>
            </template>
          </Column>
          <Column :header="t('proxy.auth')" style="width: 100px">
            <template #body="{ data }">
              <Tag
                :value="data.username ? t('common.yes') : t('common.no')"
                :severity="data.username ? 'success' : 'secondary'"
              />
            </template>
          </Column>
          <Column field="status" :header="t('common.status')" sortable style="width: 120px">
            <template #body="{ data }">
              <Tag :value="data.status" :severity="getStatusSeverity(data.status)" />
            </template>
          </Column>
          <Column :header="t('proxy.accounts')" style="width: 100px">
            <template #body="{ data }">
              <span class="accounts-count">{{ data.accounts_count }}</span>
            </template>
          </Column>
          <Column :header="t('proxy.lastCheck')" style="width: 180px">
            <template #body="{ data }">
              <span class="last-check">{{ formatDate(data.last_checked_at) }}</span>
            </template>
          </Column>
          <Column :header="t('common.actions')" style="width: 150px">
            <template #body="{ data }">
              <div class="actions-cell">
                <Button
                  icon="pi pi-refresh"
                  severity="secondary"
                  text
                  rounded
                  v-tooltip.top="t('common.check')"
                  @click="checkProxy(data)"
                />
                <Button
                  icon="pi pi-pencil"
                  severity="secondary"
                  text
                  rounded
                  v-tooltip.top="t('common.edit')"
                  @click="openEditDialog(data)"
                />
                <Button
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  v-tooltip.top="t('common.delete')"
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
        :header="t('proxy.addDialog.title')"
        modal
        :style="{ width: '520px' }"
        class="custom-dialog"
      >
        <div class="dialog-content">
          <div class="form-field">
            <label class="form-label">{{ t('proxy.addDialog.type') }}</label>
            <Dropdown
              v-model="newProxy.type"
              :options="proxyTypes"
              optionLabel="label"
              optionValue="value"
              class="w-full"
            />
          </div>

          <div class="form-row">
            <div class="form-field flex-2">
              <label class="form-label">{{ t('proxy.addDialog.host') }}</label>
              <InputText v-model="newProxy.host" placeholder="127.0.0.1" class="w-full" />
            </div>
            <div class="form-field flex-1">
              <label class="form-label">{{ t('proxy.addDialog.port') }}</label>
              <InputText v-model="newProxy.port" placeholder="1080" class="w-full" />
            </div>
          </div>

          <div class="form-row">
            <div class="form-field flex-1">
              <label class="form-label">{{ t('proxy.addDialog.username') }} ({{ t('common.optional') }})</label>
              <InputText v-model="newProxy.username" class="w-full" />
            </div>
            <div class="form-field flex-1">
              <label class="form-label">{{ t('proxy.addDialog.password') }} ({{ t('common.optional') }})</label>
              <InputText v-model="newProxy.password" type="password" class="w-full" />
            </div>
          </div>

          <div class="divider"></div>

          <div class="form-field">
            <label class="form-label">{{ t('proxy.addDialog.bulkImport') }}</label>
            <p class="hint-text">{{ t('proxy.addDialog.bulkFormat') }}</p>
            <Textarea
              v-model="bulkProxies"
              placeholder="192.168.1.1:1080&#10;192.168.1.2:1080:user:pass"
              rows="4"
              class="w-full font-mono"
            />
          </div>

          <div class="dialog-actions">
            <Button :label="t('common.cancel')" severity="secondary" @click="showAddDialog = false; resetForm()" />
            <Button :label="t('common.add')" icon="pi pi-plus" @click="addProxy" />
          </div>
        </div>
      </Dialog>

      <!-- Edit Proxy Dialog -->
      <Dialog
        v-model:visible="showEditDialog"
        :header="t('proxy.editDialog.title')"
        modal
        :style="{ width: '520px' }"
        class="custom-dialog"
      >
        <div v-if="editProxy" class="dialog-content">
          <div class="form-field">
            <label class="form-label">{{ t('proxy.addDialog.type') }}</label>
            <Dropdown
              v-model="editProxy.type"
              :options="proxyTypes"
              optionLabel="label"
              optionValue="value"
              class="w-full"
            />
          </div>

          <div class="form-row">
            <div class="form-field flex-2">
              <label class="form-label">{{ t('proxy.addDialog.host') }}</label>
              <InputText v-model="editProxy.host" class="w-full" />
            </div>
            <div class="form-field flex-1">
              <label class="form-label">{{ t('proxy.addDialog.port') }}</label>
              <InputText :modelValue="String(editProxy.port)" @update:modelValue="editProxy.port = Number($event)" class="w-full" />
            </div>
          </div>

          <div class="form-row">
            <div class="form-field flex-1">
              <label class="form-label">{{ t('proxy.addDialog.username') }}</label>
              <InputText v-model="editProxy.username" class="w-full" />
            </div>
            <div class="form-field flex-1">
              <label class="form-label">{{ t('proxy.addDialog.password') }}</label>
              <InputText v-model="editProxy.password" type="password" class="w-full" />
            </div>
          </div>

          <div class="dialog-actions">
            <Button :label="t('common.cancel')" severity="secondary" @click="showEditDialog = false" />
            <Button :label="t('common.save')" icon="pi pi-check" @click="saveEditProxy" />
          </div>
        </div>
      </Dialog>
    </div>
  </MainLayout>
</template>

<style scoped>
.proxy-page {
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #f3f4f6;
  letter-spacing: -0.5px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.table-card {
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 16px;
  overflow: hidden;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 24px;
}

.empty-icon {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.1) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.empty-icon i {
  font-size: 32px;
  color: #3b82f6;
}

.empty-text {
  color: #6b7280;
  margin-bottom: 20px;
  font-size: 15px;
}

.proxy-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.proxy-address {
  font-family: monospace;
  color: #e5e7eb;
}

.proxy-type {
  font-size: 10px;
}

.accounts-count {
  color: #9ca3af;
}

.last-check {
  font-size: 13px;
  color: #6b7280;
}

.actions-cell {
  display: flex;
  gap: 4px;
}

.dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 13px;
  color: #9ca3af;
  font-weight: 500;
}

.form-row {
  display: flex;
  gap: 12px;
}

.flex-1 {
  flex: 1;
}

.flex-2 {
  flex: 2;
}

.divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 8px 0;
}

.hint-text {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

:deep(.custom-table .p-datatable) {
  background: transparent;
}

:deep(.custom-table .p-datatable-thead > tr > th) {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.06);
  color: #6b7280;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

:deep(.custom-table .p-datatable-tbody > tr) {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.04);
  transition: all 0.2s;
}

:deep(.custom-table .p-datatable-tbody > tr:hover) {
  background: rgba(255, 255, 255, 0.03);
}

:deep(.custom-table .p-datatable-tbody > tr > td) {
  border-color: rgba(255, 255, 255, 0.04);
  padding: 16px;
}

:deep(.custom-dialog .p-dialog-header) {
  background: #161616;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.custom-dialog .p-dialog-content) {
  background: #161616;
  padding: 24px;
}
</style>
