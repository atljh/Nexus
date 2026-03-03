<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAccountStore } from '@/stores/useAccountStore'
import { useGroupStore } from '@/stores/useGroupStore'
import type { Account } from '@/types'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  modelValue: number[]
  accentColor?: string
}>(), {
  accentColor: '#a855f7'
})

const emit = defineEmits<{
  'update:modelValue': [ids: number[]]
}>()

const accountStore = useAccountStore()
const groupStore = useGroupStore()

// UI state
const expanded = ref(true)
const searchQuery = ref('')
const filterGroup = ref<number | null>(null)
const filterStatus = ref<string>('valid')

// Virtual scroll
const ROW_HEIGHT = 42
const BUFFER_ROWS = 6
const availableListRef = ref<HTMLElement | null>(null)
const selectedListRef = ref<HTMLElement | null>(null)
const availableScrollTop = ref(0)
const selectedScrollTop = ref(0)

// Filtered available accounts
const filteredAccounts = computed(() => {
  let accounts = accountStore.accounts.filter(a => a.status === 'valid')

  if (filterGroup.value !== null) {
    accounts = accounts.filter(a => a.group_id === filterGroup.value)
  }

  if (filterStatus.value === 'with_proxy') {
    accounts = accounts.filter(a => a.proxy && a.proxy.status === 'working')
  }

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    accounts = accounts.filter(a =>
      (a.username && a.username.toLowerCase().includes(q)) ||
      (a.phone && a.phone.includes(q)) ||
      (a.first_name && a.first_name.toLowerCase().includes(q)) ||
      String(a.id).includes(q)
    )
  }

  return accounts
})

// Not-yet-selected from filtered
const availableAccounts = computed(() =>
  filteredAccounts.value.filter(a => !props.modelValue.includes(a.id))
)

// Selected accounts
const selectedAccounts = computed(() =>
  accountStore.accounts.filter(a => props.modelValue.includes(a.id))
)

// Virtual scroll computed slices
function getVisibleSlice(list: Account[], scrollTop: number, containerHeight: number) {
  const total = list.length
  if (total <= 60) {
    return { items: list, topPad: 0, bottomPad: 0 }
  }

  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - BUFFER_ROWS)
  const visibleCount = Math.ceil(containerHeight / ROW_HEIGHT) + BUFFER_ROWS * 2
  const endIndex = Math.min(total, startIndex + visibleCount)

  return {
    items: list.slice(startIndex, endIndex),
    topPad: startIndex * ROW_HEIGHT,
    bottomPad: Math.max(0, (total - endIndex) * ROW_HEIGHT)
  }
}

const visibleAvailable = computed(() =>
  getVisibleSlice(availableAccounts.value, availableScrollTop.value, 280)
)

const visibleSelected = computed(() =>
  getVisibleSlice(selectedAccounts.value, selectedScrollTop.value, 280)
)

function onAvailableScroll(e: Event) {
  availableScrollTop.value = (e.target as HTMLElement).scrollTop
}

function onSelectedScroll(e: Event) {
  selectedScrollTop.value = (e.target as HTMLElement).scrollTop
}

// Reset scroll when filters change
watch([searchQuery, filterGroup], () => {
  availableScrollTop.value = 0
  if (availableListRef.value) availableListRef.value.scrollTop = 0
})

// Actions
function addAccount(account: Account) {
  emit('update:modelValue', [...props.modelValue, account.id])
}

function removeAccount(id: number) {
  emit('update:modelValue', props.modelValue.filter(i => i !== id))
}

function addAll() {
  const newIds = availableAccounts.value.map(a => a.id)
  const merged = [...new Set([...props.modelValue, ...newIds])]
  emit('update:modelValue', merged)
}

function removeAll() {
  emit('update:modelValue', [])
}

// Display helpers
function displayName(a: Account): string {
  if (a.first_name) return a.first_name + (a.last_name ? ' ' + a.last_name : '')
  if (a.username) return '@' + a.username
  return a.phone || `ID: ${a.id}`
}

function displaySub(a: Account): string {
  const parts: string[] = []
  if (a.phone) parts.push(a.phone)
  if (a.username) parts.push('@' + a.username)
  if (a.group) parts.push(a.group.name)
  return parts.join(' · ')
}

function proxyLabel(a: Account): string | null {
  if (!a.proxy) return null
  return a.proxy.status === 'working'
    ? t('proxy.status.working')
    : t(`proxy.status.${a.proxy.status}`, a.proxy.status)
}

// Ensure data is loaded
onMounted(async () => {
  if (accountStore.accounts.length === 0) await accountStore.fetchAccounts()
  if (groupStore.groups.length === 0) await groupStore.fetchGroups()
})
</script>

<template>
  <div class="account-picker" :style="{ '--accent': accentColor }">
    <!-- Collapsible Header -->
    <div class="picker-header" @click="expanded = !expanded">
      <div class="picker-header-left">
        <div class="picker-icon">
          <i class="pi pi-users"></i>
        </div>
        <span class="picker-title">{{ t('accountPicker.title') }}</span>
        <span class="picker-count" :class="{ active: modelValue.length > 0 }">
          {{ t('accountPicker.selected', { count: modelValue.length }) }}
        </span>
      </div>
      <button class="picker-toggle" :class="{ collapsed: !expanded }">
        <i class="pi pi-chevron-up"></i>
      </button>
    </div>

    <!-- Content -->
    <Transition name="picker-slide">
      <div v-if="expanded" class="picker-body">
        <!-- Left Panel: Available -->
        <div class="picker-panel available-panel">
          <div class="panel-header">
            <span class="panel-title">{{ t('accountPicker.available') }}</span>
            <span class="panel-badge">{{ availableAccounts.length }}</span>
            <span v-if="filteredAccounts.length !== availableAccounts.length + modelValue.length" class="panel-filter-hint">
              / {{ filteredAccounts.length }}
            </span>
          </div>

          <!-- Search & Filters -->
          <div class="panel-filters">
            <div class="search-row">
              <div class="search-input-wrap">
                <i class="pi pi-search"></i>
                <input
                  v-model="searchQuery"
                  type="text"
                  :placeholder="t('accountPicker.searchPlaceholder')"
                  class="search-input"
                />
              </div>
            </div>
            <div class="filter-row">
              <select v-model="filterGroup" class="filter-select">
                <option :value="null">{{ t('accountPicker.allGroups') }}</option>
                <option
                  v-for="group in groupStore.groups"
                  :key="group.id"
                  :value="group.id"
                >
                  {{ group.name }}
                </option>
              </select>
            </div>
          </div>

          <!-- Batch action -->
          <div class="panel-action-bar">
            <button class="batch-btn add-all-btn" @click="addAll" :disabled="availableAccounts.length === 0">
              <i class="pi pi-angle-double-right"></i>
              <span>{{ t('accountPicker.addAll') }}</span>
              <span v-if="availableAccounts.length > 0" class="batch-count">({{ availableAccounts.length }})</span>
            </button>
          </div>

          <!-- Account List (virtual scroll) -->
          <div
            ref="availableListRef"
            class="account-list"
            @scroll="onAvailableScroll"
          >
            <div v-if="availableAccounts.length > 0" :style="{ paddingTop: visibleAvailable.topPad + 'px', paddingBottom: visibleAvailable.bottomPad + 'px' }">
              <div
                v-for="account in visibleAvailable.items"
                :key="account.id"
                class="account-row"
                @click="addAccount(account)"
              >
                <div class="account-info">
                  <span class="account-name">{{ displayName(account) }}</span>
                  <span class="account-sub">{{ displaySub(account) }}</span>
                </div>
                <div class="account-tags">
                  <span class="tag tag-valid">{{ t('accounts.status.valid') }}</span>
                  <span v-if="proxyLabel(account)" class="tag tag-proxy">{{ proxyLabel(account) }}</span>
                  <span v-if="account.geo" class="tag tag-geo">{{ account.geo }}</span>
                </div>
                <div class="account-arrow">
                  <i class="pi pi-chevron-right"></i>
                </div>
              </div>
            </div>

            <div v-if="availableAccounts.length === 0 && filteredAccounts.length > 0" class="list-empty">
              <i class="pi pi-check-circle"></i>
              <span>{{ t('accountPicker.allAdded') }}</span>
            </div>
            <div v-else-if="filteredAccounts.length === 0" class="list-empty">
              <i class="pi pi-search"></i>
              <span>{{ t('accountPicker.notFound') }}</span>
            </div>
          </div>
        </div>

        <!-- Right Panel: Selected -->
        <div class="picker-panel selected-panel">
          <div class="panel-header">
            <span class="panel-title">{{ t('accountPicker.selectedPanel') }}</span>
            <span class="panel-badge selected-badge">{{ modelValue.length }}</span>
          </div>

          <!-- Batch action -->
          <div class="panel-action-bar">
            <button class="batch-btn remove-all-btn" @click="removeAll" :disabled="modelValue.length === 0">
              <i class="pi pi-angle-double-left"></i>
              <span>{{ t('accountPicker.removeAll') }}</span>
            </button>
          </div>

          <!-- Selected List (virtual scroll) -->
          <div
            ref="selectedListRef"
            class="account-list"
            @scroll="onSelectedScroll"
          >
            <div v-if="selectedAccounts.length > 0" :style="{ paddingTop: visibleSelected.topPad + 'px', paddingBottom: visibleSelected.bottomPad + 'px' }">
              <div
                v-for="account in visibleSelected.items"
                :key="account.id"
                class="account-row selected-row"
                @click="removeAccount(account.id)"
              >
                <div class="account-remove-icon">
                  <i class="pi pi-times"></i>
                </div>
                <div class="account-info">
                  <span class="account-name">{{ displayName(account) }}</span>
                  <span class="account-sub">{{ displaySub(account) }}</span>
                </div>
              </div>
            </div>

            <div v-if="modelValue.length === 0" class="list-empty">
              <div class="empty-icon-box">
                <i class="pi pi-inbox"></i>
              </div>
              <span>{{ t('accountPicker.noAccountsSelected') }}</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.account-picker {
  --accent: #a855f7;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 14px;
  overflow: hidden;
}

/* Header */
.picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  cursor: pointer;
  transition: background 0.15s;
  user-select: none;
}

.picker-header:hover {
  background: var(--color-bg-hover);
}

.picker-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.picker-icon {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
}

.picker-icon i {
  font-size: 14px;
  color: var(--accent);
}

.picker-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.picker-count {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-disabled);
  background: var(--color-bg-hover);
  padding: 3px 10px;
  border-radius: 20px;
  transition: all 0.2s;
}

.picker-count.active {
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

.picker-toggle {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--color-text-disabled);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  transition: all 0.2s;
}

.picker-toggle:hover {
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
}

.picker-toggle i {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.picker-toggle.collapsed i {
  transform: rotate(180deg);
}

/* Slide transition */
.picker-slide-enter-active,
.picker-slide-leave-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.picker-slide-enter-from,
.picker-slide-leave-to {
  max-height: 0;
  opacity: 0;
}

.picker-slide-enter-to,
.picker-slide-leave-from {
  max-height: 600px;
  opacity: 1;
}

/* Body */
.picker-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--color-border);
  border-top: 1px solid var(--color-border);
}

/* Panels */
.picker-panel {
  background: var(--color-bg-base);
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
}

.panel-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.panel-badge {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-muted);
  background: var(--color-bg-hover);
  padding: 2px 8px;
  border-radius: 10px;
  min-width: 22px;
  text-align: center;
}

.panel-badge.selected-badge {
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

.panel-filter-hint {
  font-size: 10px;
  color: var(--color-text-disabled);
}

/* Filters */
.panel-filters {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-bottom: 1px solid var(--color-border);
}

.search-row {
  display: flex;
  gap: 6px;
}

.search-input-wrap {
  flex: 1;
  position: relative;
}

.search-input-wrap i {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: var(--color-text-disabled);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 32px;
  padding: 0 10px 0 30px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-bg-input);
  color: var(--color-text-primary);
  font-size: 12px;
  outline: none;
  transition: border-color 0.15s;
}

.search-input::placeholder {
  color: var(--color-text-disabled);
}

.search-input:focus {
  border-color: var(--accent);
}

.filter-row {
  display: flex;
  gap: 6px;
}

.filter-select {
  flex: 1;
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-bg-input);
  color: var(--color-text-secondary);
  font-size: 11px;
  outline: none;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2371717a' stroke-width='1.5' fill='none'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  padding-right: 24px;
}

.filter-select:focus {
  border-color: var(--accent);
}

.filter-select option {
  background: var(--color-bg-elevated);
  color: var(--color-text-primary);
}

/* Batch action bar */
.panel-action-bar {
  padding: 8px 14px;
  border-bottom: 1px solid var(--color-border);
}

.batch-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.batch-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.batch-btn i {
  font-size: 12px;
}

.batch-count {
  color: var(--color-text-disabled);
  font-weight: 500;
}

.add-all-btn:not(:disabled):hover {
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 30%, transparent);
  background: color-mix(in srgb, var(--accent) 6%, transparent);
}

.remove-all-btn:not(:disabled):hover {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.06);
}

/* Account List */
.account-list {
  flex: 1;
  max-height: 280px;
  overflow-y: auto;
  padding: 4px;
}

.account-list::-webkit-scrollbar {
  width: 4px;
}

.account-list::-webkit-scrollbar-track {
  background: transparent;
}

.account-list::-webkit-scrollbar-thumb {
  background: var(--color-border-hover);
  border-radius: 3px;
}

/* Account Row */
.account-row {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 42px;
  padding: 0 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.1s, border-color 0.1s;
  border: 1px solid transparent;
}

.account-row:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-border);
}

.account-row:active {
  transform: scale(0.99);
}

.account-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.account-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}

.account-sub {
  font-size: 11px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}

/* Tags */
.account-tags {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.tag {
  font-size: 9px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 5px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.tag-valid {
  color: #16a34a;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.tag-proxy {
  color: #2563eb;
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.tag-geo {
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
  border: 1px solid var(--color-border);
}

.account-arrow {
  color: var(--color-text-disabled);
  font-size: 10px;
  transition: color 0.15s, transform 0.15s;
}

.account-row:hover .account-arrow {
  color: var(--accent);
  transform: translateX(2px);
}

/* Selected row */
.selected-row {
  flex-direction: row;
}

.account-remove-icon {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(239, 68, 68, 0.08);
  color: var(--color-text-disabled);
  transition: all 0.15s;
  flex-shrink: 0;
}

.account-remove-icon i {
  font-size: 10px;
}

.selected-row:hover .account-remove-icon {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

/* Empty state */
.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 28px 16px;
  text-align: center;
}

.list-empty i {
  font-size: 22px;
  color: var(--color-text-disabled);
}

.list-empty span {
  font-size: 11px;
  color: var(--color-text-disabled);
}

.empty-icon-box {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--color-bg-hover);
  border: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-icon-box i {
  font-size: 18px;
  color: var(--color-text-disabled);
}
</style>
