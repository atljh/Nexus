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
import FileUpload from 'primevue/fileupload'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
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
      summary: t('common.error'),
      detail: t('accounts.messages.loadError'),
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
      summary: t('common.success'),
      detail: response.message || t('accounts.messages.importSuccess'),
      life: 3000
    })

    showImportDialog.value = false
    loadAccounts()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.importFailed'),
      detail: error.message || t('accounts.messages.importFailed'),
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
      summary: t('common.success'),
      detail: t('accounts.messages.importedCount', { count: response.imported }),
      life: 3000
    })

    if (response.errors?.length > 0) {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('accounts.messages.importPartialFail', { count: response.errors.length }),
        life: 5000
      })
    }

    showImportDialog.value = false
    loadAccounts()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.importFailed'),
      detail: error.message || t('accounts.messages.importFailed'),
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
      summary: t('common.warning'),
      detail: t('accounts.messages.enterSessionString'),
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
      summary: t('common.success'),
      detail: t('accounts.messages.importSuccess'),
      life: 3000
    })

    sessionStringInput.value = ''
    showImportDialog.value = false
    loadAccounts()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.importFailed'),
      detail: error.message || t('accounts.messages.importFailed'),
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
        summary: t('accounts.messages.accountValid'),
        detail: t('accounts.messages.accountWorking', { name: response.user_info?.username || account.telegram_id }),
        life: 3000
      })
    } else {
      toast.add({
        severity: 'error',
        summary: t('accounts.messages.accountInvalid'),
        detail: response.error || t('accounts.messages.sessionNotValid'),
        life: 5000
      })
    }

    loadAccounts()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.checkFailed'),
      detail: error.message || t('accounts.messages.checkFailed'),
      life: 3000
    })
  }
}

async function deleteAccount(account: Account) {
  const name = account.username || account.telegram_id
  if (!confirm(t('accounts.deleteConfirm', { name }))) {
    return
  }

  try {
    await window.api.delete(`/api/accounts/${account.id}`)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.messages.deleted'),
      life: 3000
    })
    loadAccounts()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('accounts.messages.deleteFailed'),
      life: 3000
    })
  }
}

async function checkAllAccounts() {
  toast.add({
    severity: 'info',
    summary: t('common.info'),
    detail: t('accounts.messages.checkingAll'),
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
      <div class="page-header">
        <h1 class="page-title">{{ t('accounts.title') }}</h1>
        <div class="header-actions">
          <Button
            :label="t('accounts.import')"
            icon="pi pi-upload"
            severity="secondary"
            @click="showImportDialog = true"
          />
          <Button
            :label="t('accounts.checkAll')"
            icon="pi pi-refresh"
            severity="secondary"
            @click="checkAllAccounts"
            :disabled="accounts.length === 0"
          />
        </div>
      </div>

      <!-- Accounts table -->
      <div class="table-card">
        <DataTable
          :value="accounts"
          :loading="loading"
          paginator
          :rows="20"
          dataKey="id"
          class="custom-table"
        >
          <template #empty>
            <div class="empty-state">
              <div class="empty-icon">
                <i class="pi pi-users"></i>
              </div>
              <p class="empty-text">{{ t('accounts.noAccounts') }}</p>
              <Button
                :label="t('accounts.importAccounts')"
                icon="pi pi-upload"
                @click="showImportDialog = true"
              />
            </div>
          </template>

          <Column field="id" header="ID" sortable style="width: 80px" />
          <Column :header="t('accounts.account')" sortable>
            <template #body="{ data }">
              <div class="account-cell">
                <div class="account-avatar">
                  {{ (data.first_name || data.username || '?')[0].toUpperCase() }}
                </div>
                <div class="account-info">
                  <div class="account-name">{{ getDisplayName(data) }}</div>
                  <div v-if="data.phone" class="account-phone">{{ data.phone }}</div>
                </div>
              </div>
            </template>
          </Column>
          <Column field="status" :header="t('common.status')" sortable style="width: 140px">
            <template #body="{ data }">
              <Tag :value="t(`accounts.status.${data.status}`)" :severity="getStatusSeverity(data.status)" />
            </template>
          </Column>
          <Column :header="t('accounts.proxy')" style="width: 180px">
            <template #body="{ data }">
              <span v-if="data.proxy" class="proxy-text">
                {{ data.proxy.host }}:{{ data.proxy.port }}
              </span>
              <span v-else class="no-data">{{ t('accounts.noProxy') }}</span>
            </template>
          </Column>
          <Column :header="t('accounts.group')" style="width: 150px">
            <template #body="{ data }">
              <span v-if="data.group" class="group-text">{{ data.group.name }}</span>
              <span v-else class="no-data">—</span>
            </template>
          </Column>
          <Column :header="t('accounts.tags')" style="width: 180px">
            <template #body="{ data }">
              <div class="tags-cell">
                <Tag
                  v-for="tag in data.tags"
                  :key="tag.id"
                  :value="tag.name"
                  :style="{ backgroundColor: tag.color }"
                />
              </div>
            </template>
          </Column>
          <Column :header="t('common.actions')" style="width: 120px">
            <template #body="{ data }">
              <div class="actions-cell">
                <Button
                  icon="pi pi-refresh"
                  severity="secondary"
                  text
                  rounded
                  v-tooltip.top="t('common.check')"
                  @click="checkAccount(data)"
                />
                <Button
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  v-tooltip.top="t('common.delete')"
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
        :header="t('accounts.importDialog.title')"
        modal
        :style="{ width: '620px' }"
        :closable="!importing"
        class="custom-dialog"
      >
        <!-- Proxy Selection -->
        <div class="form-field">
          <label class="form-label">{{ t('accounts.importDialog.useProxy') }} ({{ t('common.optional') }})</label>
          <Dropdown
            v-model="selectedProxy"
            :options="proxies"
            optionLabel="host"
            optionValue="id"
            :placeholder="t('accounts.importDialog.selectProxy')"
            class="w-full"
            showClear
          >
            <template #value="{ value }">
              <span v-if="value">
                {{ proxies.find(p => p.id === value)?.host }}:{{ proxies.find(p => p.id === value)?.port }}
              </span>
              <span v-else class="placeholder-text">{{ t('accounts.importDialog.noProxyDirect') }}</span>
            </template>
            <template #option="{ option }">
              {{ option.host }}:{{ option.port }} ({{ option.type }})
            </template>
          </Dropdown>
        </div>

        <ProgressBar v-if="importing" mode="indeterminate" style="height: 4px" class="my-4" />

        <TabView>
          <TabPanel :header="t('accounts.tdata.title')" value="0">
            <div class="tab-content">
              <p class="description">{{ t('accounts.tdata.description') }}</p>
              <ol class="steps-list">
                <li>{{ t('accounts.tdata.step1') }}</li>
                <li>{{ t('accounts.tdata.step2') }}</li>
                <li>{{ t('accounts.tdata.step3') }}</li>
                <li>{{ t('accounts.tdata.step4') }}</li>
              </ol>
              <FileUpload
                mode="basic"
                accept=".zip"
                :maxFileSize="100000000"
                :chooseLabel="t('accounts.tdata.selectFile')"
                :auto="true"
                :disabled="importing"
                @uploader="importTdata"
                customUpload
              />
            </div>
          </TabPanel>

          <TabPanel :header="t('accounts.jsonSession.title')" value="1">
            <div class="tab-content">
              <p class="description">{{ t('accounts.jsonSession.description') }}</p>
              <p class="format-hint">
                {{ t('accounts.jsonSession.format') }} <code>{"session_string": "..."}</code>
              </p>
              <FileUpload
                mode="basic"
                accept=".json"
                :maxFileSize="10000000"
                :chooseLabel="t('accounts.jsonSession.selectFile')"
                :auto="true"
                :disabled="importing"
                @uploader="importJson"
                customUpload
              />
            </div>
          </TabPanel>

          <TabPanel :header="t('accounts.sessionString.title')" value="2">
            <div class="tab-content">
              <p class="description">{{ t('accounts.sessionString.description') }}</p>
              <div class="form-field">
                <label class="form-label">{{ t('accounts.sessionString.label') }}</label>
                <InputText
                  v-model="sessionStringInput"
                  :placeholder="t('accounts.sessionString.placeholder')"
                  class="w-full font-mono"
                  :disabled="importing"
                />
              </div>
              <Button
                :label="t('accounts.sessionString.importButton')"
                icon="pi pi-check"
                :loading="importing"
                @click="importSessionString"
                class="mt-4"
              />
            </div>
          </TabPanel>
        </TabView>
      </Dialog>
    </div>
  </MainLayout>
</template>

<style scoped>
.accounts-page {
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
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(124, 58, 237, 0.1) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.empty-icon i {
  font-size: 32px;
  color: #a855f7;
}

.empty-text {
  color: #6b7280;
  margin-bottom: 20px;
  font-size: 15px;
}

.account-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.account-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 600;
  color: white;
}

.account-info {
  display: flex;
  flex-direction: column;
}

.account-name {
  font-weight: 500;
  color: #e5e7eb;
}

.account-phone {
  font-size: 12px;
  color: #6b7280;
}

.proxy-text {
  font-size: 13px;
  color: #9ca3af;
  font-family: monospace;
}

.group-text {
  font-size: 13px;
  color: #9ca3af;
}

.no-data {
  color: #4b5563;
  font-size: 13px;
}

.tags-cell {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.actions-cell {
  display: flex;
  gap: 4px;
}

.form-field {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  font-size: 13px;
  color: #9ca3af;
  margin-bottom: 8px;
  font-weight: 500;
}

.placeholder-text {
  color: #6b7280;
}

.tab-content {
  padding: 20px 0;
}

.description {
  color: #9ca3af;
  margin-bottom: 16px;
  font-size: 14px;
}

.steps-list {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 20px;
  padding-left: 20px;
}

.steps-list li {
  margin-bottom: 8px;
}

.format-hint {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 16px;
}

.format-hint code {
  background: rgba(0, 0, 0, 0.3);
  padding: 2px 8px;
  border-radius: 4px;
  font-family: monospace;
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
}

:deep(.p-tabview .p-tabview-nav) {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.06);
}

:deep(.p-tabview .p-tabview-nav li .p-tabview-nav-link) {
  background: transparent;
  border-color: transparent;
  color: #6b7280;
}

:deep(.p-tabview .p-tabview-nav li.p-highlight .p-tabview-nav-link) {
  color: #a855f7;
  border-color: #a855f7;
  background: transparent;
}

:deep(.p-tabview .p-tabview-panels) {
  background: transparent;
}
</style>
