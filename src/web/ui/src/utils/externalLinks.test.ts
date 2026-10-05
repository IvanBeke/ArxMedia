import { describe, expect, it } from 'vitest'
import { episodeExternalLinks, movieExternalLinks, personExternalLinks, seasonExternalLinks, showExternalLinks } from '@/utils/externalLinks'

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

  it('builds season tvmaze and imdb links with show fallback', () => {
    const own = seasonExternalLinks(1399, 2, { tvmaze_id: 500 }, { tvmaze_id: 82, imdb_id: 'tt0944947' })
    expect(own.tvmazeUrl).toBe('https://www.tvmaze.com/shows/500/-/episodes')
    expect(own.imdbUrl).toBe('https://www.imdb.com/title/tt0944947/episodes/?season=2')
    expect(seasonExternalLinks(1399, 2, {}, { tvmaze_id: 82 }).tvmazeUrl).toBe('https://www.tvmaze.com/shows/82/-/episodes')
    const none = seasonExternalLinks(1399, 2, null, { imdb_id: 'invalid' })
    expect(none.tvmazeUrl).toBeNull()
    expect(none.imdbUrl).toBeNull()
  })

  it('builds episode tvmaze and imdb links', () => {
    const links = episodeExternalLinks(1399, 1, 2, { tvmaze_id: 4953, imdb_id: 'tt1480055' })
    expect(links.tvmazeUrl).toBe('https://www.tvmaze.com/episodes/4953')
    expect(links.imdbUrl).toBe('https://www.imdb.com/title/tt1480055/')
    const none = episodeExternalLinks(1399, 1, 2, { tvmaze_id: 0, imdb_id: 'nm123' })
    expect(none.tvmazeUrl).toBeNull()
    expect(none.imdbUrl).toBeNull()
  })

  it('builds person links with imdb name url', () => {
    const links = personExternalLinks(123, { imdb_id: 'nm1234567' })
    expect(links.tmdbUrl).toBe('https://www.themoviedb.org/person/123')
    expect(links.tvmazeUrl).toBeNull()
    expect(links.imdbUrl).toBe('https://www.imdb.com/name/nm1234567/')
  })

  it('hides person imdb link when id is missing or invalid', () => {
    expect(personExternalLinks(123, {}).imdbUrl).toBeNull()
    expect(personExternalLinks(123, { imdb_id: 'invalid' }).imdbUrl).toBeNull()
  })
})
