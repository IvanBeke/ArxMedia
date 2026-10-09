<template>
  <ConfirmDialog
    ref="confirmDialog"
    :title="t('dialog_unwatch_movie_title')"
    :message="t('dialog_unwatch_movie_message')"
    :confirm-label="t('dialog_unwatch_episode_confirm')"
    :cancel-label="t('dialog_unwatch_episode_keep')"
    :loading-label="t('dialog_unwatch_episode_loading')"
    :loading="removing"
    @confirm="onConfirm"
  />
</template>

<script setup lang="ts">
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { useMediaCardQuickActions } from '@/composables/useMediaCardQuickActions'
import { useI18n } from '@/i18n'
import { useUnwatchConfirm } from '@/composables/useUnwatchConfirm'
import type { MediaResult } from '@/types/api'

const props = withDefaults(defineProps<{ onError?: (message: string) => void }>(), { onError: undefined })

const { t } = useI18n()

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
