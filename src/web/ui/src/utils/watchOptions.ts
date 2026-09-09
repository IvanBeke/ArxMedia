import { formatDateTimeByLocale } from '@/i18n'
import { EPOCH_START_ISO, plainDateToUserInstantIso } from '@/utils/temporal'
import type { MessageKey } from '@/i18n'

export type WatchedAtOption = 'now' | 'release' | 'unknown' | 'date'

type Translate = (key: MessageKey) => string

interface WatchedAtContext {
  releaseDate?: string
  pickDateTime?: (() => Promise<string | null>) | null
}

interface WatchedAtResolution {
  cancelled: boolean
  watchedAt: string | null
  useReleaseDate: boolean
}

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
  const { releaseDate = '', pickDateTime = null } = context

  if (option === 'release') {
    return {
      cancelled: false,
      watchedAt: releaseDate ? plainDateToUserInstantIso(releaseDate) : null,
      useReleaseDate: true,
    }
  }

  if (option === 'unknown') {
    return { cancelled: false, watchedAt: EPOCH_START_ISO, useReleaseDate: false }
  }

  if (option === 'date') {
    if (typeof pickDateTime !== 'function') {
      return { cancelled: true, watchedAt: null, useReleaseDate: false }
    }
    const picked = await pickDateTime()
    if (!picked) {
      return { cancelled: true, watchedAt: null, useReleaseDate: false }
    }
    return { cancelled: false, watchedAt: picked, useReleaseDate: false }
  }

  return { cancelled: false, watchedAt: null, useReleaseDate: false }
}
