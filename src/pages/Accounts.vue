<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAccountStore, useProxyStore, useGroupStore, useTagStore } from '@/stores'
import type { Account, AccountStatus, BulkAction } from '@/types'

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
// Checkbox imported but will be used in future enhancements
import Menu from 'primevue/menu'
import InputGroup from 'primevue/inputgroup'
import InputGroupAddon from 'primevue/inputgroupaddon'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'

const { t } = useI18n()
const toast = useToast()
const confirm = useConfirm()

// Stores
const accountStore = useAccountStore()
const proxyStore = useProxyStore()
const groupStore = useGroupStore()
const tagStore = useTagStore()

// Local state
const showImportDialog = ref(false)
const showGroupDialog = ref(false)
const showTagDialog = ref(false)
const importing = ref(false)
const selectedProxy = ref<number | null>(null)
const sessionStringInput = ref('')
const searchQuery = ref('')
const bulkMenu = ref()
const newGroupName = ref('')
const newGroupColor = ref('#a855f7')
const newTagName = ref('')
const newTagColor = ref('#a855f7')

// Computed
const selectedIds = computed({
  get: () => accountStore.selectedIds,
  set: (val) => {
    accountStore.selectedIds = val
  }
})

const hasSelection = computed(() => selectedIds.value.length > 0)

const statusOptions = computed(() => [
  { label: t('accounts.allStatuses'), value: null },
  { label: t('accounts.status.valid'), value: 'valid' },
  { label: t('accounts.status.invalid'), value: 'invalid' },
  { label: t('accounts.status.banned'), value: 'banned' },
  { label: t('accounts.status.spamblock'), value: 'spamblock' },
  { label: t('accounts.status.unchecked'), value: 'unchecked' }
])

const bulkMenuItems = computed(() => [
  {
    label: t('accounts.bulk.check'),
    icon: 'pi pi-refresh',
    command: () => handleBulkAction('check')
  },
  {
    label: t('accounts.bulk.setProxy'),
    icon: 'pi pi-globe',
    items: [
      { label: t('accounts.bulk.noProxy'), command: () => handleBulkAction('set_proxy', 0) },
      ...proxyStore.proxies.map(p => ({
        label: `${p.host}:${p.port}`,
        command: () => handleBulkAction('set_proxy', p.id)
      }))
    ]
  },
  {
    label: t('accounts.bulk.setGroup'),
    icon: 'pi pi-folder',
    items: [
      { label: t('accounts.bulk.noGroup'), command: () => handleBulkAction('set_group', 0) },
      ...groupStore.groups.map(g => ({
        label: g.name,
        command: () => handleBulkAction('set_group', g.id)
      }))
    ]
  },
  { separator: true },
  {
    label: t('accounts.bulk.delete'),
    icon: 'pi pi-trash',
    class: 'text-red-500',
    command: () => confirmBulkDelete()
  }
])

// Watch search query
watch(searchQuery, (val) => {
  accountStore.setFilter('search', val || undefined)
})

// Lifecycle
onMounted(async () => {
  await Promise.all([
    accountStore.fetchAccounts(),
    proxyStore.fetchProxies(),
    groupStore.fetchGroups(),
    tagStore.fetchTags()
  ])
})

// Methods
async function importTdata(event: any) {
  const file = event.files[0]
  if (!file) return

  importing.value = true
  try {
    const result = await accountStore.importTdata(file, selectedProxy.value || undefined)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: result.message ?? t('accounts.messages.importSuccess'),
      life: 3000
    })
    showImportDialog.value = false
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.importFailed'),
      detail: error.message,
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
    const result = await accountStore.importJson(file, selectedProxy.value || undefined)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.messages.importedCount', { count: result.imported }),
      life: 3000
    })
    if (result.errors && result.errors.length > 0) {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('accounts.messages.importPartialFail', { count: result.errors.length }),
        life: 5000
      })
    }
    showImportDialog.value = false
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.importFailed'),
      detail: error.message,
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
    await accountStore.importSessionString(
      sessionStringInput.value.trim(),
      selectedProxy.value || undefined
    )
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.messages.importSuccess'),
      life: 3000
    })
    sessionStringInput.value = ''
    showImportDialog.value = false
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.importFailed'),
      detail: error.message,
      life: 5000
    })
  } finally {
    importing.value = false
  }
}

async function checkAccount(account: Account) {
  try {
    const result = await accountStore.checkAccount(account.id)
    toast.add({
      severity: result.valid ? 'success' : 'error',
      summary: result.valid ? t('accounts.messages.accountValid') : t('accounts.messages.accountInvalid'),
      detail: result.valid
        ? t('accounts.messages.accountWorking', { name: result.user_info?.username || account.telegram_id })
        : result.error,
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('accounts.messages.checkFailed'),
      detail: error.message,
      life: 3000
    })
  }
}

function confirmDelete(account: Account) {
  const name = account.username || account.telegram_id
  confirm.require({
    message: t('accounts.deleteConfirm', { name }),
    header: t('common.confirmation'),
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await accountStore.deleteAccount(account.id)
        toast.add({
          severity: 'success',
          summary: t('common.success'),
          detail: t('accounts.messages.deleted'),
          life: 3000
        })
      } catch (error: any) {
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.message,
          life: 3000
        })
      }
    }
  })
}

async function handleBulkAction(action: BulkAction, value?: number) {
  try {
    await accountStore.bulkAction(action, value)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.messages.bulkSuccess', { count: selectedIds.value.length }),
      life: 3000
    })
    if (action !== 'check') {
      accountStore.clearSelection()
    }
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 3000
    })
  }
}

function confirmBulkDelete() {
  confirm.require({
    message: t('accounts.bulkDeleteConfirm', { count: selectedIds.value.length }),
    header: t('common.confirmation'),
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => handleBulkAction('delete')
  })
}

function toggleBulkMenu(event: Event) {
  bulkMenu.value.toggle(event)
}

async function checkAllAccounts() {
  toast.add({
    severity: 'info',
    summary: t('common.info'),
    detail: t('accounts.messages.checkingAll'),
    life: 3000
  })

  for (const account of accountStore.accounts) {
    if (account.status !== 'valid') {
      await checkAccount(account)
    }
  }
}

function selectGroup(groupId: number | null) {
  groupStore.selectGroup(groupId)
  accountStore.setFilter('group_id', groupId || undefined)
}

function setStatusFilter(status: AccountStatus | null) {
  accountStore.setFilter('status', status || undefined)
}

async function createGroup() {
  if (!newGroupName.value.trim()) return

  try {
    await groupStore.createGroup({
      name: newGroupName.value.trim(),
      color: newGroupColor.value
    })
    newGroupName.value = ''
    showGroupDialog.value = false
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('groups.created'),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 3000
    })
  }
}

async function deleteGroup(id: number) {
  try {
    await groupStore.deleteGroup(id)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('groups.deleted'),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 3000
    })
  }
}

async function createTag() {
  if (!newTagName.value.trim()) return

  try {
    await tagStore.createTag({
      name: newTagName.value.trim(),
      color: newTagColor.value
    })
    newTagName.value = ''
    showTagDialog.value = false
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('tags.created'),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 3000
    })
  }
}

async function deleteTag(id: number) {
  try {
    await tagStore.deleteTag(id)
    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('tags.deleted'),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message,
      life: 3000
    })
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

function onRowSelect(event: any) {
  accountStore.toggleSelection(event.data.id)
}

function onRowUnselect(event: any) {
  accountStore.toggleSelection(event.data.id)
}
</script>

<template>
  <MainLayout>
    <Toast />
    <ConfirmDialog />

    <div class="accounts-page">
      <div class="accounts-layout">
        <!-- Sidebar with Groups -->
        <div class="groups-sidebar">
          <div class="sidebar-header">
            <h3 class="sidebar-title">{{ t('groups.title') }}</h3>
            <Button
              icon="pi pi-plus"
              severity="secondary"
              text
              rounded
              size="small"
              @click="showGroupDialog = true"
            />
          </div>

          <div class="groups-list">
            <div
              class="group-item"
              :class="{ active: groupStore.selectedGroupId === null }"
              @click="selectGroup(null)"
            >
              <div class="group-icon" style="background: #6366f1">
                <i class="pi pi-users"></i>
              </div>
              <div class="group-info">
                <span class="group-name">{{ t('groups.allAccounts') }}</span>
                <span class="group-count">{{ accountStore.accounts.length }}</span>
              </div>
            </div>

            <div
              v-for="group in groupStore.groups"
              :key="group.id"
              class="group-item"
              :class="{ active: groupStore.selectedGroupId === group.id }"
              @click="selectGroup(group.id)"
            >
              <div class="group-icon" :style="{ background: group.color || '#a855f7' }">
                <i class="pi pi-folder"></i>
              </div>
              <div class="group-info">
                <span class="group-name">{{ group.name }}</span>
                <span class="group-count">{{ group.accounts_count }}</span>
              </div>
              <Button
                icon="pi pi-trash"
                severity="danger"
                text
                rounded
                size="small"
                class="delete-btn"
                @click.stop="deleteGroup(group.id)"
              />
            </div>
          </div>

          <!-- Tags Section -->
          <div class="sidebar-section">
            <div class="sidebar-header">
              <h3 class="sidebar-title">{{ t('tags.title') }}</h3>
              <Button
                icon="pi pi-plus"
                severity="secondary"
                text
                rounded
                size="small"
                @click="showTagDialog = true"
              />
            </div>

            <div class="tags-list">
              <div
                v-for="tag in tagStore.tags"
                :key="tag.id"
                class="tag-item"
                :class="{ active: accountStore.filters.tag_id === tag.id }"
                @click="accountStore.setFilter('tag_id', accountStore.filters.tag_id === tag.id ? undefined : tag.id)"
              >
                <span class="tag-dot" :style="{ background: tag.color }"></span>
                <span class="tag-name">{{ tag.name }}</span>
                <Button
                  icon="pi pi-times"
                  severity="danger"
                  text
                  rounded
                  size="small"
                  class="delete-btn"
                  @click.stop="deleteTag(tag.id)"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
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
                :disabled="accountStore.accounts.length === 0"
              />
            </div>
          </div>

          <!-- Filters Bar -->
          <div class="filters-bar">
            <InputGroup>
              <InputGroupAddon>
                <i class="pi pi-search"></i>
              </InputGroupAddon>
              <InputText
                v-model="searchQuery"
                :placeholder="t('accounts.searchPlaceholder')"
                class="search-input"
              />
            </InputGroup>

            <Dropdown
              :model-value="accountStore.filters.status"
              :options="statusOptions"
              optionLabel="label"
              optionValue="value"
              :placeholder="t('accounts.filterByStatus')"
              @update:model-value="setStatusFilter"
              class="status-filter"
              showClear
            />

            <div v-if="hasSelection" class="bulk-actions">
              <span class="selection-count">
                {{ t('accounts.selected', { count: selectedIds.length }) }}
              </span>
              <Button
                :label="t('accounts.bulk.actions')"
                icon="pi pi-chevron-down"
                iconPos="right"
                severity="secondary"
                @click="toggleBulkMenu"
              />
              <Menu ref="bulkMenu" :model="bulkMenuItems" :popup="true" />
              <Button
                icon="pi pi-times"
                severity="secondary"
                text
                rounded
                @click="accountStore.clearSelection"
              />
            </div>
          </div>

          <!-- Accounts Table -->
          <div class="table-card">
            <DataTable
              v-model:selection="selectedIds"
              :value="accountStore.filteredAccounts"
              :loading="accountStore.loading"
              paginator
              :rows="20"
              dataKey="id"
              class="custom-table"
              selectionMode="multiple"
              @row-select="onRowSelect"
              @row-unselect="onRowUnselect"
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

              <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>

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
                      @click="confirmDelete(data)"
                    />
                  </div>
                </template>
              </Column>
            </DataTable>
          </div>
        </div>
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
        <div class="form-field">
          <label class="form-label">{{ t('accounts.importDialog.useProxy') }} ({{ t('common.optional') }})</label>
          <Dropdown
            v-model="selectedProxy"
            :options="proxyStore.proxies"
            optionLabel="host"
            optionValue="id"
            :placeholder="t('accounts.importDialog.selectProxy')"
            class="w-full"
            showClear
          >
            <template #value="{ value }">
              <span v-if="value">
                {{ proxyStore.getById(value)?.host }}:{{ proxyStore.getById(value)?.port }}
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

      <!-- Create Group Dialog -->
      <Dialog
        v-model:visible="showGroupDialog"
        :header="t('groups.create')"
        modal
        :style="{ width: '400px' }"
        class="custom-dialog"
      >
        <div class="form-field">
          <label class="form-label">{{ t('groups.name') }}</label>
          <InputText
            v-model="newGroupName"
            :placeholder="t('groups.namePlaceholder')"
            class="w-full"
          />
        </div>
        <div class="form-field">
          <label class="form-label">{{ t('common.color') }}</label>
          <div class="color-picker">
            <div
              v-for="color in tagStore.presetColors"
              :key="color"
              class="color-option"
              :class="{ active: newGroupColor === color }"
              :style="{ background: color }"
              @click="newGroupColor = color"
            ></div>
          </div>
        </div>

        <template #footer>
          <Button :label="t('common.cancel')" severity="secondary" @click="showGroupDialog = false" />
          <Button :label="t('common.create')" icon="pi pi-check" @click="createGroup" />
        </template>
      </Dialog>

      <!-- Create Tag Dialog -->
      <Dialog
        v-model:visible="showTagDialog"
        :header="t('tags.create')"
        modal
        :style="{ width: '400px' }"
        class="custom-dialog"
      >
        <div class="form-field">
          <label class="form-label">{{ t('tags.name') }}</label>
          <InputText
            v-model="newTagName"
            :placeholder="t('tags.namePlaceholder')"
            class="w-full"
          />
        </div>
        <div class="form-field">
          <label class="form-label">{{ t('common.color') }}</label>
          <div class="color-picker">
            <div
              v-for="color in tagStore.presetColors"
              :key="color"
              class="color-option"
              :class="{ active: newTagColor === color }"
              :style="{ background: color }"
              @click="newTagColor = color"
            ></div>
          </div>
        </div>

        <template #footer>
          <Button :label="t('common.cancel')" severity="secondary" @click="showTagDialog = false" />
          <Button :label="t('common.create')" icon="pi pi-check" @click="createTag" />
        </template>
      </Dialog>
    </div>
  </MainLayout>
</template>

<style scoped>
.accounts-page {
  height: 100%;
}

.accounts-layout {
  display: flex;
  gap: 24px;
  height: 100%;
}

/* Sidebar */
.groups-sidebar {
  width: 280px;
  flex-shrink: 0;
  background: linear-gradient(145deg, #161616 0%, #111111 100%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 16px;
  overflow-y: auto;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sidebar-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.groups-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.group-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.group-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.group-item.active {
  background: rgba(168, 85, 247, 0.15);
}

.group-item .delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
}

.group-item:hover .delete-btn {
  opacity: 1;
}

.group-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
}

.group-info {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.group-name {
  font-size: 14px;
  font-weight: 500;
  color: #e5e7eb;
}

.group-count {
  font-size: 12px;
  color: #6b7280;
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 8px;
  border-radius: 10px;
}

/* Tags */
.tags-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tag-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.tag-item.active {
  background: rgba(168, 85, 247, 0.15);
}

.tag-item .delete-btn {
  opacity: 0;
  margin-left: auto;
}

.tag-item:hover .delete-btn {
  opacity: 1;
}

.tag-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.tag-name {
  font-size: 13px;
  color: #d1d5db;
}

/* Main Content */
.main-content {
  flex: 1;
  min-width: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
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

/* Filters Bar */
.filters-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input {
  width: 280px;
}

.status-filter {
  width: 180px;
}

.bulk-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
  padding-left: 16px;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
}

.selection-count {
  font-size: 13px;
  color: #a855f7;
  font-weight: 500;
}

/* Table */
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

/* Dialogs */
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

/* Color Picker */
.color-picker {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.color-option {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s;
}

.color-option:hover {
  transform: scale(1.1);
}

.color-option.active {
  box-shadow: 0 0 0 2px #161616, 0 0 0 4px white;
}

/* Table styles */
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

:deep(.custom-table .p-datatable-tbody > tr.p-highlight) {
  background: rgba(168, 85, 247, 0.1);
}

:deep(.custom-dialog .p-dialog-header) {
  background: #161616;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.custom-dialog .p-dialog-content) {
  background: #161616;
}

:deep(.custom-dialog .p-dialog-footer) {
  background: #161616;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
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

:deep(.p-checkbox .p-checkbox-box) {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.2);
}

:deep(.p-checkbox .p-checkbox-box.p-highlight) {
  background: #a855f7;
  border-color: #a855f7;
}
</style>
