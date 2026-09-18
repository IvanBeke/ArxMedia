import { ref } from 'vue'
import { trackingAPI } from '@/api'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import { useI18n } from '@/i18n'
import type { WatchEntry } from '@/types/api'

export function getRemoveHistoryConfirmText(entry: WatchEntry): string {
  const { t } = useI18n()
  if (entry?.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE) {
    return t('remove_history_confirm_episode')
  }
  return t('remove_history_confirm_movie')
}

export function useHistoryDelete(options: {
  onDeleted: (entry: WatchEntry) => Promise<void> | void
}) {
  const deletingEntryId = ref<number | null>(null)

  async function deleteEntry(entry: WatchEntry): Promise<void> {
    if (deletingEntryId.value) return
    deletingEntryId.value = entry.id

    try {
      await trackingAPI.deleteHistory(entry.id)
      await options.onDeleted(entry)
    } catch (e) {
      console.error('Failed to delete history entry', e)
    } finally {
      deletingEntryId.value = null
    }
  }

  return { deletingEntryId, deleteEntry }
}
