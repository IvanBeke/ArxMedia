import { WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { formatDateTimeByLocale } from '@/i18n'

const RATEABLE_STATUSES = new Set([
  WATCH_ENTRY_STATUS.WATCHED,
  WATCH_ENTRY_STATUS.WATCHING,
  WATCH_ENTRY_STATUS.DROPPED,
])

export function canRateByStatus(status) {
  return RATEABLE_STATUSES.has(status)
}

export function formatUpdatedAtLabel(value) {
  if (!value) {
    return 'Unknown'
  }
  return formatDateTimeByLocale(value, { hour12: false }) || 'Unknown'
}
