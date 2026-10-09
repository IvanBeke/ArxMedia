<template>
  <ConfirmDialog
    ref="confirmDialog"
    :title="t('dialog_unwatch_episode_title')"
    :message="t('dialog_unwatch_episode_message')"
    :confirm-label="t('dialog_unwatch_episode_confirm')"
    :cancel-label="t('dialog_unwatch_episode_keep')"
    :loading-label="t('dialog_unwatch_episode_loading')"
    :loading="removing"
    @confirm="onConfirm"
  />
</template>

<script setup lang="ts">
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'
import { useI18n } from '@/i18n'
import { useUnwatchConfirm } from '@/composables/useUnwatchConfirm'
type EpisodeTarget = { tmdbId: string | number; seasonNumber: string | number; episodeNumber: string | number }

const props = withDefaults(defineProps<{ onError?: (message: string) => void }>(), { onError: undefined })
const { t } = useI18n()

const emit = defineEmits<{ unwatched: [episode: EpisodeTarget] }>()

const { unmark } = useEpisodeWatchActions(props.onError ? { onError: props.onError } : {})

const { confirmDialog, removing, open, onConfirm } = useUnwatchConfirm({
  emit,
  perform: (target) => unmark(target),
})

defineExpose({ open })
</script>
