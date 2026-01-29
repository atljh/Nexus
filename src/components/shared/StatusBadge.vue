<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Tag from 'primevue/tag'

export type StatusType = 'account' | 'proxy' | 'task'
export type AccountStatus = 'unchecked' | 'checking' | 'valid' | 'invalid' | 'banned' | 'muted' | 'spamblock' | 'session_expired' | 'deactivated' | 'needs_reauth' | 'connection_failed'
export type ProxyStatus = 'unchecked' | 'working' | 'slow' | 'very_slow' | 'not_working' | 'timeout'
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused'

type TagSeverity = 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast' | undefined

const props = withDefaults(defineProps<{
  status: string
  type?: StatusType
  showIcon?: boolean
}>(), {
  type: 'account',
  showIcon: false
})

const { t, te } = useI18n()

const severity = computed<TagSeverity>(() => {
  if (props.type === 'account') {
    return getAccountSeverity(props.status)
  } else if (props.type === 'proxy') {
    return getProxySeverity(props.status)
  } else if (props.type === 'task') {
    return getTaskSeverity(props.status)
  }
  return 'secondary'
})

const label = computed(() => {
  const key = `${props.type === 'account' ? 'accounts' : props.type}.status.${props.status}`
  return te(key) ? t(key) : props.status
})

const icon = computed(() => {
  if (!props.showIcon) return undefined

  if (props.type === 'account') {
    switch (props.status) {
      case 'valid': return 'pi pi-check-circle'
      case 'invalid': return 'pi pi-times-circle'
      case 'banned': return 'pi pi-ban'
      case 'checking': return 'pi pi-spin pi-spinner'
      case 'spamblock': return 'pi pi-exclamation-triangle'
      case 'muted': return 'pi pi-volume-off'
      case 'session_expired': return 'pi pi-clock'
      case 'needs_reauth': return 'pi pi-key'
      case 'connection_failed': return 'pi pi-wifi'
      default: return 'pi pi-question-circle'
    }
  } else if (props.type === 'proxy') {
    switch (props.status) {
      case 'working': return 'pi pi-check-circle'
      case 'not_working': return 'pi pi-times-circle'
      case 'slow': return 'pi pi-exclamation-circle'
      case 'very_slow': return 'pi pi-exclamation-triangle'
      case 'timeout': return 'pi pi-clock'
      default: return 'pi pi-question-circle'
    }
  } else if (props.type === 'task') {
    switch (props.status) {
      case 'completed': return 'pi pi-check-circle'
      case 'running': return 'pi pi-spin pi-spinner'
      case 'failed': return 'pi pi-times-circle'
      case 'cancelled': return 'pi pi-ban'
      case 'paused': return 'pi pi-pause'
      default: return 'pi pi-clock'
    }
  }
  return undefined
})

const ariaLabel = computed(() => {
  return `${props.type} status: ${label.value}`
})

function getAccountSeverity(status: string): TagSeverity {
  switch (status) {
    case 'valid': return 'success'
    case 'invalid': return 'danger'
    case 'banned': return 'danger'
    case 'deactivated': return 'danger'
    case 'muted': return 'warn'
    case 'spamblock': return 'warn'
    case 'session_expired': return 'warn'
    case 'needs_reauth': return 'warn'
    case 'connection_failed': return 'warn'
    case 'checking': return 'info'
    default: return 'secondary'
  }
}

function getProxySeverity(status: string): TagSeverity {
  switch (status) {
    case 'working': return 'success'
    case 'not_working': return 'danger'
    case 'timeout': return 'danger'
    case 'slow': return 'warn'
    case 'very_slow': return 'warn'
    default: return 'secondary'
  }
}

function getTaskSeverity(status: string): TagSeverity {
  switch (status) {
    case 'completed': return 'success'
    case 'running': return 'info'
    case 'failed': return 'danger'
    case 'cancelled': return 'warn'
    case 'paused': return 'warn'
    default: return 'secondary'
  }
}
</script>

<template>
  <Tag
    :value="label"
    :severity="severity"
    :icon="icon"
    :aria-label="ariaLabel"
    role="status"
  />
</template>
