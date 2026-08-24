// Shared pagination helpers for views backed by DRF PageNumberPagination.

// Bootstrap mirror of the server's page size until a full first response
// calibrates it (see PaginationControls).
export const DEFAULT_PAGE_SIZE = 20

export function parsePage(value, fallback = 1) {
  const page = Number.parseInt(String(value ?? ''), 10)
  return Number.isInteger(page) && page > 0 ? page : fallback
}

// Normalizes a paginated API payload into { items, count, loadedCount }.
// Handles DRF envelopes ({count, results}), bare arrays, and empty payloads.
export function normalizePagedResponse(data) {
  if (Array.isArray(data?.results)) {
    return {
      items: data.results,
      count: Number.isFinite(data.count) ? data.count : data.results.length,
      loadedCount: data.results.length,
    }
  }

  const list = Array.isArray(data) ? data : []
  return { items: list, count: list.length, loadedCount: 0 }
}

// Returns the page to recover to when the API rejected the requested page
// (DRF answers out-of-range pages with 404 {"detail": "Invalid page."}),
// or null when the error is unrelated and should be surfaced normally.
export function invalidPageRecovery(error, requestedPage, fallback = 1) {
  const isInvalidPage = Boolean(
    error &&
    error.status === 404 &&
    typeof error.detail === 'string' &&
    /invalid page/i.test(error.detail)
  )
  if (!isInvalidPage || !Number.isInteger(requestedPage) || requestedPage <= fallback) {
    return null
  }
  return fallback
}
