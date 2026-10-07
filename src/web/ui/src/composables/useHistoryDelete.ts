import { ref } from 'vue'
import { trackingAPI } from '@/api'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import { useI18n } from '@/i18n'
import type { WatchEntry } from '@/types/api'
import { getApiErrorMessage } from '@/utils/errors'

export function getRemoveHistoryConfirmText(entry: WatchEntry): string {
  const { t } = useI18n()
  if (entry?.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE) {
    return t('remove_history_confirm_episode')
  }
  return t('remove_history_confirm_movie')
}

export function useHistoryDelete(options: {
  onDeleted: (entry: WatchEntry) => Promise<void> | void
  onError?: (message: string) => void
}) {
  const deletingEntryId = ref<number | null>(null)

  async function deleteEntry(entry: WatchEntry): Promise<void> {
    if (deletingEntryId.value) return
    deletingEntryId.value = entry.id

    try {
      await trackingAPI.deleteHistory(entry.id)
      await options.onDeleted(entry)
    } catch (error: unknown) {
      options.onError?.(getApiErrorMessage(error, 'Could not remove this entry.'))
    } finally {
      deletingEntryId.value = null
    }
  }

  return { deletingEntryId, deleteEntry }
}
