<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAccountStore } from '@/stores/useAccountStore'
import { useGroupStore } from '@/stores/useGroupStore'
import { useTagStore } from '@/stores/useTagStore'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  modelValue: number[]
  accentColor?: string
  defaultExpanded?: boolean
}>(), {
  accentColor: '#a855f7',
  defaultExpanded: false
})

const emit = defineEmits<{
  'update:modelValue': [ids: number[]]
}>()

const accountStore = useAccountStore()
const groupStore = useGroupStore()
const tagStore = useTagStore()

// All valid accounts
const validAccounts = computed(() =>
  accountStore.accounts.filter(a => a.status === 'valid')
)

// Whether all valid accounts are selected
const allSelected = computed(() =>
  validAccounts.value.length > 0 && validAccounts.value.every(a => props.modelValue.includes(a.id))
)

// Groups that have valid accounts
const activeGroups = computed(() => {
  const groupIds = new Set(validAccounts.value.filter(a => a.group_id).map(a => a.group_id))
  return groupStore.groups.filter(g => groupIds.has(g.id))
})

// Tags that are used by valid accounts
const activeTags = computed(() => {
  const tagIds = new Set<number>()
  validAccounts.value.forEach(a => a.tags?.forEach(tag => tagIds.add(tag.id)))
  return tagStore.tags.filter(tag => tagIds.has(tag.id))
})

// Get accounts for a group
function accountsForGroup(groupId: number) {
  return validAccounts.value.filter(a => a.group_id === groupId)
}

// Get accounts for a tag
function accountsForTag(tagId: number) {
  return validAccounts.value.filter(a => a.tags?.some(tag => tag.id === tagId))
}

// Check if all accounts in a group are selected
function isGroupSelected(groupId: number) {
  const accs = accountsForGroup(groupId)
  return accs.length > 0 && accs.every(a => props.modelValue.includes(a.id))
}

// Check if some (but not all) accounts in a group are selected
function isGroupPartial(groupId: number) {
  const accs = accountsForGroup(groupId)
  const selected = accs.filter(a => props.modelValue.includes(a.id))
  return selected.length > 0 && selected.length < accs.length
}

// Check if all accounts with a tag are selected
function isTagSelected(tagId: number) {
  const accs = accountsForTag(tagId)
  return accs.length > 0 && accs.every(a => props.modelValue.includes(a.id))
}

function isTagPartial(tagId: number) {
  const accs = accountsForTag(tagId)
  const selected = accs.filter(a => props.modelValue.includes(a.id))
  return selected.length > 0 && selected.length < accs.length
}

// Toggle all
function toggleAll() {
  if (allSelected.value) {
    emit('update:modelValue', [])
  } else {
    emit('update:modelValue', validAccounts.value.map(a => a.id))
  }
}

// Toggle group
function toggleGroup(groupId: number) {
  const accs = accountsForGroup(groupId)
  const accIds = accs.map(a => a.id)
  if (isGroupSelected(groupId)) {
    // Remove these accounts
    emit('update:modelValue', props.modelValue.filter(id => !accIds.includes(id)))
  } else {
    // Add these accounts
    const merged = [...new Set([...props.modelValue, ...accIds])]
    emit('update:modelValue', merged)
  }
}

// Toggle tag
function toggleTag(tagId: number) {
  const accs = accountsForTag(tagId)
  const accIds = accs.map(a => a.id)
  if (isTagSelected(tagId)) {
    emit('update:modelValue', props.modelValue.filter(id => !accIds.includes(id)))
  } else {
    const merged = [...new Set([...props.modelValue, ...accIds])]
    emit('update:modelValue', merged)
  }
}

// Ensure data is loaded
onMounted(async () => {
  if (accountStore.accounts.length === 0) await accountStore.fetchAccounts()
  if (groupStore.groups.length === 0) await groupStore.fetchGroups()
  if (tagStore.tags.length === 0) await tagStore.fetchTags()
})
</script>

<template>
  <div class="account-picker" :style="{ '--accent': accentColor }">
    <!-- Header row -->
    <div class="picker-header">
      <div class="picker-header-left">
        <div class="picker-icon">
          <i class="pi pi-users"></i>
        </div>
        <span class="picker-title">{{ t('accountPicker.title') }}</span>
        <span class="picker-count" :class="{ active: modelValue.length > 0 }">
          {{ t('accountPicker.selected', { count: modelValue.length }) }}
        </span>
      </div>
    </div>

    <!-- Selection chips -->
    <div class="picker-chips">
      <!-- All accounts button -->
      <button
        class="chip chip-all"
        :class="{ selected: allSelected, partial: !allSelected && modelValue.length > 0 }"
        @click="toggleAll"
      >
        <i :class="allSelected ? 'pi pi-check-square' : 'pi pi-stop'"></i>
        <span>{{ t('accountPicker.allGroups') }}</span>
        <span class="chip-count">{{ validAccounts.length }}</span>
      </button>

      <!-- Separator if groups or tags exist -->
      <div v-if="activeGroups.length > 0 || activeTags.length > 0" class="chip-separator"></div>

      <!-- Groups -->
      <button
        v-for="group in activeGroups"
        :key="'g-' + group.id"
        class="chip chip-group"
        :class="{ selected: isGroupSelected(group.id), partial: isGroupPartial(group.id) }"
        @click="toggleGroup(group.id)"
      >
        <span class="chip-dot" :style="{ background: group.color || 'var(--color-text-muted)' }"></span>
        <span>{{ group.name }}</span>
        <span class="chip-count">{{ accountsForGroup(group.id).length }}</span>
      </button>

      <!-- Tags -->
      <button
        v-for="tag in activeTags"
        :key="'t-' + tag.id"
        class="chip chip-tag"
        :class="{ selected: isTagSelected(tag.id), partial: isTagPartial(tag.id) }"
        @click="toggleTag(tag.id)"
      >
        <span class="chip-dot" :style="{ background: tag.color }"></span>
        <span>{{ tag.name }}</span>
        <span class="chip-count">{{ accountsForTag(tag.id).length }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.account-picker {
  --accent: #a855f7;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  overflow: hidden;
}

/* Header */
.picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 0;
}

.picker-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.picker-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
}

.picker-icon i {
  font-size: 13px;
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
  padding: 2px 10px;
  border-radius: 20px;
  transition: all 0.2s;
}

.picker-count.active {
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

/* Chips area */
.picker-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 12px 16px;
}

.chip-separator {
  width: 1px;
  height: 24px;
  background: var(--color-border);
  align-self: center;
  margin: 0 4px;
}

/* Chip base */
.chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.chip:hover {
  border-color: var(--color-border-hover);
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
}

.chip i {
  font-size: 12px;
}

.chip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.chip-count {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-disabled);
  background: var(--color-bg-hover);
  padding: 1px 6px;
  border-radius: 6px;
  min-width: 18px;
  text-align: center;
}

/* Selected state */
.chip.selected {
  border-color: color-mix(in srgb, var(--accent) 40%, transparent);
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
}

.chip.selected .chip-count {
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  color: var(--accent);
}

.chip.selected i {
  color: var(--accent);
}

/* Partial state */
.chip.partial {
  border-color: color-mix(in srgb, var(--accent) 25%, transparent);
  background: color-mix(in srgb, var(--accent) 5%, transparent);
  color: var(--color-text-secondary);
}

.chip.partial .chip-count {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
}
</style>
