import { WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { formatDateTimeByLocale } from '@/i18n'
import type { WatchEntryStatus } from '@/types/tracking'

const RATEABLE_STATUSES = new Set<WatchEntryStatus>([
  WATCH_ENTRY_STATUS.WATCHED,
  WATCH_ENTRY_STATUS.WATCHING,
  WATCH_ENTRY_STATUS.DROPPED,
])

export function canRateByStatus(status: unknown): status is WatchEntryStatus {
  return typeof status === 'string' && RATEABLE_STATUSES.has(status as WatchEntryStatus)
}

export function formatUpdatedAtLabel(value: unknown): string {
  if (!value) {
    return 'Unknown'
  }
  return formatDateTimeByLocale(value, { hour12: false }) || 'Unknown'
}
