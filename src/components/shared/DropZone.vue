<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = withDefaults(defineProps<{
  accept?: string
  multiple?: boolean
  disabled?: boolean
  title?: string
  hint?: string
  formats?: string[]
}>(), {
  accept: '*',
  multiple: true,
  disabled: false,
  formats: () => []
})

const emit = defineEmits<{
  'files-selected': [files: File[]]
  'dragover': [event: DragEvent]
  'dragleave': [event: DragEvent]
}>()

const { t } = useI18n()
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const displayTitle = computed(() => props.title || t('accounts.dropZone.dropTitle'))
const displayHint = computed(() => props.hint || t('accounts.dropZone.dropHint'))
const ariaLabel = computed(() => `${displayTitle.value}. ${displayHint.value}`)

function handleDragEnter(event: DragEvent) {
  if (props.disabled) return
  event.preventDefault()
  isDragging.value = true
}

function handleDragOver(event: DragEvent) {
  if (props.disabled) return
  event.preventDefault()
  isDragging.value = true
  emit('dragover', event)
}

function handleDragLeave(event: DragEvent) {
  if (props.disabled) return
  event.preventDefault()
  isDragging.value = false
  emit('dragleave', event)
}

function handleDrop(event: DragEvent) {
  if (props.disabled) return
  event.preventDefault()
  isDragging.value = false

  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    processFiles(Array.from(files))
  }
}

function handleClick() {
  if (props.disabled) return
  fileInput.value?.click()
}

function handleKeyDown(event: KeyboardEvent) {
  if (props.disabled) return
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    fileInput.value?.click()
  }
}

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    processFiles(Array.from(input.files))
    // Reset input to allow selecting same file again
    input.value = ''
  }
}

function processFiles(files: File[]) {
  // Filter files by accept pattern if specified
  let filteredFiles = files

  if (props.accept !== '*') {
    const acceptPatterns = props.accept.split(',').map(p => p.trim().toLowerCase())
    filteredFiles = files.filter(file => {
      const fileName = file.name.toLowerCase()
      const fileType = file.type.toLowerCase()

      return acceptPatterns.some(pattern => {
        if (pattern.startsWith('.')) {
          // Extension pattern
          return fileName.endsWith(pattern)
        } else if (pattern.includes('*')) {
          // Wildcard pattern (e.g., image/*)
          const regex = new RegExp('^' + pattern.replace('*', '.*') + '$')
          return regex.test(fileType)
        } else {
          // Exact type
          return fileType === pattern
        }
      })
    })
  }

  if (filteredFiles.length > 0) {
    emit('files-selected', props.multiple ? filteredFiles : [filteredFiles[0]])
  }
}

// Expose methods for parent components
defineExpose({
  open: () => fileInput.value?.click()
})
</script>

<template>
  <div
    class="drop-zone"
    :class="{
      'drop-zone-active': isDragging,
      'drop-zone-disabled': disabled
    }"
    role="button"
    :tabindex="disabled ? -1 : 0"
    :aria-label="ariaLabel"
    :aria-disabled="disabled"
    @dragenter="handleDragEnter"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
    @click="handleClick"
    @keydown="handleKeyDown"
  >
    <div class="drop-zone-content">
      <slot name="icon">
        <i class="pi pi-cloud-upload drop-zone-icon"></i>
      </slot>

      <slot name="title">
        <p class="drop-zone-title">{{ displayTitle }}</p>
      </slot>

      <slot name="hint">
        <p class="drop-zone-hint">{{ displayHint }}</p>
      </slot>

      <slot name="formats">
        <div v-if="formats.length > 0" class="drop-zone-formats">
          <span
            v-for="format in formats"
            :key="format"
            class="format-badge"
          >
            {{ format }}
          </span>
        </div>
      </slot>

      <slot></slot>
    </div>

    <input
      ref="fileInput"
      type="file"
      :accept="accept"
      :multiple="multiple"
      class="hidden-input"
      :aria-hidden="true"
      tabindex="-1"
      @change="handleFileSelect"
    />
  </div>
</template>

<style scoped>
.drop-zone {
  border: 2px dashed var(--color-border);
  border-radius: 12px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--color-bg-surface);
  position: relative;
}

.drop-zone:hover:not(.drop-zone-disabled) {
  border-color: var(--color-primary);
  background: var(--color-bg-elevated);
}

.drop-zone:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.2);
}

.drop-zone:focus:not(:focus-visible) {
  box-shadow: none;
}

.drop-zone:focus-visible {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.3);
}

.drop-zone-active {
  border-color: var(--color-primary);
  background: rgba(168, 85, 247, 0.1);
}

.drop-zone-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.drop-zone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.drop-zone-icon {
  font-size: 2.5rem;
  color: var(--color-text-muted);
  margin-bottom: 0.5rem;
}

.drop-zone-active .drop-zone-icon {
  color: var(--color-primary);
}

.drop-zone-title {
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.drop-zone-hint {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  margin: 0;
}

.drop-zone-formats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin-top: 0.5rem;
}

.format-badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  background: var(--color-bg-elevated);
  border-radius: 4px;
  color: var(--color-text-secondary);
  font-family: monospace;
}

.hidden-input {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
