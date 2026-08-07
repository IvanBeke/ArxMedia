<template>
  <div v-if="open" class="fixed inset-0 z-[140] flex items-center justify-center p-4">
    <button
      type="button"
      class="absolute inset-0 bg-black/50"
      aria-label="Close date time picker"
      @click="onCancel"
    ></button>

    <div class="relative w-full max-w-sm rounded-lg border border-surface-200 bg-surface p-4 shadow-xl">
      <h3 class="text-primary text-sm font-semibold mb-3">{{ title }}</h3>
      <label class="block text-xs text-muted mb-1" for="watched-datetime-input">Watched at</label>
      <input
        id="watched-datetime-input"
        v-model="localValue"
        type="datetime-local"
        class="input"
      />

      <div class="mt-4 flex items-center justify-end gap-2">
        <button type="button" class="btn-ghost text-sm" @click="setNow">Now</button>
        <button type="button" class="btn-ghost text-sm" @click="onCancel">Cancel</button>
        <button type="button" class="btn-primary text-sm" :disabled="!localValue" @click="onConfirm">Save</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: 'Select watched date and time' },
  initialValue: { type: String, default: '' },
})

const emit = defineEmits(['confirm', 'cancel'])
const localValue = ref('')

function toLocalDateTimeInput(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hour}:${minute}`
}

function setNow() {
  localValue.value = toLocalDateTimeInput(new Date().toISOString())
}

function onConfirm() {
  if (!localValue.value) return
  const date = new Date(localValue.value)
  if (Number.isNaN(date.getTime())) return
  emit('confirm', date.toISOString())
}

function onCancel() {
  emit('cancel')
}

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    localValue.value = toLocalDateTimeInput(props.initialValue)
    if (!localValue.value) {
      setNow()
    }
  }
)
</script>
