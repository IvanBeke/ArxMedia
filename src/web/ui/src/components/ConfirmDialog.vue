<template>
  <dialog
    ref="dialogRef"
    closedby="any"
    class="app-dialog confirm-dialog w-full max-w-md rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
    :aria-labelledby="titleId"
    @click="onDialogClick"
  >
    <div class="p-6">
      <h2 :id="titleId" class="text-lg font-display text-primary font-semibold">{{ title }}</h2>
      <p v-if="message" class="mt-2 text-sm text-muted">{{ message }}</p>
      <div class="mt-5 flex gap-3">
        <button type="button" class="btn-ghost flex-1" @click="close">{{ cancelLabel }}</button>
        <button
          type="button"
          class="btn-ghost flex-1 cursor-pointer"
          :class="danger ? 'border-red-500/40 text-red-300 hover:bg-red-500/10' : ''"
          :disabled="loading"
          @click="$emit('confirm')"
        >
          {{ loading ? (loadingLabel || confirmLabel) : confirmLabel }}
        </button>
      </div>
    </div>
  </dialog>
</template>

<script setup lang="ts">
import { ref, useId } from 'vue'
import { closeOnDialogBackdropClick } from '@/composables/useDialogLightDismiss'

withDefaults(defineProps<{
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  loadingLabel?: string
  loading?: boolean
  danger?: boolean
}>(), {
  message: '', confirmLabel: 'Confirm', cancelLabel: 'Cancel', loadingLabel: '', loading: false, danger: true,
})

defineEmits<{ confirm: [] }>()

const dialogRef = ref<HTMLDialogElement | null>(null)
const titleId = useId()

function showModal() {
  dialogRef.value?.showModal()
}

function close() {
  if (dialogRef.value?.open) {
    dialogRef.value.close()
  }
}

function onDialogClick(event: MouseEvent) {
  closeOnDialogBackdropClick(event, dialogRef.value)
}

defineExpose({ showModal, close })
</script>
