type ErrorData = Record<string, unknown>

function isErrorData(value: unknown): value is ErrorData {
  return typeof value === 'object' && value !== null
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  const detail = isErrorData(error) ? error.detail : undefined
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0]
    if (typeof first === 'string' && first.trim()) return first
  }
  if (isErrorData(detail)) {
    const firstValue = Object.values(detail)[0]
    if (Array.isArray(firstValue) && firstValue.length && typeof firstValue[0] === 'string') {
      return firstValue[0]
    }
    if (typeof firstValue === 'string' && firstValue.trim()) {
      return firstValue
    }
  }
  if (isErrorData(error)) {
    const firstValue = Object.values(error)[0]
    if (Array.isArray(firstValue) && firstValue.length && typeof firstValue[0] === 'string') {
      return firstValue[0]
    }
  }
  const nonFieldErrors = isErrorData(error) ? error.non_field_errors : undefined
  if (Array.isArray(nonFieldErrors) && typeof nonFieldErrors[0] === 'string') {
    return nonFieldErrors[0]
  }
  return fallback
}
