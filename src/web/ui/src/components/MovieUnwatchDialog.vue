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

<script setup>
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { useMediaCardQuickActions } from '@/composables/useMediaCardQuickActions'
import { useUnwatchConfirm } from '@/composables/useUnwatchConfirm'

const props = defineProps({
  onError: { type: Function, default: null },
})

const emit = defineEmits(['unwatched'])

function defaultOnError(message) {
  console.error(message)
}

const { handleRemoveWatched } = useMediaCardQuickActions({ onError: props.onError || defaultOnError })

const { confirmDialog, removing, open, onConfirm } = useUnwatchConfirm({
  emit,
  perform: (movieItem) => handleRemoveWatched(movieItem, MEDIA_TYPE.MOVIE),
})

defineExpose({ open })
</script>
