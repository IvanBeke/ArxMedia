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

<script setup lang="ts">
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'
import { useUnwatchConfirm } from '@/composables/useUnwatchConfirm'
type EpisodeTarget = { tmdbId: string | number; seasonNumber: string | number; episodeNumber: string | number }

const emit = defineEmits<{ unwatched: [episode: EpisodeTarget] }>()

const { unmark } = useEpisodeWatchActions()

const { confirmDialog, removing, open, onConfirm } = useUnwatchConfirm({
  emit,
  perform: (target) => unmark(target),
})

defineExpose({ open })
</script>
