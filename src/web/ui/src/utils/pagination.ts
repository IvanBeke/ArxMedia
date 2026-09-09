// Shared pagination helpers for views backed by DRF PageNumberPagination.

// Bootstrap mirror of the server's page size until a full first response
// calibrates it (see PaginationControls).
export const DEFAULT_PAGE_SIZE = 20

export function parsePage(value: unknown, fallback = 1): number {
  const page = Number.parseInt(String(value ?? ''), 10)
  return Number.isInteger(page) && page > 0 ? page : fallback
}

// Normalizes a paginated API payload into { items, count, loadedCount }.
// Handles DRF envelopes ({count, results}), bare arrays, and empty payloads.
export function normalizePagedResponse<T>(data: unknown): {
  items: T[]
  count: number
  loadedCount: number
} {
  if (
    typeof data === 'object' &&
    data !== null &&
    'results' in data &&
    Array.isArray(data.results)
  ) {
    const results = data.results as T[]
    const count = 'count' in data && typeof data.count === 'number' ? data.count : results.length
    return {
      items: results,
      count: Number.isFinite(count) ? count : results.length,
      loadedCount: results.length,
    }
  }

  const list = Array.isArray(data) ? (data as T[]) : []
  return { items: list, count: list.length, loadedCount: 0 }
}

// Returns the page to recover to when the API rejected the requested page
// (DRF answers out-of-range pages with 404 {"detail": "Invalid page."}),
// or null when the error is unrelated and should be surfaced normally.
export function invalidPageRecovery(error: unknown, requestedPage: number, fallback = 1): number | null {
  const isInvalidPage = Boolean(
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    error.status === 404 &&
    'detail' in error &&
    typeof error.detail === 'string' &&
    /invalid page/i.test(error.detail)
  )
  if (!isInvalidPage || !Number.isInteger(requestedPage) || requestedPage <= fallback) {
    return null
  }
  return fallback
}
