<template>
  <ConfirmDialog
    ref="confirmDialog"
    title="Remove this movie from history?"
    message="This will remove the movie from your watched history."
    confirm-label="Unwatch"
    cancel-label="Keep watched"
    loading-label="Unwatching..."
    :loading="removing"
    @confirm="onConfirm"
  />
</template>

<script setup lang="ts">
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { useMediaCardQuickActions } from '@/composables/useMediaCardQuickActions'
import { useUnwatchConfirm } from '@/composables/useUnwatchConfirm'
import type { MediaResult } from '@/types/api'

const props = withDefaults(defineProps<{ onError?: (message: string) => void }>(), { onError: undefined })

const emit = defineEmits<{ unwatched: [movie: MediaResult] }>()

function defaultOnError(message: string) {
  console.error(message)
}

const { handleRemoveWatched } = useMediaCardQuickActions({ onError: props.onError ?? defaultOnError })

const { confirmDialog, removing, open, onConfirm } = useUnwatchConfirm({
  emit,
  perform: (movieItem) => handleRemoveWatched(movieItem, MEDIA_TYPE.MOVIE),
})

defineExpose({ open })
</script>
