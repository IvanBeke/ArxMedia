import { describe, expect, it } from 'vitest'
import { episodeExternalLinks, movieExternalLinks, seasonExternalLinks, showExternalLinks } from '@/utils/externalLinks'

describe('externalLinks', () => {
  it('builds movie links and hides tvmaze', () => {
    const links = movieExternalLinks(550, { imdb_id: 'tt0137523' })
    expect(links.tmdbUrl).toBe('https://www.themoviedb.org/movie/550')
    expect(links.tvmazeUrl).toBeNull()
    expect(links.imdbUrl).toBe('https://www.imdb.com/title/tt0137523/')
  })

  it('hides imdb link when id is missing or invalid', () => {
    expect(movieExternalLinks(550, {}).imdbUrl).toBeNull()
    expect(movieExternalLinks(550, { imdb_id: 'invalid' }).imdbUrl).toBeNull()
  })

  it('builds show links including tvmaze', () => {
    const links = showExternalLinks(1399, { tvmaze_id: 82, imdb_id: 'tt0944947' })
    expect(links.tmdbUrl).toBe('https://www.themoviedb.org/tv/1399')
    expect(links.tvmazeUrl).toBe('https://www.tvmaze.com/shows/82/-')
    expect(links.imdbUrl).toBe('https://www.imdb.com/title/tt0944947/')
  })

  it('builds season and episode tmdb links', () => {
    expect(seasonExternalLinks(1399, 1).tmdbUrl).toBe('https://www.themoviedb.org/tv/1399/season/1')
    expect(episodeExternalLinks(1399, 1, 2).tmdbUrl).toBe(
      'https://www.themoviedb.org/tv/1399/season/1/episode/2',
    )
  })
})
