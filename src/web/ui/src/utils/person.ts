import { temporalYear } from '@/utils/temporal'
import type { MediaType, PersonCombinedCredits, PersonCredit } from '@/types/api'

export type PersonMediaFilter = 'all' | MediaType

export interface YearGroup {
  year: number | null
  label: string
  items: PersonCredit[]
}

export function genderLabel(gender: number | null | undefined): string {
  if (gender === 1) return 'Female'
  if (gender === 2) return 'Male'
  if (gender === 3) return 'Non-binary'
  return '—'
}

function parseDateParts(value: string | null | undefined): { year: number; month: number; day: number } | null {
  if (!value) return null
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null
  if (month < 1 || month > 12 || day < 1 || day > 31) return null
  return { year, month, day }
}

export function ageFor(birthday: string | null | undefined, endDate?: string | null | Date): number | null {
  const birth = parseDateParts(birthday)
  if (!birth) return null
  const end = endDate instanceof Date
    ? { year: endDate.getFullYear(), month: endDate.getMonth() + 1, day: endDate.getDate() }
    : (parseDateParts(endDate ?? null) ?? (() => {
      const now = new Date()
      return { year: now.getFullYear(), month: now.getMonth() + 1, day: now.getDate() }
    })())
  let age = end.year - birth.year
  if (end.month < birth.month || (end.month === birth.month && end.day < birth.day)) {
    age -= 1
  }
  return age >= 0 ? age : null
}

// Person filmography is dated by the credit, not the media's release or first-air date.
function creditDate(item: PersonCredit): string | null {
  return item.first_credit_air_date || item.release_date || item.first_air_date || null
}

function creditTime(item: PersonCredit): number {
  const value = creditDate(item)
  if (!value) return Number.NEGATIVE_INFINITY
  const time = Date.parse(value)
  return Number.isFinite(time) ? time : Number.NEGATIVE_INFINITY
}

export function creditYear(item: PersonCredit): number | null {
  return temporalYear(creditDate(item))
}

export function creditTitle(item: PersonCredit): string {
  return item.title || item.name || 'Untitled'
}

export function creditRole(item: PersonCredit): string {
  return (item.character || item.job || '').trim()
}

export function creditDetailLink(item: PersonCredit): string {
  if (item.media_type === 'tv') return `/tv/${item.id}`
  return `/movies/${item.id}`
}

export function sortByPopularity(items: PersonCredit[]): PersonCredit[] {
  return [...items].sort((a, b) => (b.popularity ?? b.vote_average ?? 0) - (a.popularity ?? a.vote_average ?? 0))
}

export function truncateAtWord(value: string, maxLength: number): string {
  const trimmed = value.trim()
  if (trimmed.length <= maxLength) return trimmed
  const slice = trimmed.slice(0, maxLength)
  const lastSpace = slice.lastIndexOf(' ')
  if (lastSpace <= 0) return `${slice.trimEnd()}…`
  return `${slice.slice(0, lastSpace).trimEnd()}…`
}

function creditKey(item: PersonCredit): string {
  return `${item.media_type}-${item.id}`
}

function popularityOf(item: PersonCredit): number {
  return item.popularity ?? item.vote_average ?? 0
}

export function dedupeCredits(items: PersonCredit[]): PersonCredit[] {
  const best = new Map<string, PersonCredit>()
  for (const item of items) {
    const existing = best.get(creditKey(item))
    if (!existing || popularityOf(item) > popularityOf(existing)) {
      best.set(creditKey(item), item)
    }
  }
  return [...best.values()]
}

export function isSelfCredit(item: PersonCredit): boolean {
  const character = (item.character || '').trim().toLowerCase()
  if (!character) return false
  const head = (character.split(' - ')[0] ?? '').split(' (')[0]?.trim() ?? ''
  return head === 'self'
}

export function topKnownFor(cast: PersonCredit[], count = 8): PersonCredit[] {
  const deduped = dedupeCredits(cast)
  const scripted = sortByPopularity(deduped.filter((item) => !isSelfCredit(item)))
  if (scripted.length >= count) return scripted.slice(0, count)
  const cameos = sortByPopularity(deduped.filter((item) => isSelfCredit(item)))
  return [...scripted, ...cameos].slice(0, count)
}

export function knownCreditsCount(credits: PersonCombinedCredits | null): number {
  if (!credits) return 0
  return (credits.cast?.length ?? 0) + (credits.crew?.length ?? 0)
}

export function filterByMedia(items: PersonCredit[], filter: PersonMediaFilter): PersonCredit[] {
  if (filter === 'all') return items
  return items.filter((item) => item.media_type === filter)
}

export function groupCreditsByYear(items: PersonCredit[]): YearGroup[] {
  const byYear = new Map<number | null, PersonCredit[]>()
  for (const item of items) {
    const year = creditYear(item)
    const bucket = byYear.get(year) ?? []
    bucket.push(item)
    byYear.set(year, bucket)
  }
  const groups: YearGroup[] = [...byYear.entries()].map(([year, yearItems]) => ({
    year,
    label: year === null ? '—' : String(year),
    items: yearItems
      .map((item, index) => ({ item, index }))
      .sort((a, b) => {
        const aTime = creditTime(a.item)
        const bTime = creditTime(b.item)
        if (aTime === bTime) return a.index - b.index
        return bTime - aTime
      })
      .map(({ item }) => item),
  }))
  groups.sort((a, b) => (b.year ?? Number.MIN_SAFE_INTEGER) - (a.year ?? Number.MIN_SAFE_INTEGER))
  return groups
}
