export function getApiErrorMessage(error, fallback) {
  if (error?.detail) return error.detail
  if (Array.isArray(error?.non_field_errors) && error.non_field_errors.length) {
    return error.non_field_errors[0]
  }
  return fallback
}
