<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAccountStore } from '@/stores'
import type { Account, TwoFAStatus } from '@/types'

import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
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
const checking = ref(false)
const status = ref<TwoFAStatus | null>(null)
const activeTab = ref(0)

// Form fields
const setPassword = ref('')
const setPasswordConfirm = ref('')
const setHint = ref('')
const changeCurrentPassword = ref('')
const changeNewPassword = ref('')
const changeNewPasswordConfirm = ref('')
const changeHint = ref('')
const removePassword = ref('')

// Computed
const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const canSet = computed(() =>
  setPassword.value.length >= 1 &&
  setPassword.value === setPasswordConfirm.value
)

const canChange = computed(() =>
  changeCurrentPassword.value.length >= 1 &&
  changeNewPassword.value.length >= 1 &&
  changeNewPassword.value === changeNewPasswordConfirm.value
)

const canRemove = computed(() =>
  removePassword.value.length >= 1
)

// Watch for dialog open
watch(() => props.visible, async (visible) => {
  if (visible && props.account) {
    await check2FAStatus()
  } else {
    resetForm()
  }
})

// Methods
async function check2FAStatus() {
  if (!props.account) return

  checking.value = true
  status.value = null

  try {
    status.value = await accountStore.check2FAStatus(props.account.id)

    // Set active tab based on status
    if (status.value.has_2fa) {
      activeTab.value = 1 // Change tab
    } else {
      activeTab.value = 0 // Set tab
    }
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || error.detail,
      life: 3000
    })
  } finally {
    checking.value = false
  }
}

async function handleSet2FA() {
  if (!props.account || !canSet.value) return

  loading.value = true
  try {
    const result = await accountStore.set2FA(props.account.id, {
      password: setPassword.value,
      hint: setHint.value || undefined
    })

    if (result.success) {
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('accounts.twoFA.setSuccess'),
        life: 3000
      })
      emit('updated')
      dialogVisible.value = false
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

async function handleChange2FA() {
  if (!props.account || !canChange.value) return

  loading.value = true
  try {
    const result = await accountStore.change2FA(props.account.id, {
      current_password: changeCurrentPassword.value,
      new_password: changeNewPassword.value,
      new_hint: changeHint.value || undefined
    })

    if (result.success) {
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('accounts.twoFA.changeSuccess'),
        life: 3000
      })
      emit('updated')
      dialogVisible.value = false
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

async function handleRemove2FA() {
  if (!props.account || !canRemove.value) return

  loading.value = true
  try {
    const result = await accountStore.remove2FA(props.account.id, {
      current_password: removePassword.value
    })

    if (result.success) {
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('accounts.twoFA.removeSuccess'),
        life: 3000
      })
      emit('updated')
      dialogVisible.value = false
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

function resetForm() {
  setPassword.value = ''
  setPasswordConfirm.value = ''
  setHint.value = ''
  changeCurrentPassword.value = ''
  changeNewPassword.value = ''
  changeNewPasswordConfirm.value = ''
  changeHint.value = ''
  removePassword.value = ''
  status.value = null
  activeTab.value = 0
}

function copyPassword() {
  if (props.account?.two_fa_password) {
    navigator.clipboard.writeText(props.account.two_fa_password)
    toast.add({
      severity: 'info',
      summary: t('common.copied'),
      life: 1500
    })
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
    :header="t('accounts.twoFA.title')"
    modal
    :style="{ width: '480px' }"
    :closable="!loading"
    class="twofa-dialog"
  >
    <!-- Loading State -->
    <div v-if="checking" class="loading-state">
      <ProgressSpinner style="width: 48px; height: 48px" />
      <p>{{ t('accounts.twoFA.checking') }}</p>
    </div>

    <template v-else>
      <!-- Account Info -->
      <div class="account-info-box">
        <div class="account-avatar">
          {{ (account?.first_name || account?.username || '?')[0].toUpperCase() }}
        </div>
        <div class="account-details">
          <div class="account-name">{{ getAccountName() }}</div>
          <div class="account-status" :class="status?.has_2fa ? 'enabled' : 'disabled'">
            <i :class="status?.has_2fa ? 'pi pi-lock' : 'pi pi-lock-open'"></i>
            {{ status?.has_2fa ? t('accounts.twoFA.enabled') : t('accounts.twoFA.disabled') }}
          </div>
        </div>
      </div>

      <!-- Error Message -->
      <Message v-if="status?.error" severity="error" :closable="false" class="mb-3">
        {{ status.error }}
      </Message>

      <!-- Hint -->
      <div v-if="status?.password_hint" class="hint-box">
        <i class="pi pi-info-circle"></i>
        <span>{{ t('accounts.twoFA.hint') }}: {{ status.password_hint }}</span>
      </div>

      <!-- Saved Password -->
      <div v-if="account?.two_fa_password" class="saved-password-box" @click="copyPassword">
        <i class="pi pi-key"></i>
        <span class="saved-password-label">{{ t('accounts.twoFA.savedPassword') }}:</span>
        <code class="saved-password-value">{{ account.two_fa_password }}</code>
        <i class="pi pi-copy copy-icon"></i>
      </div>

      <!-- Tabs -->
      <TabView v-model:activeIndex="activeTab" class="twofa-tabs">
        <!-- Set 2FA Tab -->
        <TabPanel :value="0" :header="t('accounts.twoFA.set')" :disabled="status?.has_2fa">
          <div class="tab-content">
            <div class="form-field">
              <label class="form-label">{{ t('accounts.twoFA.password') }}</label>
              <InputText
                v-model="setPassword"
                type="password"
                :placeholder="t('accounts.twoFA.enterPassword')"
                class="w-full"
                :disabled="loading"
              />
            </div>

            <div class="form-field">
              <label class="form-label">{{ t('accounts.twoFA.confirmPassword') }}</label>
              <InputText
                v-model="setPasswordConfirm"
                type="password"
                :placeholder="t('accounts.twoFA.confirmPasswordPlaceholder')"
                class="w-full"
                :disabled="loading"
              />
              <small v-if="setPassword && setPasswordConfirm && setPassword !== setPasswordConfirm" class="error-text">
                {{ t('accounts.twoFA.errors.passwordMismatch') }}
              </small>
            </div>

            <div class="form-field">
              <label class="form-label">{{ t('accounts.twoFA.passwordHint') }}</label>
              <InputText
                v-model="setHint"
                :placeholder="t('accounts.twoFA.hintPlaceholder')"
                class="w-full"
                :disabled="loading"
              />
            </div>

            <Button
              :label="t('accounts.twoFA.set')"
              icon="pi pi-lock"
              :loading="loading"
              :disabled="!canSet"
              @click="handleSet2FA"
              class="w-full"
            />
          </div>
        </TabPanel>

        <!-- Change 2FA Tab -->
        <TabPanel :value="1" :header="t('accounts.twoFA.change')" :disabled="!status?.has_2fa">
          <div class="tab-content">
            <div class="form-field">
              <label class="form-label">{{ t('accounts.twoFA.currentPassword') }}</label>
              <InputText
                v-model="changeCurrentPassword"
                type="password"
                :placeholder="t('accounts.twoFA.enterCurrentPassword')"
                class="w-full"
                :disabled="loading"
              />
            </div>

            <div class="form-field">
              <label class="form-label">{{ t('accounts.twoFA.newPassword') }}</label>
              <InputText
                v-model="changeNewPassword"
                type="password"
                :placeholder="t('accounts.twoFA.enterNewPassword')"
                class="w-full"
                :disabled="loading"
              />
            </div>

            <div class="form-field">
              <label class="form-label">{{ t('accounts.twoFA.confirmNewPassword') }}</label>
              <InputText
                v-model="changeNewPasswordConfirm"
                type="password"
                :placeholder="t('accounts.twoFA.confirmNewPasswordPlaceholder')"
                class="w-full"
                :disabled="loading"
              />
              <small v-if="changeNewPassword && changeNewPasswordConfirm && changeNewPassword !== changeNewPasswordConfirm" class="error-text">
                {{ t('accounts.twoFA.errors.passwordMismatch') }}
              </small>
            </div>

            <div class="form-field">
              <label class="form-label">{{ t('accounts.twoFA.newHint') }}</label>
              <InputText
                v-model="changeHint"
                :placeholder="t('accounts.twoFA.hintPlaceholder')"
                class="w-full"
                :disabled="loading"
              />
            </div>

            <Button
              :label="t('accounts.twoFA.change')"
              icon="pi pi-sync"
              :loading="loading"
              :disabled="!canChange"
              @click="handleChange2FA"
              class="w-full"
            />
          </div>
        </TabPanel>

        <!-- Remove 2FA Tab -->
        <TabPanel :value="2" :header="t('accounts.twoFA.remove')" :disabled="!status?.has_2fa">
          <div class="tab-content">
            <Message severity="warn" :closable="false" class="mb-3">
              {{ t('accounts.twoFA.removeWarning') }}
            </Message>

            <div class="form-field">
              <label class="form-label">{{ t('accounts.twoFA.currentPassword') }}</label>
              <InputText
                v-model="removePassword"
                type="password"
                :placeholder="t('accounts.twoFA.enterCurrentPassword')"
                class="w-full"
                :disabled="loading"
              />
            </div>

            <Button
              :label="t('accounts.twoFA.remove')"
              icon="pi pi-trash"
              severity="danger"
              :loading="loading"
              :disabled="!canRemove"
              @click="handleRemove2FA"
              class="w-full"
            />
          </div>
        </TabPanel>
      </TabView>
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
  background: rgba(255, 255, 255, 0.10);
  border-radius: 12px;
  margin-bottom: 16px;
}

.account-avatar {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
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

.account-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  margin-top: 4px;
}

.account-status.enabled {
  color: #22c55e;
}

.account-status.disabled {
  color: #8b8f9a;
}

.hint-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(168, 85, 247, 0.1);
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  color: #a855f7;
}

.saved-password-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 8px;
  margin-bottom: 16px;
  cursor: pointer;
  transition: background 0.15s;
}

.saved-password-box:hover {
  background: rgba(34, 197, 94, 0.14);
}

.saved-password-box .pi-key {
  color: #22c55e;
  font-size: 14px;
}

.saved-password-label {
  font-size: 13px;
  color: #9ca3af;
}

.saved-password-value {
  font-size: 14px;
  color: #e5e7eb;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.copy-icon {
  margin-left: auto;
  color: #6b7280;
  font-size: 12px;
}

.saved-password-box:hover .copy-icon {
  color: #22c55e;
}

.tab-content {
  padding: 16px 0;
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

.error-text {
  color: #ef4444;
  font-size: 12px;
  margin-top: 4px;
}

:deep(.twofa-dialog .p-dialog-header) {
  background: #161616;
  border-bottom: 1px solid rgba(255, 255, 255, 0.10);
}

:deep(.twofa-dialog .p-dialog-content) {
  background: #161616;
  padding-top: 20px;
}

:deep(.twofa-tabs .p-tabview-nav) {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.10);
}

:deep(.twofa-tabs .p-tabview-nav li .p-tabview-nav-link) {
  background: transparent;
  border-color: transparent;
  color: #8b8f9a;
}

:deep(.twofa-tabs .p-tabview-nav li.p-highlight .p-tabview-nav-link) {
  color: #a855f7;
  border-color: #a855f7;
  background: transparent;
}

:deep(.twofa-tabs .p-tabview-nav li.p-disabled .p-tabview-nav-link) {
  color: #4b5563;
  cursor: not-allowed;
}

:deep(.twofa-tabs .p-tabview-panels) {
  background: transparent;
  padding: 0;
}
</style>
