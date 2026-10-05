import type { ExternalIds } from '@/types/api'

export interface DetailExternalLinks {
  tmdbUrl: string | null
  tvmazeUrl: string | null
  imdbUrl: string | null
}

function tvmazeUrlFor(ids: ExternalIds | undefined | null): string | null {
  const raw = ids?.tvmaze_id
  const num = typeof raw === 'string' ? Number.parseInt(raw, 10) : raw
  if (typeof num === 'number' && Number.isFinite(num) && num > 0) {
    return `https://www.tvmaze.com/shows/${num}/-`
  }
  return null
}

function imdbUrlFor(ids: ExternalIds | undefined | null): string | null {
  const imdb = typeof ids?.imdb_id === 'string' ? ids.imdb_id : null
  if (imdb && /^tt\d+$/.test(imdb)) {
    return `https://www.imdb.com/title/${imdb}/`
  }
  if (imdb && /^nm\d+$/.test(imdb)) {
    return `https://www.imdb.com/name/${imdb}/`
  }
  return null
}

export function movieExternalLinks(tmdbId: string | number, ids?: ExternalIds | null): DetailExternalLinks {
  return {
    tmdbUrl: `https://www.themoviedb.org/movie/${tmdbId}`,
    tvmazeUrl: null,
    imdbUrl: imdbUrlFor(ids ?? null),
  }
}

export function showExternalLinks(tmdbId: string | number, ids?: ExternalIds | null): DetailExternalLinks {
  return {
    tmdbUrl: `https://www.themoviedb.org/tv/${tmdbId}`,
    tvmazeUrl: tvmazeUrlFor(ids ?? null),
    imdbUrl: imdbUrlFor(ids ?? null),
  }
}

export function seasonExternalLinks(
  tmdbId: string | number,
  seasonNumber: string | number,
  seasonIds?: ExternalIds | null,
  showIds?: ExternalIds | null,
): DetailExternalLinks {
  const tvmazeShow = tvmazeUrlFor(seasonIds ?? null) ?? tvmazeUrlFor(showIds ?? null)
  const showImdb = imdbUrlFor(showIds ?? null)
  return {
    tmdbUrl: `https://www.themoviedb.org/tv/${tmdbId}/season/${seasonNumber}`,
    tvmazeUrl: tvmazeShow ? `${tvmazeShow}/episodes` : null,
    imdbUrl: showImdb?.includes('/title/') ? `${showImdb}episodes/?season=${seasonNumber}` : null,
  }
}

export function episodeExternalLinks(
  tmdbId: string | number,
  seasonNumber: string | number,
  episodeNumber: string | number,
  ids?: ExternalIds | null,
): DetailExternalLinks {
  const raw = ids?.tvmaze_id
  const tvmazeId = typeof raw === 'string' ? Number.parseInt(raw, 10) : raw
  const imdb = imdbUrlFor(ids ?? null)
  return {
    tmdbUrl: `https://www.themoviedb.org/tv/${tmdbId}/season/${seasonNumber}/episode/${episodeNumber}`,
    tvmazeUrl: typeof tvmazeId === 'number' && Number.isFinite(tvmazeId) && tvmazeId > 0
      ? `https://www.tvmaze.com/episodes/${tvmazeId}`
      : null,
    imdbUrl: imdb?.includes('/title/') ? imdb : null,
  }
}

export function personExternalLinks(personId: string | number, ids?: ExternalIds | null): DetailExternalLinks {
  return {
    tmdbUrl: `https://www.themoviedb.org/person/${personId}`,
    tvmazeUrl: null,
    imdbUrl: imdbUrlFor(ids ?? null),
  }
}
