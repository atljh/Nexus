<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAccountStore, useProxyStore } from '@/stores'

import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Stepper from 'primevue/stepper'
import StepItem from 'primevue/stepitem'
import Step from 'primevue/step'
import StepPanel from 'primevue/steppanel'
import StepPanels from 'primevue/steppanels'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'added'): void
}>()

const { t } = useI18n()
const toast = useToast()
const accountStore = useAccountStore()
const proxyStore = useProxyStore()

// Form state
const phone = ref('')
const code = ref('')
const password = ref('')
const selectedProxyId = ref<number | null>(null)

// Countdown timer for resend
const resendCountdown = ref(0)
let countdownInterval: number | null = null

// Computed
const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const currentStep = computed(() => {
  switch (accountStore.authStep) {
    case 'phone': return 0
    case 'code': return 1
    case 'password': return 2
    case 'success': return 3
    default: return 0
  }
})

const selectedProxy = computed(() => {
  if (!selectedProxyId.value) return null
  return proxyStore.getById(selectedProxyId.value)
})

const proxyConfig = computed(() => {
  const proxy = selectedProxy.value
  if (!proxy) return undefined
  return {
    type: proxy.type as 'socks5' | 'socks4' | 'http' | 'https',
    host: proxy.host,
    port: proxy.port,
    username: proxy.username || undefined,
    password: proxy.password || undefined
  }
})

const canSubmitPhone = computed(() =>
  phone.value.length >= 10 && !accountStore.authLoading
)

const canSubmitCode = computed(() =>
  code.value.length >= 4 && !accountStore.authLoading
)

const canSubmitPassword = computed(() =>
  password.value.length >= 1 && !accountStore.authLoading
)

// Watch dialog visibility
watch(() => props.visible, (visible) => {
  if (!visible) {
    resetForm()
  }
})

// Cleanup on unmount
onUnmounted(() => {
  if (countdownInterval) {
    clearInterval(countdownInterval)
  }
})

// Methods
function resetForm() {
  phone.value = ''
  code.value = ''
  password.value = ''
  selectedProxyId.value = null
  resendCountdown.value = 0
  if (countdownInterval) {
    clearInterval(countdownInterval)
    countdownInterval = null
  }
  accountStore.resetAuth()
}

function startResendCountdown() {
  resendCountdown.value = 60
  if (countdownInterval) {
    clearInterval(countdownInterval)
  }
  countdownInterval = setInterval(() => {
    resendCountdown.value--
    if (resendCountdown.value <= 0) {
      clearInterval(countdownInterval!)
      countdownInterval = null
    }
  }, 1000) as unknown as number
}

async function handleSubmitPhone() {
  if (!canSubmitPhone.value) return

  try {
    await accountStore.startAuth({
      phone: phone.value,
      proxy: proxyConfig.value
    })

    startResendCountdown()

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.auth.codeSent'),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || error.detail,
      life: 5000
    })
  }
}

async function handleSubmitCode() {
  if (!canSubmitCode.value) return

  try {
    const result = await accountStore.verifyAuthCode(code.value)

    if (result.status === 'success') {
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('accounts.auth.success.description'),
        life: 3000
      })
      emit('added')
    }
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || error.detail,
      life: 5000
    })
  }
}

async function handleSubmitPassword() {
  if (!canSubmitPassword.value) return

  try {
    const result = await accountStore.verifyAuthCode(code.value, password.value)

    if (result.status === 'success') {
      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('accounts.auth.success.description'),
        life: 3000
      })
      emit('added')
    }
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || error.detail,
      life: 5000
    })
  }
}

async function handleResendCode() {
  if (resendCountdown.value > 0) return

  try {
    await accountStore.resendAuthCode()
    startResendCountdown()

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('accounts.auth.codeResent'),
      life: 3000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || error.detail,
      life: 5000
    })
  }
}

function handleClose() {
  if (accountStore.authLoading) return
  accountStore.cancelAuth()
  dialogVisible.value = false
}

function handleDone() {
  dialogVisible.value = false
  resetForm()
}
</script>

<template>
  <Dialog
    v-model:visible="dialogVisible"
    :header="t('accounts.auth.title')"
    modal
    :style="{ width: '500px' }"
    :closable="!accountStore.authLoading"
    class="add-account-dialog"
    @hide="resetForm"
  >
    <div class="stepper-container">
      <Stepper :value="currentStep" linear class="auth-stepper">
        <!-- Step Items -->
        <StepItem :value="0">
          <Step>{{ t('accounts.auth.steps.phone') }}</Step>
        </StepItem>
        <StepItem :value="1">
          <Step>{{ t('accounts.auth.steps.code') }}</Step>
        </StepItem>
        <StepItem :value="2">
          <Step>{{ t('accounts.auth.steps.password') }}</Step>
        </StepItem>
        <StepItem :value="3">
          <Step>{{ t('accounts.auth.steps.success') }}</Step>
        </StepItem>

        <StepPanels>
          <!-- Phone Step -->
          <StepPanel :value="0">
            <div class="step-content">
              <div class="step-header">
                <i class="pi pi-phone step-icon"></i>
                <h3>{{ t('accounts.auth.phone.title') }}</h3>
                <p>{{ t('accounts.auth.phone.description') }}</p>
              </div>

              <Message v-if="accountStore.authError" severity="error" :closable="false" class="mb-3">
                {{ accountStore.authError }}
              </Message>

              <div class="form-field">
                <label class="form-label">{{ t('accounts.auth.phone.label') }}</label>
                <InputText
                  v-model="phone"
                  :placeholder="t('accounts.auth.phone.placeholder')"
                  class="w-full"
                  :disabled="accountStore.authLoading"
                  @keyup.enter="handleSubmitPhone"
                />
                <small class="hint-text">{{ t('accounts.auth.phone.hint') }}</small>
              </div>

              <div class="form-field">
                <label class="form-label">{{ t('accounts.auth.proxy.title') }}</label>
                <Select
                  v-model="selectedProxyId"
                  :options="proxyStore.workingProxies"
                  optionLabel="host"
                  optionValue="id"
                  :placeholder="t('accounts.auth.proxy.placeholder')"
                  class="w-full"
                  showClear
                  :disabled="accountStore.authLoading"
                >
                  <template #value="{ value }">
                    <span v-if="value">
                      {{ proxyStore.getById(value)?.host }}:{{ proxyStore.getById(value)?.port }}
                    </span>
                    <span v-else class="placeholder-text">{{ t('accounts.auth.proxy.noProxy') }}</span>
                  </template>
                  <template #option="{ option }">
                    <div class="proxy-option">
                      <span>{{ option.host }}:{{ option.port }}</span>
                      <span class="proxy-type">{{ option.type }}</span>
                    </div>
                  </template>
                </Select>
              </div>

              <div class="step-actions">
                <Button
                  :label="t('common.cancel')"
                  severity="secondary"
                  :disabled="accountStore.authLoading"
                  @click="handleClose"
                />
                <Button
                  :label="t('accounts.auth.sendCode')"
                  icon="pi pi-arrow-right"
                  iconPos="right"
                  :loading="accountStore.authLoading"
                  :disabled="!canSubmitPhone"
                  @click="handleSubmitPhone"
                />
              </div>
            </div>
          </StepPanel>

          <!-- Code Step -->
          <StepPanel :value="1">
            <div class="step-content">
              <div class="step-header">
                <i class="pi pi-key step-icon"></i>
                <h3>{{ t('accounts.auth.code.title') }}</h3>
                <p>{{ t('accounts.auth.code.description') }}</p>
              </div>

              <Message v-if="accountStore.authError && accountStore.authStep === 'code'" severity="error" :closable="false" class="mb-3">
                {{ accountStore.authError }}
              </Message>

              <div class="phone-display">
                <i class="pi pi-phone"></i>
                <span>{{ accountStore.authPhone }}</span>
              </div>

              <div class="form-field">
                <label class="form-label">{{ t('accounts.auth.code.label') }}</label>
                <InputText
                  v-model="code"
                  :placeholder="t('accounts.auth.code.placeholder')"
                  class="w-full code-input"
                  :disabled="accountStore.authLoading"
                  maxlength="6"
                  @keyup.enter="handleSubmitCode"
                />
              </div>

              <div class="resend-section">
                <Button
                  :label="resendCountdown > 0 ? `${t('accounts.auth.resendIn')} ${resendCountdown}s` : t('accounts.auth.resendCode')"
                  text
                  size="small"
                  :disabled="resendCountdown > 0 || accountStore.authLoading"
                  @click="handleResendCode"
                />
              </div>

              <div class="step-actions">
                <Button
                  :label="t('common.back')"
                  severity="secondary"
                  :disabled="accountStore.authLoading"
                  @click="accountStore.resetAuth()"
                />
                <Button
                  :label="t('accounts.auth.verify')"
                  icon="pi pi-check"
                  :loading="accountStore.authLoading"
                  :disabled="!canSubmitCode"
                  @click="handleSubmitCode"
                />
              </div>
            </div>
          </StepPanel>

          <!-- Password Step (2FA) -->
          <StepPanel :value="2">
            <div class="step-content">
              <div class="step-header">
                <i class="pi pi-lock step-icon"></i>
                <h3>{{ t('accounts.auth.password.title') }}</h3>
                <p>{{ t('accounts.auth.password.description') }}</p>
              </div>

              <Message v-if="accountStore.authError && accountStore.authStep === 'password'" severity="error" :closable="false" class="mb-3">
                {{ accountStore.authError }}
              </Message>

              <div class="form-field">
                <label class="form-label">{{ t('accounts.auth.password.label') }}</label>
                <InputText
                  v-model="password"
                  type="password"
                  :placeholder="t('accounts.auth.password.placeholder')"
                  class="w-full"
                  :disabled="accountStore.authLoading"
                  @keyup.enter="handleSubmitPassword"
                />
              </div>

              <div class="step-actions">
                <Button
                  :label="t('common.cancel')"
                  severity="secondary"
                  :disabled="accountStore.authLoading"
                  @click="handleClose"
                />
                <Button
                  :label="t('accounts.auth.verify')"
                  icon="pi pi-check"
                  :loading="accountStore.authLoading"
                  :disabled="!canSubmitPassword"
                  @click="handleSubmitPassword"
                />
              </div>
            </div>
          </StepPanel>

          <!-- Success Step -->
          <StepPanel :value="3">
            <div class="step-content">
              <div class="success-state">
                <div class="success-icon">
                  <i class="pi pi-check"></i>
                </div>
                <h3>{{ t('accounts.auth.success.title') }}</h3>
                <p>{{ t('accounts.auth.success.description') }}</p>
              </div>

              <div class="step-actions center">
                <Button
                  :label="t('common.done')"
                  icon="pi pi-check"
                  @click="handleDone"
                />
              </div>
            </div>
          </StepPanel>
        </StepPanels>
      </Stepper>
    </div>
  </Dialog>
</template>

<style scoped>
.stepper-container {
  padding: 16px 0;
}

.step-content {
  padding: 24px 0;
}

.step-header {
  text-align: center;
  margin-bottom: 24px;
}

.step-icon {
  font-size: 32px;
  color: #a855f7;
  margin-bottom: 12px;
}

.step-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 8px;
}

.step-header p {
  font-size: 14px;
  color: #9ca3af;
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

.hint-text {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.placeholder-text {
  color: #6b7280;
}

.proxy-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.proxy-type {
  font-size: 11px;
  color: #6b7280;
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}

.phone-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(168, 85, 247, 0.1);
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 15px;
  color: #a855f7;
}

.code-input {
  font-size: 24px;
  text-align: center;
  letter-spacing: 8px;
  font-family: monospace;
}

.resend-section {
  text-align: center;
  margin-bottom: 16px;
}

.step-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 24px;
}

.step-actions.center {
  justify-content: center;
}

.success-state {
  text-align: center;
  padding: 24px 0;
}

.success-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

.success-icon i {
  font-size: 28px;
  color: white;
}

.success-state h3 {
  font-size: 20px;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 8px;
}

.success-state p {
  font-size: 14px;
  color: #9ca3af;
}

:deep(.add-account-dialog .p-dialog-header) {
  background: #161616;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.add-account-dialog .p-dialog-content) {
  background: #161616;
  padding: 0 24px;
}

:deep(.auth-stepper .p-stepper-header) {
  background: transparent;
}

:deep(.auth-stepper .p-stepper-separator) {
  background: rgba(255, 255, 255, 0.1);
}

:deep(.auth-stepper .p-stepper-number) {
  background: rgba(255, 255, 255, 0.1);
  color: #6b7280;
  border: none;
}

:deep(.auth-stepper .p-stepper-item.p-stepper-item-active .p-stepper-number) {
  background: #a855f7;
  color: white;
}

:deep(.auth-stepper .p-stepper-title) {
  color: #6b7280;
  font-size: 12px;
}

:deep(.auth-stepper .p-stepper-item.p-stepper-item-active .p-stepper-title) {
  color: #e5e7eb;
}
</style>
