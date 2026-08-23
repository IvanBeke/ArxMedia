export function tmdbImageUrl(path, size = 'w500') {
  if (!path) {
    return null
  }
  return `https://image.tmdb.org/t/p/${size}${path}`
}
