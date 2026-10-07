import { formatDateTimeByLocale } from '@/i18n'
import type { MessageKey } from '@/i18n'

export type WatchedAtOption = 'now' | 'release' | 'unknown' | 'date'

type Translate = (key: MessageKey) => string

/** What the API accepts as `watched_at`: a token the backend resolves, or an ISO timestamp. */
export type WatchedAtValue = 'now' | 'unknown' | 'release_date' | (string & {})

interface WatchedAtContext {
  pickDateTime?: (() => Promise<string | null>) | null
}

interface WatchedAtResolution {
  cancelled: boolean
  watchedAt: WatchedAtValue | null
}

const OPTION_TOKENS: Partial<Record<string, WatchedAtValue>> = { release: 'release_date', unknown: 'unknown' }

export function watchedTooltipText(watched: boolean, watchedAtIso: unknown, t: Translate): string {
  if (!watched) {
    return t('tracking_mark_as_watched')
  }
  if (!watchedAtIso) {
    return t('tracking_watched')
  }
  const formatted = formatDateTimeByLocale(watchedAtIso)
  if (!formatted) {
    return t('tracking_watched')
  }
  return `${t('tracking_watched_on')} ${formatted}`
}

export async function resolveWatchedAtFromOption(
  option: WatchedAtOption | string,
  context: WatchedAtContext = {},
): Promise<WatchedAtResolution> {
  if (option === 'date') {
    const picked = typeof context.pickDateTime === 'function' ? await context.pickDateTime() : null
    return picked ? { cancelled: false, watchedAt: picked } : { cancelled: true, watchedAt: null }
  }
  return { cancelled: false, watchedAt: OPTION_TOKENS[option] ?? 'now' }
}
