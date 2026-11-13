<template>
  <div v-if="open" class="fixed inset-0 z-[140] flex items-center justify-center p-4">
    <button
      type="button"
      class="absolute inset-0 bg-black/50"
      :aria-label="t('picker_close')"
      @click="onCancel"
    ></button>

    <div class="relative w-full max-w-sm rounded-lg border border-surface-200 bg-surface p-4 shadow-xl">
      <h3 class="text-primary text-sm font-semibold mb-3">{{ title || t('picker_default_title') }}</h3>
      <label class="block text-xs text-muted mb-1" for="watched-datetime-input">{{ t('picker_watched_at') }}</label>
      <input
        id="watched-datetime-input"
        v-model="localValue"
        type="datetime-local"
        class="input"
      />

      <div class="mt-4 flex items-center justify-end gap-2">
        <button type="button" class="btn-ghost text-sm" @click="setNow">{{ t('picker_now') }}</button>
        <button type="button" class="btn-ghost text-sm" @click="onCancel">{{ t('common_cancel') }}</button>
        <button type="button" class="btn-primary text-sm" :disabled="!localValue" @click="onConfirm">{{ t('common_save') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from '@/i18n'
import { localDateTimeInputToIso, nowInstantIso, toLocalDateTimeInput } from '@/utils/temporal'

const props = withDefaults(defineProps<{
  open?: boolean
  title?: string
  initialValue?: string
}>(), {
  open: false, title: '', initialValue: '',
})

const { t } = useI18n()
const emit = defineEmits<{ confirm: [value: string]; cancel: [] }>()
const localValue = ref<string>('')

function setNow() {
  localValue.value = toLocalDateTimeInput(nowInstantIso())
}

function onConfirm() {
  if (!localValue.value) return
  const isoValue = localDateTimeInputToIso(localValue.value)
  if (!isoValue) return
  emit('confirm', isoValue)
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
