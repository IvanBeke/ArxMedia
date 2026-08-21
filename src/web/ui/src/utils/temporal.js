const ISO_DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/

function hasTemporal() {
  return typeof globalThis.Temporal !== 'undefined'
}

function pad2(value) {
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

export function parsePlainDate(value) {
  if (!value) {
    return null
  }
  try {
    return Temporal.PlainDate.from(String(value))
  } catch {
    return null
  }
}

export function parseInstant(value) {
  if (!value) {
    return null
  }
  if (ISO_DATE_ONLY_RE.test(String(value))) {
    return null
  }
  try {
    return Temporal.Instant.from(String(value))
  } catch {
    return null
  }
}

export function toZonedDateTime(value, timeZone = getUserTimeZone()) {
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

export function temporalYear(value) {
  const plainDate = parsePlainDate(value)
  if (plainDate) {
    return plainDate.year
  }
  const zdt = toZonedDateTime(value)
  return zdt ? zdt.year : null
}

export function nowInstantIso() {
  return Temporal.Now.instant().toString()
}

export function nowEpochMs() {
  return Number(Temporal.Now.instant().epochMilliseconds)
}

export function instantEpochMs(value) {
  const instant = parseInstant(value)
  if (!instant) {
    return Number.NaN
  }
  return Number(instant.epochMilliseconds)
}

export function instantFromEpochMs(value) {
  if (!Number.isFinite(value)) {
    return ''
  }
  try {
    return Temporal.Instant.fromEpochMilliseconds(Math.trunc(value)).toString()
  } catch {
    return ''
  }
}

export function isoDateKey(value, timeZone = getUserTimeZone()) {
  const plainDate = parsePlainDate(value)
  if (plainDate) {
    return plainDate.toString()
  }
  const zdt = toZonedDateTime(value, timeZone)
  return zdt ? zdt.toPlainDate().toString() : ''
}

export function formatTemporalDate(value, locale, options = {}) {
  const zdt = toZonedDateTime(value)
  if (!zdt) {
    return ''
  }
  return zdt.toLocaleString(locale, options)
}

export function formatTemporalDateTime(value, locale, options = {}) {
  const zdt = toZonedDateTime(value)
  if (!zdt) {
    return ''
  }
  return zdt.toLocaleString(locale, options)
}

export function formatIsoAsDDMMYYYY(value) {
  const zdt = toZonedDateTime(value)
  if (!zdt) {
    return ''
  }
  return `${pad2(zdt.day)}/${pad2(zdt.month)}/${zdt.year}`
}

export function formatIsoTimeHHMM(value, timeZone = getUserTimeZone()) {
  const zdt = toZonedDateTime(value, timeZone)
  if (!zdt) {
    return ''
  }
  return `${pad2(zdt.hour)}:${pad2(zdt.minute)}`
}

export function toLocalDateTimeInput(value, timeZone = getUserTimeZone()) {
  const zdt = toZonedDateTime(value, timeZone)
  if (!zdt) {
    return ''
  }
  return `${zdt.year}-${pad2(zdt.month)}-${pad2(zdt.day)}T${pad2(zdt.hour)}:${pad2(zdt.minute)}`
}

export function localDateTimeInputToIso(value, timeZone = getUserTimeZone()) {
  if (!value) {
    return ''
  }
  try {
    const dateTime = Temporal.PlainDateTime.from(String(value))
    return dateTime.toZonedDateTime(timeZone).toInstant().toString()
  } catch {
    return ''
  }
}

export function plainDateToUserInstantIso(value, timeZone = getUserTimeZone()) {
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

export function shiftIsoMonthStart(value, amount) {
  const plainDate = parsePlainDate(value)
  if (!plainDate) {
    return null
  }
  return plainDate.with({ day: 1 }).add({ months: amount })
}

export function monthBounds(value) {
  const plainDate = parsePlainDate(value)
  if (!plainDate) {
    return null
  }
  const start = plainDate.with({ day: 1 })
  const end = start.add({ months: 1 }).subtract({ days: 1 })
  return { start, end }
}

export function weekBounds(value) {
  const plainDate = parsePlainDate(value)
  if (!plainDate) {
    return null
  }
  const start = plainDate.subtract({ days: plainDate.dayOfWeek - 1 })
  const end = start.add({ days: 6 })
  return { start, end }
}
