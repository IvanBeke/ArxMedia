<template>
  <dialog
    ref="dialogRef"
    closedby="any"
    class="app-dialog w-full max-w-md rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
    :aria-labelledby="titleId"
    @close="release"
    @click="onDialogClick"
  >
    <div class="p-6">
      <h2 :id="titleId" class="text-lg font-display text-primary font-semibold">{{ t('avatar_crop_title') }}</h2>
      <p class="mt-1 text-sm text-muted">{{ t('avatar_crop_hint') }}</p>

      <div
        ref="viewport"
        role="group"
        tabindex="0"
        :aria-label="t('avatar_crop_area_label')"
        class="relative mx-auto mt-4 aspect-square w-full max-w-xs cursor-grab touch-none select-none overflow-hidden rounded-lg bg-surface active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-brand-400"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerEnd"
        @pointercancel="onPointerEnd"
        @wheel.prevent="onWheel"
        @keydown="onKeydown"
      >
        <img
          v-if="imageUrl"
          :src="imageUrl"
          alt=""
          draggable="false"
          class="pointer-events-none absolute left-0 top-0 max-w-none"
          :style="imageStyle"
        />
        <div class="pointer-events-none absolute inset-0 rounded-full border-2 border-white/80 shadow-[0_0_0_999px_rgba(0,0,0,0.6)]"></div>
      </div>

      <label class="mt-4 flex items-center gap-3 text-xs text-gray-400">
        <span>{{ t('avatar_zoom') }}</span>
        <input v-model.number="zoom" type="range" min="1" :max="maxZoom" step="0.01" class="w-full accent-brand-500" />
      </label>

      <p v-if="error || exportError" role="alert" class="mt-3 text-sm text-red-400">{{ error || exportError }}</p>

      <div class="mt-5 flex gap-3">
        <button type="button" class="btn-ghost flex-1" @click="close">{{ t('common_cancel') }}</button>
        <button type="button" class="btn-primary flex-1 disabled:opacity-60" :disabled="saving" @click="save">
          {{ saving ? t('avatar_saving') : t('avatar_save') }}
        </button>
      </div>
    </div>
  </dialog>
</template>

<script setup lang="ts">
import { ref, useId } from 'vue'
import { useI18n } from '@/i18n'
import { useAvatarCrop } from '@/composables/useAvatarCrop'
import { closeOnDialogBackdropClick } from '@/composables/useDialogLightDismiss'

defineProps<{ saving: boolean; error: string }>()
const emit = defineEmits<{ save: [blob: Blob] }>()

const { t } = useI18n()
const titleId = useId()
const dialogRef = ref<HTMLDialogElement | null>(null)
const exportError = ref('')
const {
  viewport, imageUrl, imageStyle, zoom, maxZoom, load, release, exportBlob,
  onPointerDown, onPointerMove, onPointerEnd, onWheel, onKeydown,
} = useAvatarCrop()

/** Rejects when the file cannot be decoded as an image; the dialog stays closed. */
async function open(file: File) {
  await load(file)
  exportError.value = ''
  dialogRef.value?.showModal()
}

function close() {
  if (dialogRef.value?.open) dialogRef.value.close()
}

async function save() {
  exportError.value = ''
  try {
    emit('save', await exportBlob())
  } catch {
    exportError.value = t('avatar_error_decode')
  }
}

function onDialogClick(event: MouseEvent) {
  closeOnDialogBackdropClick(event, dialogRef.value)
}

defineExpose({ open, close })
</script>
