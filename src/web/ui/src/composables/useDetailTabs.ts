import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { MediaTab } from '@/components/MediaTabs.vue'

/**
 * Tab state for detail pages, derived from `?tab=`; selecting a tab pushes the URL.
 * `validTabs[0]` is the default; tabs missing from `tabs()` display as it.
 */
export function useDetailTabs<T extends string>(validTabs: readonly [T, ...T[]], tabs: () => MediaTab[]) {
  const route = useRoute()
  const router = useRouter()
  const defaultTab = validTabs[0]
  // The page stays mounted while it fades out, so it must ignore the next page's route.
  const path = route.path

  function parse(raw: unknown): T {
    const value = String(raw || defaultTab)
    return (validTabs as readonly string[]).includes(value) ? (value as T) : defaultTab
  }

  const visibleTabs = computed(tabs)
  let lastTab = defaultTab

  // The URL is the source of truth. A tab that isn't available is shown as the default
  // without rewriting the URL, so it adds no history entries.
  const activeTab = computed<T>({
    get() {
      if (route.path !== path) return lastTab
      const tab = parse(route.query.tab)
      lastTab = visibleTabs.value.some((item) => item.id === tab) ? tab : defaultTab
      return lastTab
    },
    set(tab) {
      if (route.path === path && parse(route.query.tab) !== tab) router.push({ query: { ...route.query, tab } })
    },
  })

  return { activeTab, visibleTabs }
}
