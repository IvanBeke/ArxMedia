<template>
  <nav v-if="totalPages > 1" class="mt-8 flex items-center justify-center" aria-label="Pagination">
    <div class="inline-flex overflow-hidden rounded-md border border-surface-200 bg-surface-100">
      <button
        type="button"
        class="pagination-btn border-r border-surface-200"
      :disabled="isFirst"
      :class="{ 'opacity-50': isFirst }"
      aria-label="Go to first page"
      @click="requestGo(1)"
    >
      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M18 6l-6 6 6 6" />
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6l-6 6 6 6" />
      </svg>
      </button>
      <button
        type="button"
        class="pagination-btn border-r border-surface-200"
      :disabled="isFirst"
      :class="{ 'opacity-50': isFirst }"
      aria-label="Go to previous page"
      @click="requestGo(currentPage - 1)"
    >
      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 6l-6 6 6 6" />
      </svg>
      </button>

      <span v-if="rangeStart > 1" class="pagination-ellipsis border-r border-surface-200" aria-hidden="true">...</span>
      <button
        v-for="pageNum in visiblePages"
        :key="pageNum"
        type="button"
        class="pagination-btn border-r border-surface-200"
        :class="pageNum === currentPage ? 'pagination-btn-active bg-brand-500 text-white hover:bg-brand-500' : ''"
        :disabled="disabled"
        :aria-current="pageNum === currentPage ? 'page' : undefined"
        :aria-label="`Go to page ${pageNum}`"
        @click="requestGo(pageNum)"
      >
        {{ pageNum }}
      </button>
      <span v-if="rangeEnd < totalPages" class="pagination-ellipsis border-r border-surface-200" aria-hidden="true">...</span>

      <button
        type="button"
        class="pagination-btn border-r border-surface-200"
      :disabled="isLast"
      :class="{ 'opacity-50': isLast }"
      aria-label="Go to next page"
      @click="requestGo(currentPage + 1)"
    >
      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 6l6 6-6 6" />
      </svg>
      </button>
      <button
        type="button"
        class="pagination-btn"
      :disabled="isLast"
      :class="{ 'opacity-50': isLast }"
      aria-label="Go to last page"
      @click="requestGo(totalPages)"
    >
      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 6l6 6-6 6" />
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6l6 6-6 6" />
      </svg>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.pagination-btn {
  min-width: 2.25rem;
  height: 2.25rem;
  padding: 0 0.5rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  line-height: 1;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s;
}

.pagination-btn:hover:not(:disabled) {
  background-color: var(--bg-surface-200);
}

.pagination-btn:disabled {
  cursor: not-allowed;
}

.pagination-btn-active {
  font-weight: 700;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, #ffffff 28%, transparent 72%);
}

.pagination-ellipsis {
  min-width: 2.25rem;
  height: 2.25rem;
  padding: 0 0.25rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  color: var(--text-muted);
}
</style>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  count: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  loadedCount: { type: Number, default: 0 },
  maxVisiblePages: { type: Number, default: 10 },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['go', 'update:page', 'update:totalPages'])

// Bootstrap mirror of the server's DRF page size; recalibrated below from the
// first full page of results. Partial pages must never shrink this value,
// otherwise totalPages inflates and phantom page links appear.
const DEFAULT_PAGE_SIZE = 20
const fullPageSize = ref(DEFAULT_PAGE_SIZE)

watch(
  [() => props.page, () => props.loadedCount],
  ([pageValue, loadedValue]) => {
    if (pageValue === 1 && loadedValue > 0) {
      fullPageSize.value = loadedValue
    }
  },
  { immediate: true }
)

const totalPages = computed(() => {
  if (!Number.isFinite(props.count) || props.count <= 0) {
    return 1
  }
  return Math.max(1, Math.ceil(props.count / fullPageSize.value))
})

watch(
  totalPages,
  (value) => {
    emit('update:totalPages', value)
    // Correct the parent's page state when committed data shrank below it.
    if (props.page > value) {
      emit('update:page', value)
    }
  },
  { immediate: true }
)

const currentPage = computed(() => Math.min(Math.max(1, props.page), totalPages.value))

function requestGo(pageNum) {
  if (
    props.disabled ||
    !Number.isInteger(pageNum) ||
    pageNum < 1 ||
    pageNum > totalPages.value ||
    pageNum === currentPage.value
  ) {
    return
  }
  emit('go', pageNum)
}

const isFirst = computed(() => props.disabled || currentPage.value <= 1)
const isLast = computed(() => props.disabled || currentPage.value >= totalPages.value)

const rangeStart = computed(() => {
  if (totalPages.value <= props.maxVisiblePages) {
    return 1
  }
  const half = Math.floor(props.maxVisiblePages / 2)
  const maxStart = totalPages.value - props.maxVisiblePages + 1
  return Math.max(1, Math.min(currentPage.value - half, maxStart))
})

const rangeEnd = computed(() => {
  if (totalPages.value <= props.maxVisiblePages) {
    return totalPages.value
  }
  return rangeStart.value + props.maxVisiblePages - 1
})

const visiblePages = computed(() => {
  const pages = []
  for (let pageNum = rangeStart.value; pageNum <= rangeEnd.value; pageNum += 1) {
    pages.push(pageNum)
  }
  return pages
})
</script>
