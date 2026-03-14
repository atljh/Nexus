<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAccountStore } from '@/stores'
import type { Account } from '@/types'

import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import ProgressSpinner from 'primevue/progressspinner'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'

const props = defineProps<{
  visible: boolean
  account: Account | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'updated'): void
}>()

const { t } = useI18n()
const toast = useToast()
const accountStore = useAccountStore()

// State
const loading = ref(false)
const fetching = ref(false)
const fetchError = ref<string | null>(null)

// Form fields
const firstName = ref('')
const lastName = ref('')
const bio = ref('')
const username = ref('')

// Computed
const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const hasChanges = computed(() => {
  if (!props.account) return false
  return (
    firstName.value !== (props.account.first_name || '') ||
    lastName.value !== (props.account.last_name || '') ||
    bio.value !== currentBio.value ||
    username.value !== (props.account.username || '')
  )
})

const currentBio = ref('')

// Watch dialog open
watch(() => props.visible, async (visible) => {
  if (visible && props.account) {
    // Pre-fill from local data
    firstName.value = props.account.first_name || ''
    lastName.value = props.account.last_name || ''
    username.value = props.account.username || ''
    bio.value = ''
    currentBio.value = ''
    fetchError.value = null

    // Fetch current profile from Telegram
    await fetchCurrentProfile()
  } else {
    // Cleanup on close
    firstName.value = ''
    lastName.value = ''
    bio.value = ''
    currentBio.value = ''
    username.value = ''
    fetchError.value = null
  }
})

async function fetchCurrentProfile() {
  if (!props.account) return

  fetching.value = true
  fetchError.value = null

  try {
    const profile = await accountStore.getCurrentProfile(props.account.id)
    firstName.value = profile.first_name || ''
    lastName.value = profile.last_name || ''
    bio.value = profile.bio || ''
    currentBio.value = profile.bio || ''
    username.value = profile.username || ''
  } catch (error: any) {
    fetchError.value = error.message || error.detail || 'Failed to fetch profile'
    // Keep local data as fallback
  } finally {
    fetching.value = false
  }
}

async function handleSave() {
  if (!props.account || !hasChanges.value) return

  loading.value = true
  try {
    const data: Record<string, string> = {}

    if (firstName.value !== (props.account.first_name || '')) {
      data.first_name = firstName.value
    }
    if (lastName.value !== (props.account.last_name || '')) {
      data.last_name = lastName.value
    }
    if (bio.value !== currentBio.value) {
      data.bio = bio.value
    }
    if (username.value !== (props.account.username || '')) {
      data.username = username.value
    }

    const result = await accountStore.updateProfile(props.account.id, data)

    if (result.success) {
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('accounts.profile.updateSuccess'),
        life: 3000
      })
      emit('updated')
      dialogVisible.value = false
    } else if (result.errors && Object.keys(result.errors).length > 0) {
      const errorMessages = Object.entries(result.errors)
        .map(([field, msg]) => `${field}: ${msg}`)
        .join(', ')
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: errorMessages,
        life: 5000
      })
      // Partially succeeded — update fields that did work
      if (result.updated_fields.length > 0) {
        emit('updated')
      }
    }
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || error.detail,
      life: 5000
    })
  } finally {
    loading.value = false
  }
}

function getAccountName(): string {
  if (!props.account) return ''
  if (props.account.username) return `@${props.account.username}`
  if (props.account.first_name) return props.account.first_name
  if (props.account.phone) return props.account.phone
  return `ID: ${props.account.telegram_id}`
}
</script>

<template>
  <Dialog
    v-model:visible="dialogVisible"
    :header="t('accounts.profile.title')"
    modal
    :style="{ width: '480px' }"
    :closable="!loading"
    class="profile-dialog"
  >
    <!-- Loading State -->
    <div v-if="fetching" class="loading-state">
      <ProgressSpinner style="width: 48px; height: 48px" />
      <p>{{ t('accounts.profile.fetching') }}</p>
    </div>

    <template v-else>
      <!-- Account Info -->
      <div class="account-info-box">
        <div class="account-avatar">
          {{ (account?.first_name || account?.username || '?')[0].toUpperCase() }}
        </div>
        <div class="account-details">
          <div class="account-name">{{ getAccountName() }}</div>
          <div class="account-phone" v-if="account?.phone">{{ account.phone }}</div>
        </div>
      </div>

      <Message v-if="fetchError" severity="warn" :closable="false" class="mb-3">
        {{ fetchError }}
      </Message>

      <!-- Form -->
      <div class="form-field">
        <label class="form-label">{{ t('accounts.profile.firstName') }}</label>
        <InputText
          v-model="firstName"
          :placeholder="t('accounts.profile.firstNamePlaceholder')"
          class="w-full"
          :disabled="loading"
          :maxlength="64"
        />
      </div>

      <div class="form-field">
        <label class="form-label">{{ t('accounts.profile.lastName') }}</label>
        <InputText
          v-model="lastName"
          :placeholder="t('accounts.profile.lastNamePlaceholder')"
          class="w-full"
          :disabled="loading"
          :maxlength="64"
        />
      </div>

      <div class="form-field">
        <label class="form-label">
          {{ t('accounts.profile.bio') }}
          <span class="char-count">{{ bio.length }}/140</span>
        </label>
        <Textarea
          v-model="bio"
          :placeholder="t('accounts.profile.bioPlaceholder')"
          class="w-full"
          :disabled="loading"
          :maxlength="140"
          rows="3"
          autoResize
        />
      </div>

      <div class="form-field">
        <label class="form-label">{{ t('accounts.profile.username') }}</label>
        <div class="username-input">
          <span class="username-prefix">@</span>
          <InputText
            v-model="username"
            :placeholder="t('accounts.profile.usernamePlaceholder')"
            class="w-full"
            :disabled="loading"
          />
        </div>
      </div>
    </template>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        @click="dialogVisible = false"
        :disabled="loading"
      />
      <Button
        :label="t('common.save')"
        icon="pi pi-check"
        :loading="loading"
        :disabled="!hasChanges || fetching"
        @click="handleSave"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 16px;
}

.loading-state p {
  color: #9ca3af;
  font-size: 14px;
}

.account-info-box {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  margin-bottom: 20px;
}

.account-avatar {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  color: white;
}

.account-details {
  flex: 1;
}

.account-name {
  font-weight: 600;
  color: #e5e7eb;
  font-size: 15px;
}

.account-phone {
  font-size: 13px;
  color: #6b7280;
  margin-top: 2px;
}

.form-field {
  margin-bottom: 16px;
}

.form-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #9ca3af;
  margin-bottom: 8px;
  font-weight: 500;
}

.char-count {
  font-size: 11px;
  color: #6b7280;
  font-weight: 400;
}

.username-input {
  display: flex;
  align-items: center;
  gap: 0;
}

.username-prefix {
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-right: none;
  border-radius: 6px 0 0 6px;
  color: #6b7280;
  font-size: 14px;
  line-height: 1.5;
}

.username-input :deep(.p-inputtext) {
  border-radius: 0 6px 6px 0;
}

:deep(.profile-dialog .p-dialog-header) {
  background: #161616;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
}

:deep(.profile-dialog .p-dialog-content) {
  background: #161616;
  padding-top: 20px;
}

:deep(.profile-dialog .p-dialog-footer) {
  background: #161616;
  border-top: 1px solid rgba(255, 255, 255, 0.10);
}
</style>
