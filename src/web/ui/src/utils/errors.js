export function getApiErrorMessage(error, fallback) {
  if (typeof error?.detail === 'string' && error.detail.trim()) return error.detail
  if (Array.isArray(error?.detail) && error.detail.length) {
    const first = error.detail[0]
    if (typeof first === 'string' && first.trim()) return first
  }
  if (error?.detail && typeof error.detail === 'object') {
    const firstValue = Object.values(error.detail)[0]
    if (Array.isArray(firstValue) && firstValue.length && typeof firstValue[0] === 'string') {
      return firstValue[0]
    }
    if (typeof firstValue === 'string' && firstValue.trim()) {
      return firstValue
    }
  }
  if (error && typeof error === 'object') {
    const firstValue = Object.values(error)[0]
    if (Array.isArray(firstValue) && firstValue.length && typeof firstValue[0] === 'string') {
      return firstValue[0]
    }
  }
  if (Array.isArray(error?.non_field_errors) && error.non_field_errors.length) {
    return error.non_field_errors[0]
  }
  return fallback
}
