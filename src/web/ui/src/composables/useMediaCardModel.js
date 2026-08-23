import { computed, unref } from 'vue'
import { MEDIA_TYPE, WATCH_ENTRY_MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { formatDateByLocale } from '@/i18n'
import { temporalYear } from '@/utils/temporal'
import { tmdbImageUrl } from '@/utils/images'

function resolvePosterUrl(item) {
  const path = item?.poster_url || item?.poster_path
  if (!path) return null
  if (String(path).startsWith('http')) return path
  return tmdbImageUrl(path, 'w342')
}

function normalizeStatus(status, watched) {
  if (status && status !== WATCH_ENTRY_STATUS.NONE) return status
  return watched ? WATCH_ENTRY_STATUS.WATCHED : WATCH_ENTRY_STATUS.NONE
}

function resolveMediaType(item, mediaType) {
  if (mediaType) return mediaType
  if (item?.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE || item?.media_type === MEDIA_TYPE.TV) return MEDIA_TYPE.TV
  return MEDIA_TYPE.MOVIE
}

export function useMediaCardModel(context, entrySource, optionsSource = {}) {
  const model = computed(() => {
    const item = unref(typeof entrySource === 'function' ? entrySource() : entrySource) || {}
    const rawOptions = typeof optionsSource === 'function' ? optionsSource() : optionsSource
    const options = unref(rawOptions) || {}

    const itemMediaType = resolveMediaType(item, options.mediaType)
    const isEpisode = item.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE

    const title = isEpisode
      ? (item.show_title || item.show_name || item.episode_title || item.title || 'Episode')
      : (item.title || item.name || '')

    const subtitle = isEpisode
      ? (item.episode_title || (item.title && item.title !== title ? item.title : ''))
      : ''

    const tmdbId = item.tmdb_id || item.id
    const detailLink = itemMediaType === MEDIA_TYPE.TV ? `/tv/${tmdbId}` : `/movies/${tmdbId}`
    const episodeDetailLink = isEpisode
      ? `/tv/${item.tmdb_id}/season/${item.season_number}/episode/${item.episode_number}`
      : ''

    const rawReleaseDate = item.release_date || ''
    return {
      title,
      subtitle,
      titleTooltip: title,
      subtitleTooltip: subtitle,
      posterUrl: resolvePosterUrl(item),
      posterAlt: title,
      posterLinkTo: options.posterLinkTo || episodeDetailLink || detailLink,
      titleLinkTo: options.titleLinkTo || detailLink,
      subtitleLinkTo: options.subtitleLinkTo || detailLink,
      releaseDate: formatDateByLocale(rawReleaseDate),
      year: rawReleaseDate ? (temporalYear(rawReleaseDate) || '') : '',
      showMediaTypeBadge: options.showMediaTypeBadge ?? context === 'mixed',
      mediaType: itemMediaType,
      episodeCode: {
        visible: Boolean(isEpisode && item.season_number && item.episode_number),
        seasonNumber: item.season_number,
        episodeNumber: item.episode_number,
      },
      status: {
        value: normalizeStatus(options.status, options.watched),
        visible: normalizeStatus(options.status, options.watched) !== WATCH_ENTRY_STATUS.NONE,
      },
      userRating: item.rating ?? item.user_status?.rating,
      providerRating: item.vote_average,
      hasUserRating:
        (item.rating !== null && item.rating !== undefined) ||
        (item.user_status?.rating !== null && item.user_status?.rating !== undefined),
      actions: {
        watchlist: {
          visible: Boolean(options.showQuickAction),
          active: Boolean(options.quickActionActive),
          loading: Boolean(options.quickActionLoading),
          pulsing: Boolean(options.quickActionPulsing),
          ariaLabel: options.quickActionAriaLabel || 'Add to watchlist',
        },
        watchedMenu: {
          visible: Boolean(options.showWatchedQuickAction),
          loading: Boolean(options.watchedQuickActionLoading),
          pulsing: Boolean(options.watchedQuickActionPulsing),
          ariaLabel: options.watchedQuickActionAriaLabel || 'Mark as watched',
          releaseDate: item.release_date || '',
        },
      },
    }
  })

  return { model }
}
