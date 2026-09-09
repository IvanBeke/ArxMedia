import type { Temporal as TemporalPolyfill } from '@js-temporal/polyfill'

const ISO_DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/

export const EPOCH_START_ISO = '1970-01-01T00:00:00Z'

function hasTemporal() {
  return typeof globalThis.Temporal !== 'undefined'
}

function temporal(): typeof TemporalPolyfill {
  if (!globalThis.Temporal) {
    throw new Error('Temporal is unavailable. Call ensureTemporal() before using temporal utilities.')
  }
  return globalThis.Temporal
}

function pad2(value: number): string {
  return String(value).padStart(2, '0')
}

export function getUserTimeZone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
}

export async function ensureTemporal() {
  if (hasTemporal()) {
    return
  }
  const temporalModule = await import('@js-temporal/polyfill')
  globalThis.Temporal = temporalModule.Temporal
  if (!Date.prototype.toTemporalInstant && temporalModule.toTemporalInstant) {
    Date.prototype.toTemporalInstant = temporalModule.toTemporalInstant
  }
}

export function parsePlainDate(value: unknown): TemporalPolyfill.PlainDate | null {
  if (!value) {
    return null
  }
  try {
    return temporal().PlainDate.from(String(value))
  } catch {
    return null
  }
}

export function parseInstant(value: unknown): TemporalPolyfill.Instant | null {
  if (!value) {
    return null
  }
  if (ISO_DATE_ONLY_RE.test(String(value))) {
    return null
  }
  try {
    return temporal().Instant.from(String(value))
  } catch {
    return null
  }
}

export function toZonedDateTime(
  value: unknown,
  timeZone = getUserTimeZone(),
): TemporalPolyfill.ZonedDateTime | null {
  const instant = parseInstant(value)
  if (instant) {
    return instant.toZonedDateTimeISO(timeZone)
  }

  const plainDate = parsePlainDate(value)
  if (plainDate) {
    return plainDate.toZonedDateTime({ timeZone, plainTime: '00:00:00' })
  }

  return null
}

export function temporalYear(value: unknown): number | null {
  const plainDate = parsePlainDate(value)
  if (plainDate) {
    return plainDate.year
  }
  const zdt = toZonedDateTime(value)
  return zdt ? zdt.year : null
}

export function nowInstantIso(): string {
  return temporal().Now.instant().toString()
}

export function nowEpochMs(): number {
  return Number(temporal().Now.instant().epochMilliseconds)
}

export function instantEpochMs(value: unknown): number {
  const instant = parseInstant(value)
  if (!instant) {
    return Number.NaN
  }
  return Number(instant.epochMilliseconds)
}

export function instantFromEpochMs(value: number): string {
  if (!Number.isFinite(value)) {
    return ''
  }
  try {
    return temporal().Instant.fromEpochMilliseconds(Math.trunc(value)).toString()
  } catch {
    return ''
  }
}

export function isoDateKey(value: unknown, timeZone = getUserTimeZone()): string {
  const plainDate = parsePlainDate(value)
  if (plainDate) {
    return plainDate.toString()
  }
  const zdt = toZonedDateTime(value, timeZone)
  return zdt ? zdt.toPlainDate().toString() : ''
}

export function formatTemporalDate(
  value: unknown,
  locale: string | string[],
  options: Intl.DateTimeFormatOptions = {},
): string {
  const zdt = toZonedDateTime(value)
  if (!zdt) {
    return ''
  }
  return zdt.toLocaleString(locale, options)
}

export function formatTemporalDateTime(
  value: unknown,
  locale: string | string[],
  options: Intl.DateTimeFormatOptions = {},
): string {
  const zdt = toZonedDateTime(value)
  if (!zdt) {
    return ''
  }
  return zdt.toLocaleString(locale, options)
}

export function formatIsoAsDDMMYYYY(value: unknown): string {
  const zdt = toZonedDateTime(value)
  if (!zdt) {
    return ''
  }
  return `${pad2(zdt.day)}/${pad2(zdt.month)}/${zdt.year}`
}

export function formatIsoTimeHHMM(value: unknown, timeZone = getUserTimeZone()): string {
  const zdt = toZonedDateTime(value, timeZone)
  if (!zdt) {
    return ''
  }
  return `${pad2(zdt.hour)}:${pad2(zdt.minute)}`
}

export function toLocalDateTimeInput(value: unknown, timeZone = getUserTimeZone()): string {
  const zdt = toZonedDateTime(value, timeZone)
  if (!zdt) {
    return ''
  }
  return `${zdt.year}-${pad2(zdt.month)}-${pad2(zdt.day)}T${pad2(zdt.hour)}:${pad2(zdt.minute)}`
}

export function localDateTimeInputToIso(value: unknown, timeZone = getUserTimeZone()): string {
  if (!value) {
    return ''
  }
  try {
    const dateTime = temporal().PlainDateTime.from(String(value))
    return dateTime.toZonedDateTime(timeZone).toInstant().toString()
  } catch {
    return ''
  }
}

export function plainDateToUserInstantIso(value: unknown, timeZone = getUserTimeZone()): string {
  const instant = parseInstant(value)
  if (instant) {
    return instant.toString()
  }

  const plainDate = parsePlainDate(value)
  if (!plainDate) {
    return ''
  }
  try {
    return plainDate
      .toZonedDateTime({ timeZone, plainTime: '00:00:00' })
      .toInstant()
      .toString()
  } catch {
    return ''
  }
}

export function shiftIsoMonthStart(value: unknown, amount: number): TemporalPolyfill.PlainDate | null {
  const plainDate = parsePlainDate(value)
  if (!plainDate) {
    return null
  }
  return plainDate.with({ day: 1 }).add({ months: amount })
}

export function monthBounds(
  value: unknown,
): { start: TemporalPolyfill.PlainDate; end: TemporalPolyfill.PlainDate } | null {
  const plainDate = parsePlainDate(value)
  if (!plainDate) {
    return null
  }
  const start = plainDate.with({ day: 1 })
  const end = start.add({ months: 1 }).subtract({ days: 1 })
  return { start, end }
}

export function weekBounds(
  value: unknown,
): { start: TemporalPolyfill.PlainDate; end: TemporalPolyfill.PlainDate } | null {
  const plainDate = parsePlainDate(value)
  if (!plainDate) {
    return null
  }
  const start = plainDate.subtract({ days: plainDate.dayOfWeek - 1 })
  const end = start.add({ days: 6 })
  return { start, end }
}
