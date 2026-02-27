<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProxyStore } from '@/stores'
import Select from 'primevue/select'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import { useToast } from 'primevue/usetoast'

const props = withDefaults(defineProps<{
  modelValue: number | null
  required?: boolean
  showInlineCreate?: boolean
  onlyWorking?: boolean
  disabled?: boolean
  invalid?: boolean
}>(), {
  required: false,
  showInlineCreate: true,
  onlyWorking: true,
  disabled: false,
  invalid: false
})

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
  'proxy-created': [proxyId: number]
}>()

const { t } = useI18n()
const toast = useToast()
const proxyStore = useProxyStore()

// State
const showInlineForm = ref(false)
const inlineLoading = ref(false)
const inputMode = ref<'string' | 'form'>('string')
const proxyString = ref('')
const newProxy = ref({
  type: 'socks5' as 'socks5' | 'socks4' | 'http' | 'https',
  host: '',
  port: '',
  username: '',
  password: ''
})

const proxyTypes = [
  { label: 'SOCKS5', value: 'socks5' },
  { label: 'SOCKS4', value: 'socks4' },
  { label: 'HTTP', value: 'http' },
  { label: 'HTTPS', value: 'https' }
]

// Computed
const proxies = computed(() => {
  return props.onlyWorking ? proxyStore.workingProxies : proxyStore.proxies
})

const selectedProxy = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const hasValidForm = computed(() => {
  return newProxy.value.host.trim() && newProxy.value.port.trim()
})

// Methods
function toggleInlineForm() {
  showInlineForm.value = !showInlineForm.value
  if (!showInlineForm.value) {
    resetForm()
  }
}

function resetForm() {
  proxyString.value = ''
  newProxy.value = {
    type: 'socks5',
    host: '',
    port: '',
    username: '',
    password: ''
  }
}

async function createProxyFromString() {
  if (!proxyString.value.trim()) return

  inlineLoading.value = true
  try {
    const created = await proxyStore.createFromString(proxyString.value.trim())
    if (created) {
      // Check the proxy
      await proxyStore.checkProxy(created.id)
      const proxy = proxyStore.getById(created.id)

      if (proxy?.status === 'working') {
        selectedProxy.value = created.id
        emit('proxy-created', created.id)
        toast.add({
          severity: 'success',
          summary: t('proxy.created'),
          detail: `${proxy.host}:${proxy.port}`,
          life: 3000
        })
        showInlineForm.value = false
        resetForm()
      } else {
        toast.add({
          severity: 'warn',
          summary: t('proxy.notWorking'),
          detail: t('proxy.checkFailed'),
          life: 5000
        })
      }
    }
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.createFailed'),
      life: 5000
    })
  } finally {
    inlineLoading.value = false
  }
}

async function createProxyFromForm() {
  if (!hasValidForm.value) return

  inlineLoading.value = true
  try {
    const created = await proxyStore.createProxy({
      type: newProxy.value.type,
      host: newProxy.value.host.trim(),
      port: parseInt(newProxy.value.port.trim(), 10),
      username: newProxy.value.username.trim() || undefined,
      password: newProxy.value.password.trim() || undefined
    })

    if (created) {
      // Check the proxy
      await proxyStore.checkProxy(created.id)
      const proxy = proxyStore.getById(created.id)

      if (proxy?.status === 'working') {
        selectedProxy.value = created.id
        emit('proxy-created', created.id)
        toast.add({
          severity: 'success',
          summary: t('proxy.created'),
          detail: `${proxy.host}:${proxy.port}`,
          life: 3000
        })
        showInlineForm.value = false
        resetForm()
      } else {
        toast.add({
          severity: 'warn',
          summary: t('proxy.notWorking'),
          detail: t('proxy.checkFailed'),
          life: 5000
        })
      }
    }
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.message || t('proxy.createFailed'),
      life: 5000
    })
  } finally {
    inlineLoading.value = false
  }
}
</script>

<template>
  <div class="proxy-select-field">
    <!-- Toggle Button for Inline Form -->
    <div v-if="showInlineCreate" class="inline-toggle">
      <Button
        :label="showInlineForm ? t('accounts.importDialog.selectExisting') : t('accounts.importDialog.addNewProxy')"
        :icon="showInlineForm ? 'pi pi-list' : 'pi pi-plus'"
        severity="secondary"
        text
        size="small"
        @click="toggleInlineForm"
      />
    </div>

    <!-- Inline Proxy Form -->
    <div v-if="showInlineForm" class="inline-proxy-form">
      <!-- Input Mode Tabs -->
      <div class="input-mode-tabs">
        <Button
          :label="t('accounts.importDialog.proxyString')"
          :severity="inputMode === 'string' ? 'primary' : 'secondary'"
          :text="inputMode !== 'string'"
          size="small"
          @click="inputMode = 'string'"
        />
        <Button
          :label="t('accounts.importDialog.proxyForm')"
          :severity="inputMode === 'form' ? 'primary' : 'secondary'"
          :text="inputMode !== 'form'"
          size="small"
          @click="inputMode = 'form'"
        />
      </div>

      <!-- String Input Mode -->
      <div v-if="inputMode === 'string'" class="string-input-mode">
        <InputText
          v-model="proxyString"
          :placeholder="t('accounts.importDialog.proxyStringPlaceholder')"
          class="w-full font-mono"
          :disabled="inlineLoading"
        />
        <small class="input-hint">
          {{ t('accounts.importDialog.proxyStringHint') }}
        </small>
        <Button
          :label="t('accounts.importDialog.addAndCheck')"
          icon="pi pi-check"
          :loading="inlineLoading"
          :disabled="!proxyString.trim()"
          @click="createProxyFromString"
          class="w-full mt-2"
          size="small"
        />
      </div>

      <!-- Form Input Mode -->
      <div v-else class="form-input-mode">
        <div class="proxy-form-row">
          <div class="proxy-form-field type-field">
            <label class="form-label-small">{{ t('proxy.addDialog.type') }}</label>
            <Select
              v-model="newProxy.type"
              :options="proxyTypes"
              optionLabel="label"
              optionValue="value"
              class="w-full"
              :disabled="inlineLoading"
            />
          </div>
          <div class="proxy-form-field host-field">
            <label class="form-label-small">{{ t('proxy.addDialog.host') }}</label>
            <InputText
              v-model="newProxy.host"
              placeholder="127.0.0.1"
              class="w-full"
              :disabled="inlineLoading"
            />
          </div>
          <div class="proxy-form-field port-field">
            <label class="form-label-small">{{ t('proxy.addDialog.port') }}</label>
            <InputText
              v-model="newProxy.port"
              placeholder="1080"
              class="w-full"
              :disabled="inlineLoading"
            />
          </div>
        </div>
        <div class="proxy-form-row">
          <div class="proxy-form-field">
            <label class="form-label-small">{{ t('proxy.addDialog.username') }} ({{ t('common.optional') }})</label>
            <InputText
              v-model="newProxy.username"
              :placeholder="t('proxy.addDialog.username')"
              class="w-full"
              :disabled="inlineLoading"
            />
          </div>
          <div class="proxy-form-field">
            <label class="form-label-small">{{ t('proxy.addDialog.password') }} ({{ t('common.optional') }})</label>
            <InputText
              v-model="newProxy.password"
              type="password"
              :placeholder="t('proxy.addDialog.password')"
              class="w-full"
              :disabled="inlineLoading"
            />
          </div>
        </div>
        <Button
          :label="t('accounts.importDialog.addAndCheck')"
          icon="pi pi-check"
          :loading="inlineLoading"
          :disabled="!hasValidForm"
          @click="createProxyFromForm"
          class="w-full mt-2"
          size="small"
        />
      </div>
    </div>

    <!-- Proxy Dropdown -->
    <Select
      v-if="!showInlineForm"
      v-model="selectedProxy"
      :options="proxies"
      optionLabel="host"
      optionValue="id"
      :placeholder="t('accounts.importDialog.selectProxy')"
      class="w-full"
      :class="{ 'p-invalid': invalid }"
      :disabled="disabled"
      :aria-label="t('accounts.importDialog.selectProxy')"
    >
      <template #value="{ value }">
        <span v-if="value">
          {{ proxyStore.getById(value)?.host }}:{{ proxyStore.getById(value)?.port }}
        </span>
        <span v-else class="placeholder-text">{{ t('accounts.importDialog.selectProxy') }}</span>
      </template>
      <template #option="{ option }">
        <div class="proxy-option">
          <span>{{ option.host }}:{{ option.port }}</span>
          <span class="proxy-type-badge">{{ option.type }}</span>
        </div>
      </template>
    </Select>

    <small v-if="!showInlineForm && proxies.length === 0" class="no-proxy-warning">
      {{ t('accounts.importDialog.noWorkingProxies') }}
    </small>

    <small v-if="required && !selectedProxy && !showInlineForm" class="required-hint">
      {{ t('accounts.importDialog.proxyRequired') }}
    </small>
  </div>
</template>

<style scoped>
.proxy-select-field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.inline-toggle {
  display: flex;
  justify-content: flex-end;
}

.inline-proxy-form {
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 1rem;
}

.input-mode-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.input-hint {
  display: block;
  color: var(--color-text-muted);
  font-size: 0.75rem;
  margin-top: 0.25rem;
}

.proxy-form-row {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.proxy-form-field {
  flex: 1;
}

.proxy-form-field.type-field {
  flex: 0 0 100px;
}

.proxy-form-field.port-field {
  flex: 0 0 80px;
}

.form-label-small {
  display: block;
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  margin-bottom: 0.25rem;
}

.proxy-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.proxy-type-badge {
  font-size: 0.7rem;
  padding: 0.125rem 0.375rem;
  background: var(--color-bg-surface);
  border-radius: 4px;
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.placeholder-text {
  color: var(--color-text-muted);
}

.no-proxy-warning,
.required-hint {
  color: var(--p-orange-400);
  font-size: 0.75rem;
}
</style>
