import { ref, watch } from 'vue'
import { parsePage } from '@/utils/pagination'

// Owns the repeated route-query <-> page-state wiring shared by filter-bar
// views: the current page is initialized from ?page= and follows external
// query changes (browser back/forward) without triggering loads itself —
// mutating the returned ref is what drives each view's load watcher.
export function useQueryPageSync(route) {
  const currentPage = ref(parsePage(route.query.page))

  watch(
    () => route.query.page,
    () => {
      const nextPage = parsePage(route.query.page)
      if (nextPage === currentPage.value) return
      currentPage.value = nextPage
    }
  )

  return currentPage
}
