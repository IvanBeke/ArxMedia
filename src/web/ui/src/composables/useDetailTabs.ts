import { computed, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { MediaTab } from '@/components/MediaTabs.vue'

/**
 * Tab state for detail pages, kept in sync with `?tab=` in both directions.
 * `validTabs[0]` is the default; tabs missing from `tabs()` fall back to it.
 */
export function useDetailTabs<T extends string>(validTabs: readonly [T, ...T[]], tabs: () => MediaTab[]) {
  const route = useRoute()
  const router = useRouter()
  const defaultTab = validTabs[0]

  function parse(raw: unknown): T {
    const value = String(raw || defaultTab)
    return (validTabs as readonly string[]).includes(value) ? (value as T) : defaultTab
  }

  const activeTab = ref(parse(route.query.tab)) as Ref<T>
  const visibleTabs = computed(tabs)

  watch(visibleTabs, (list) => {
    if (!list.some((tab) => tab.id === activeTab.value)) activeTab.value = defaultTab
  }, { immediate: true })

  watch(() => activeTab.value, (tab) => {
    if (route.query.tab !== tab) router.replace({ query: { ...route.query, tab } })
  })

  // The URL can change while the page stays mounted (links to ?tab=..., query edits).
  watch(() => route.query.tab, (raw) => {
    const tab = parse(raw)
    if (tab !== activeTab.value) {
      activeTab.value = visibleTabs.value.some((item) => item.id === tab) ? tab : defaultTab
    }
  })

  function setTab(tab: T) {
    activeTab.value = tab
  }

  return { activeTab, visibleTabs, setTab }
}
