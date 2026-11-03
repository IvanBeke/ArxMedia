<template>
  <dialog
    ref="dialogRef"
    closedby="any"
    class="app-dialog w-full max-w-lg rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
    :aria-labelledby="titleId"
    @click="onDialogClick"
  >
    <div class="p-5 md:p-6">
      <div class="mb-4 flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 :id="titleId" class="text-lg font-display text-primary font-semibold">{{ heading }}</h2>
          <p class="text-xs text-muted mt-1 truncate">{{ title }}</p>
        </div>
        <button type="button" class="text-muted hover:text-primary" :aria-label="t('common_cancel')" @click="close">
          <X class="w-5 h-5" aria-hidden="true" />
        </button>
      </div>
      <slot />
    </div>
  </dialog>
</template>

<script setup lang="ts">
import { ref, useId } from 'vue'
import { X } from '@lucide/vue'
import { closeOnDialogBackdropClick } from '@/composables/useDialogLightDismiss'
import { useI18n } from '@/i18n'

defineProps<{ heading: string; title: string }>()

const { t } = useI18n()
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
