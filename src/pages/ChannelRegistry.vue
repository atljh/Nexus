<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import MainLayout from '@/layouts/MainLayout.vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'

import { useChannelStore } from '@/stores/useChannelStore'
import type { ChannelMembership, ChannelMembershipStatus, SavedChannel } from '@/types'

const { t } = useI18n()
const toast = useToast()
const channelStore = useChannelStore()

const searchQuery = ref('')
const selectedChannelId = ref<number | null>(null)
const membershipFilter = ref<'all' | ChannelMembershipStatus>('all')

const targetInput = ref('')
const inviteLinkInput = ref('')
const titleInput = ref('')
const editingChannelId = ref<number | null>(null)
const isSubmitting = ref(false)
const subscribingIds = ref<number[]>([])

function isSubscribing(channelId: number): boolean {
  return subscribingIds.value.includes(channelId)
}

const membershipFilterOptions = computed(() => [
  { value: 'all', label: t('channels.filters.all') },
  { value: 'member', label: t('channels.filters.member') },
  { value: 'pending_approval', label: t('channels.filters.pending') },
  { value: 'failed', label: t('channels.filters.failed') },
  { value: 'unknown', label: t('channels.filters.unknown') }
])

const filteredChannels = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  const values = [...channelStore.channels]
    .sort((a, b) => {
      const aMembers = a.members_count ?? 0
      const bMembers = b.members_count ?? 0
      if (aMembers !== bMembers) return bMembers - aMembers
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    })

  if (!query) return values

  return values.filter((channel) =>
    [
      channel.display_name,
      channel.title,
      channel.normalized_target,
      channel.invite_link
    ].some(value => value?.toLowerCase().includes(query))
  )
})

const selectedChannel = computed(() =>
  channelStore.currentChannel?.id === selectedChannelId.value
    ? channelStore.currentChannel
    : channelStore.channels.find(channel => channel.id === selectedChannelId.value) ?? null
)

const filteredMemberships = computed(() => {
  if (membershipFilter.value === 'all') return channelStore.memberships
  return channelStore.memberships.filter((membership) => membership.status === membershipFilter.value)
})

const channelStats = computed(() => ({
  total: channelStore.channels.length,
  members: channelStore.channels.reduce((sum, channel) => sum + (channel.members_count || 0), 0),
  pending: channelStore.channels.reduce((sum, channel) => sum + (channel.pending_count || 0), 0)
}))

function resetForm(): void {
  editingChannelId.value = null
  targetInput.value = ''
  inviteLinkInput.value = ''
  titleInput.value = ''
}

function applyChannelToForm(channel: SavedChannel): void {
  editingChannelId.value = channel.id
  targetInput.value = channel.normalized_target ?? channel.invite_link ?? ''
  inviteLinkInput.value = channel.invite_link ?? ''
  titleInput.value = channel.title ?? ''
}

async function submitChannel(): Promise<void> {
  if (!targetInput.value.trim() && !inviteLinkInput.value.trim()) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('channels.messages.targetRequired'),
      life: 3000
    })
    return
  }

  isSubmitting.value = true
  try {
    const isEditing = editingChannelId.value !== null
    const payload = {
      target: targetInput.value.trim() || undefined,
      invite_link: inviteLinkInput.value.trim() || undefined,
      title: titleInput.value.trim() || undefined
    }

    const channel = editingChannelId.value
      ? await channelStore.updateChannel(editingChannelId.value, payload)
      : await channelStore.createChannel(payload)

    if (!channel) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('channels.messages.saveFailed'),
        life: 3000
      })
      return
    }

    await channelStore.fetchChannels('', true)
    selectedChannelId.value = channel.id
    await channelStore.fetchMemberships(channel.id)
    resetForm()

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: isEditing ? t('channels.messages.updated') : t('channels.messages.created'),
      life: 3000
    })
  } finally {
    isSubmitting.value = false
  }
}

async function selectChannel(channelId: number): Promise<void> {
  selectedChannelId.value = channelId
  await channelStore.fetchMemberships(channelId)
}

async function removeChannel(channelId: number): Promise<void> {
  const deleted = await channelStore.deleteChannel(channelId)
  if (!deleted) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('channels.messages.deleteFailed'),
      life: 3000
    })
    return
  }

  if (selectedChannelId.value === channelId) {
    selectedChannelId.value = null
    channelStore.clearMemberships()
  }
  if (editingChannelId.value === channelId) {
    resetForm()
  }

  toast.add({
    severity: 'success',
    summary: t('common.success'),
    detail: t('channels.messages.deleted'),
    life: 3000
  })
}

async function subscribeUnsubscribed(channel: SavedChannel): Promise<void> {
  if (isSubscribing(channel.id)) return
  subscribingIds.value = [...subscribingIds.value, channel.id]
  try {
    const result = await channelStore.subscribeUnsubscribed(channel.id)
    if (!result || !result.success) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('channels.messages.subscribeFailed'),
        life: 4000
      })
      return
    }

    if (!result.task_id || result.total === 0) {
      toast.add({
        severity: 'info',
        summary: t('common.info'),
        detail: t('channels.messages.subscribeAllDone'),
        life: 4000
      })
      return
    }

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('channels.messages.subscribeStarted', { count: result.total }),
      life: 5000
    })

    await pollSubscribeProgress(channel.id, result.task_id)
  } catch {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('channels.messages.subscribeFailed'),
      life: 4000
    })
  } finally {
    subscribingIds.value = subscribingIds.value.filter(id => id !== channel.id)
  }
}

async function pollSubscribeProgress(channelId: number, taskId: number): Promise<void> {
  const terminal = ['completed', 'failed', 'cancelled']
  // Poll up to ~10 minutes, refreshing the card counts as accounts join.
  for (let i = 0; i < 150; i++) {
    await new Promise(resolve => setTimeout(resolve, 4000))
    await channelStore.fetchChannel(channelId)
    if (selectedChannelId.value === channelId) {
      await channelStore.fetchMemberships(channelId)
    }
    try {
      const task = await window.api.get(`/api/tasks/${taskId}`) as { status: string }
      if (terminal.includes(task.status)) {
        await channelStore.fetchChannel(channelId)
        toast.add({
          severity: task.status === 'completed' ? 'success' : 'warn',
          summary: task.status === 'completed' ? t('common.success') : t('common.warning'),
          detail: t('channels.messages.subscribeFinished'),
          life: 5000
        })
        return
      }
    } catch {
      // keep polling — task endpoint may briefly be unavailable
    }
  }
}

function membershipSeverity(status: ChannelMembershipStatus): 'success' | 'warn' | 'danger' | 'secondary' {
  if (status === 'member') return 'success'
  if (status === 'pending_approval') return 'warn'
  if (status === 'failed') return 'danger'
  return 'secondary'
}

function accountLabel(membership: ChannelMembership): string {
  const account = membership.account
  if (!account) return `#${membership.account_id}`
  const name = [account.first_name, account.last_name].filter(Boolean).join(' ').trim()
  return name || account.username || account.phone || `#${account.id}`
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

watch(filteredChannels, async (channels) => {
  if (selectedChannelId.value !== null && channels.some(channel => channel.id === selectedChannelId.value)) return
  const first = channels[0]
  if (first) {
    await selectChannel(first.id)
  } else {
    selectedChannelId.value = null
    channelStore.clearMemberships()
  }
}, { immediate: false })

onMounted(async () => {
  await channelStore.fetchChannels('', true)
  if (channelStore.channels.length > 0) {
    await selectChannel(channelStore.channels[0].id)
  }
})
</script>

<template>
  <MainLayout>
    <div class="channels-page">
      <div class="page-header">
        <div>
          <h1>{{ t('nav.channels') }}</h1>
          <p class="header-subtitle">{{ t('channels.subtitle') }}</p>
        </div>

        <div class="stats-row">
          <div class="stat-chip">
            <span class="stat-value">{{ channelStats.total }}</span>
            <span class="stat-label">{{ t('channels.stats.saved') }}</span>
          </div>
          <div class="stat-chip">
            <span class="stat-value">{{ channelStats.members }}</span>
            <span class="stat-label">{{ t('channels.stats.members') }}</span>
          </div>
          <div class="stat-chip">
            <span class="stat-value">{{ channelStats.pending }}</span>
            <span class="stat-label">{{ t('channels.stats.pending') }}</span>
          </div>
        </div>
      </div>

      <div class="page-grid">
        <div class="channels-column">
          <div class="panel-card">
            <div class="panel-header">
              <div>
                <h2>{{ editingChannelId ? t('channels.form.editTitle') : t('channels.form.createTitle') }}</h2>
                <p>{{ t('channels.form.hint') }}</p>
              </div>
            </div>

            <div class="form-grid">
              <div class="form-group">
                <label class="form-label">{{ t('channels.form.target') }}</label>
                <InputText
                  v-model="targetInput"
                  :placeholder="t('channels.form.targetPlaceholder')"
                  class="w-full"
                />
              </div>

              <div class="form-group">
                <label class="form-label">{{ t('channels.form.inviteLink') }}</label>
                <InputText
                  v-model="inviteLinkInput"
                  :placeholder="t('channels.form.invitePlaceholder')"
                  class="w-full"
                />
              </div>

              <div class="form-group">
                <label class="form-label">{{ t('channels.form.title') }}</label>
                <InputText
                  v-model="titleInput"
                  :placeholder="t('channels.form.titlePlaceholder')"
                  class="w-full"
                />
              </div>
            </div>

            <div class="form-actions">
              <Button
                :label="editingChannelId ? t('channels.form.update') : t('channels.form.save')"
                :loading="isSubmitting"
                icon="pi pi-save"
                @click="submitChannel"
              />
              <Button
                :label="t('channels.form.reset')"
                severity="secondary"
                outlined
                icon="pi pi-times"
                @click="resetForm"
              />
            </div>
          </div>

          <div class="panel-card">
            <div class="panel-header">
              <div>
                <h2>{{ t('channels.list.title') }}</h2>
                <p>{{ t('channels.list.hint') }}</p>
              </div>
              <InputText
                v-model="searchQuery"
                :placeholder="t('channels.list.searchPlaceholder')"
                class="search-input"
              />
            </div>

            <div v-if="filteredChannels.length" class="channel-list">
              <button
                v-for="channel in filteredChannels"
                :key="channel.id"
                class="channel-card"
                :class="{ active: selectedChannelId === channel.id }"
                @click="selectChannel(channel.id)"
              >
                <div class="channel-card-head">
                  <div>
                    <div class="channel-title">{{ channel.display_name }}</div>
                    <div class="channel-meta">
                      {{ channel.normalized_target || channel.invite_link || '—' }}
                    </div>
                  </div>
                  <Tag :severity="channel.is_private ? 'warn' : 'info'" :value="channel.is_private ? t('channels.private') : t('channels.public')" />
                </div>

                <div class="channel-counts">
                  <span>{{ t('channels.counts.members', { count: channel.members_count }) }}</span>
                  <span>{{ t('channels.counts.pending', { count: channel.pending_count }) }}</span>
                  <span>{{ t('channels.counts.failed', { count: channel.failed_count }) }}</span>
                </div>

                <div class="channel-actions">
                  <Button
                    :icon="isSubscribing(channel.id) ? 'pi pi-spin pi-spinner' : 'pi pi-user-plus'"
                    :label="t('channels.actions.subscribeUnsubscribed')"
                    text
                    severity="success"
                    size="small"
                    :disabled="isSubscribing(channel.id)"
                    @click.stop="subscribeUnsubscribed(channel)"
                  />
                  <Button
                    icon="pi pi-pencil"
                    text
                    severity="secondary"
                    @click.stop="applyChannelToForm(channel)"
                  />
                  <Button
                    icon="pi pi-trash"
                    text
                    severity="danger"
                    @click.stop="removeChannel(channel.id)"
                  />
                </div>
              </button>
            </div>

            <div v-else class="empty-state">
              <i class="pi pi-inbox"></i>
              <p>{{ t('channels.list.empty') }}</p>
            </div>
          </div>
        </div>

        <div class="details-column">
          <div class="panel-card detail-card">
            <div class="panel-header">
              <div>
                <h2>{{ selectedChannel?.display_name || t('channels.details.title') }}</h2>
                <p>{{ selectedChannel?.normalized_target || selectedChannel?.invite_link || t('channels.details.placeholder') }}</p>
              </div>

              <Select
                v-model="membershipFilter"
                :options="membershipFilterOptions"
                option-label="label"
                option-value="value"
                class="filter-select"
              />
            </div>

            <div v-if="selectedChannel" class="details-summary">
              <div class="summary-item">
                <span class="summary-label">{{ t('channels.details.members') }}</span>
                <span class="summary-value">{{ selectedChannel.members_count }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">{{ t('channels.details.pending') }}</span>
                <span class="summary-value">{{ selectedChannel.pending_count }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">{{ t('channels.details.failed') }}</span>
                <span class="summary-value">{{ selectedChannel.failed_count }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">{{ t('channels.details.lastResolved') }}</span>
                <span class="summary-value">{{ formatDate(selectedChannel.last_resolved_at) }}</span>
              </div>
            </div>

            <div v-if="channelStore.membershipsLoading" class="empty-state">
              <i class="pi pi-spin pi-spinner"></i>
              <p>{{ t('common.loading') }}</p>
            </div>

            <div v-else-if="filteredMemberships.length" class="membership-list">
              <div
                v-for="membership in filteredMemberships"
                :key="membership.id"
                class="membership-row"
              >
                <div class="membership-main">
                  <div class="membership-title">{{ accountLabel(membership) }}</div>
                  <div class="membership-meta">
                    <span v-if="membership.account?.phone">{{ membership.account.phone }}</span>
                    <span v-if="membership.account?.username">@{{ membership.account.username }}</span>
                    <span>{{ t('channels.details.checkedAt') }}: {{ formatDate(membership.last_checked_at) }}</span>
                  </div>
                  <div v-if="membership.last_error" class="membership-error">{{ membership.last_error }}</div>
                </div>

                <div class="membership-side">
                  <Tag
                    :severity="membershipSeverity(membership.status)"
                    :value="t(`channels.filters.${membership.status === 'pending_approval' ? 'pending' : membership.status}`)"
                  />
                  <span class="account-status">{{ membership.account?.status || '—' }}</span>
                </div>
              </div>
            </div>

            <div v-else class="empty-state">
              <i class="pi pi-users"></i>
              <p>{{ selectedChannel ? t('channels.details.empty') : t('channels.details.selectPrompt') }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.channels-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.page-header h1 {
  margin: 0;
  font-size: 32px;
  font-weight: 800;
  color: #f8fafc;
}

.header-subtitle {
  margin: 8px 0 0;
  color: #94a3b8;
}

.stats-row {
  display: flex;
  gap: 12px;
}

.stat-chip {
  min-width: 120px;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.7));
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.stat-value {
  display: block;
  font-size: 26px;
  font-weight: 800;
  color: #f8fafc;
}

.stat-label {
  display: block;
  margin-top: 4px;
  color: #94a3b8;
  font-size: 13px;
}

.page-grid {
  display: grid;
  grid-template-columns: minmax(360px, 520px) minmax(0, 1fr);
  gap: 20px;
}

.channels-column,
.details-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-card {
  border-radius: 22px;
  padding: 20px;
  background:
    radial-gradient(circle at top right, rgba(249, 115, 22, 0.1), transparent 32%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.95), rgba(10, 15, 27, 0.92));
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: 0 20px 48px rgba(2, 6, 23, 0.28);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.panel-header h2 {
  margin: 0;
  color: #f8fafc;
  font-size: 20px;
}

.panel-header p {
  margin: 6px 0 0;
  color: #94a3b8;
  font-size: 13px;
}

.form-grid {
  display: grid;
  gap: 14px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  color: #cbd5e1;
  font-size: 13px;
  font-weight: 600;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.search-input,
.filter-select {
  width: 240px;
}

.channel-list,
.membership-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.channel-card {
  width: 100%;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.58);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, transform 0.18s ease, background 0.18s ease;
}

.channel-card:hover,
.channel-card.active {
  border-color: rgba(249, 115, 22, 0.65);
  background: rgba(30, 41, 59, 0.78);
  transform: translateY(-1px);
}

.channel-card-head,
.channel-actions,
.membership-row,
.membership-side,
.details-summary {
  display: flex;
}

.channel-card-head,
.membership-row {
  justify-content: space-between;
  gap: 12px;
}

.channel-title,
.membership-title {
  color: #f8fafc;
  font-weight: 700;
}

.channel-meta,
.membership-meta,
.account-status {
  color: #94a3b8;
  font-size: 12px;
}

.channel-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 10px;
  color: #cbd5e1;
  font-size: 12px;
}

.channel-actions {
  justify-content: flex-end;
  margin-top: 10px;
}

.detail-card {
  min-height: 100%;
}

.details-summary {
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.summary-item {
  min-width: 132px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.52);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.summary-label {
  display: block;
  color: #94a3b8;
  font-size: 12px;
}

.summary-value {
  display: block;
  margin-top: 6px;
  color: #f8fafc;
  font-weight: 700;
}

.membership-row {
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.membership-main {
  min-width: 0;
}

.membership-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 6px;
}

.membership-error {
  margin-top: 8px;
  color: #fca5a5;
  font-size: 12px;
}

.membership-side {
  flex-direction: column;
  gap: 8px;
  align-items: flex-end;
}

.empty-state {
  display: flex;
  min-height: 220px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  color: #94a3b8;
}

.empty-state i {
  font-size: 28px;
}

@media (max-width: 1180px) {
  .page-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
  }

  .stats-row {
    width: 100%;
  }

  .search-input,
  .filter-select {
    width: 100%;
  }
}
</style>
