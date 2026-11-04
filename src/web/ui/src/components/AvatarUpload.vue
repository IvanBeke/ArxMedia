<template>
  <div>
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
      <label
        class="flex flex-1 cursor-pointer items-center gap-4 rounded-lg border-2 border-dashed p-4 transition-colors focus-within:border-brand-500"
        :class="dragging ? 'border-brand-500 bg-brand-500/10' : 'border-surface-200 hover:border-surface-300'"
        @dragenter.prevent="dragging = true"
        @dragover.prevent="dragging = true"
        @dragleave="onDragLeave"
        @drop.prevent="onDrop"
      >
        <UserAvatar :username="username" :src="avatar" size="xl" />
        <span class="min-w-0">
          <span class="block text-sm text-primary">{{ dragging ? t('avatar_drop_active') : t('avatar_drop_prompt') }}</span>
          <span class="block text-xs text-gray-500">{{ t('avatar_formats_hint', { size: AVATAR_MAX_FILE_MB }) }}</span>
        </span>
        <input
          type="file"
          class="sr-only"
          :accept="AVATAR_ACCEPTED_TYPES.join(',')"
          :aria-label="t('avatar_choose')"
          @change="onFileChange"
        />
      </label>
      <button v-if="avatar" type="button" class="btn-ghost text-sm" :disabled="removing" @click="remove">
        {{ removing ? t('avatar_removing') : t('avatar_remove') }}
      </button>
    </div>
    <p v-if="error" role="alert" class="mt-2 text-sm text-red-400">{{ error }}</p>

    <AvatarCropDialog ref="cropDialog" :saving="uploading" :error="cropError" @save="upload" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { authAPI } from '@/api'
import AvatarCropDialog from '@/components/AvatarCropDialog.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import { useI18n } from '@/i18n'
import { AVATAR_ACCEPTED_TYPES, AVATAR_MAX_FILE_MB, avatarFileError } from '@/utils/avatarCrop'
import { getApiErrorMessage } from '@/utils/errors'
import type { User } from '@/types/api'

defineProps<{ username: string; avatar: string | null }>()
const emit = defineEmits<{ updated: [user: User] }>()

const { t } = useI18n()
const cropDialog = ref<InstanceType<typeof AvatarCropDialog> | null>(null)
const dragging = ref(false)
const uploading = ref(false)
const removing = ref(false)
const error = ref('')
const cropError = ref('')

async function handleFile(file: File) {
  error.value = ''
  cropError.value = ''
  const problem = avatarFileError(file)
  if (problem) {
    error.value = t(problem === 'type' ? 'avatar_error_type' : 'avatar_error_size', { size: AVATAR_MAX_FILE_MB })
    return
  }
  try {
    await cropDialog.value?.open(file)
  } catch {
    error.value = t('avatar_error_decode')
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file) void handleFile(file)
}

function onDragLeave(event: DragEvent) {
  if (!(event.currentTarget as HTMLElement).contains(event.relatedTarget as Node | null)) dragging.value = false
}

function onDrop(event: DragEvent) {
  dragging.value = false
  const file = event.dataTransfer?.files[0]
  if (file) void handleFile(file)
}

async function upload(blob: Blob) {
  uploading.value = true
  cropError.value = ''
  try {
    emit('updated', await authAPI.uploadAvatar(blob))
    cropDialog.value?.close()
  } catch (e: unknown) {
    cropError.value = getApiErrorMessage(e, t('avatar_upload_failed'))
  } finally {
    uploading.value = false
  }
}

async function remove() {
  removing.value = true
  error.value = ''
  try {
    emit('updated', await authAPI.removeAvatar())
  } catch (e: unknown) {
    error.value = getApiErrorMessage(e, t('avatar_remove_failed'))
  } finally {
    removing.value = false
  }
}
</script>
