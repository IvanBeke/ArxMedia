import type { Person } from '@/types/api'

function cleanValues(values: (string | null | undefined)[]): string[] {
  return values
    .map((value) => (typeof value === 'string' ? value.trim() : ''))
    .filter((value) => value.length > 0)
}

/**
 * Display line for a cast/crew card subtitle.
 *
 * Flat credits (movie, episode) carry `character`/`job` directly.
 * Aggregate credits (TV show, season) nest them in `roles[]`/`jobs[]`.
 * Multiple entries are comma-joined.
 */
export function creditLine(person: Person): string {
  const roles = Array.isArray(person.roles)
    ? cleanValues(person.roles.map((role) => role?.character))
    : []
  if (roles.length > 0) {
    return roles.join(', ')
  }

  const jobs = Array.isArray(person.jobs)
    ? cleanValues(person.jobs.map((job) => job?.job))
    : []
  if (jobs.length > 0) {
    return jobs.join(', ')
  }

  const flat = cleanValues([person.character, person.job])
  return flat[0] || ''
}
