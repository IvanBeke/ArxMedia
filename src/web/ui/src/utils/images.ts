export function tmdbImageUrl(path: string | null | undefined, size = 'w500'): string | null {
  if (!path) {
    return null
  }
  return `https://image.tmdb.org/t/p/${size}${path}`
}
