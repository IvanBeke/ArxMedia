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
): DetailExternalLinks {
  return {
    tmdbUrl: `https://www.themoviedb.org/tv/${tmdbId}/season/${seasonNumber}`,
    tvmazeUrl: null,
    imdbUrl: null,
  }
}

export function episodeExternalLinks(
  tmdbId: string | number,
  seasonNumber: string | number,
  episodeNumber: string | number,
): DetailExternalLinks {
  return {
    tmdbUrl: `https://www.themoviedb.org/tv/${tmdbId}/season/${seasonNumber}/episode/${episodeNumber}`,
    tvmazeUrl: null,
    imdbUrl: null,
  }
}

export function personExternalLinks(personId: string | number, ids?: ExternalIds | null): DetailExternalLinks {
  return {
    tmdbUrl: `https://www.themoviedb.org/person/${personId}`,
    tvmazeUrl: null,
    imdbUrl: imdbUrlFor(ids ?? null),
  }
}
