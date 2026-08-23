<template>
  <ConfirmDialog
    ref="confirmDialog"
    title="Remove this episode from history?"
    message="This will remove this episode from your watched history."
    confirm-label="Unwatch"
    cancel-label="Keep watched"
    loading-label="Unwatching..."
    :loading="removing"
    @confirm="onConfirm"
  />
</template>

<script setup>
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'
import { useUnwatchConfirm } from '@/composables/useUnwatchConfirm'

const emit = defineEmits(['unwatched'])

const { unmark } = useEpisodeWatchActions()

const { confirmDialog, removing, open, onConfirm } = useUnwatchConfirm({
  emit,
  perform: (target) => unmark(target),
})

defineExpose({ open })
</script>
