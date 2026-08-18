<template>
  <div ref="rootRef" class="relative w-full">
    <div class="relative">
      <input
        ref="inputRef"
        :value="localQuery"
        :placeholder="placeholder"
        :autofocus="autofocus"
        class="input rounded-md pr-16"
        :class="compact ? 'py-2 text-sm' : 'py-3 text-sm'"
        @focus="openPanel"
        @input="onInput"
        @keydown.enter.prevent="submitSearch"
      />
      <button
        v-if="localQuery"
        type="button"
        class="absolute right-9 top-1/2 -translate-y-1/2 text-muted hover:text-primary"
        aria-label="Clear search"
        @click="clearQuery"
      >
        <X class="h-4 w-4" />
      </button>
      <button
        type="button"
        class="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted hover:bg-surface-100 hover:text-primary"
        aria-label="Search"
        @click="submitSearch"
      >
        <Search class="h-4 w-4" />
      </button>
    </div>

    <div v-if="inlineScopeSelector" class="mt-2 flex items-center gap-1">
      <button
        v-for="option in scopeOptions"
        :key="`inline-${option.value}`"
        type="button"
        class="rounded-md px-2.5 py-1 text-xs font-medium transition-colors"
        :class="localScope === option.value ? 'bg-brand-500 text-white' : 'text-muted hover:bg-surface-100 hover:text-primary'"
        @mousedown.prevent
        @click="setScope(option.value)"
      >
        {{ option.label }}
      </button>
    </div>

    <div
      v-if="showPanel"
      class="absolute z-[140] mt-2 w-full overflow-hidden rounded-md border border-surface-200 bg-surface shadow-xl"
    >
      <div class="flex items-center gap-1 border-b border-surface-200 p-2">
        <button
          v-for="option in scopeOptions"
          :key="option.value"
          type="button"
          class="rounded-md px-2.5 py-1 text-xs font-medium transition-colors"
          :class="localScope === option.value ? 'bg-brand-500 text-white' : 'text-muted hover:bg-surface-100 hover:text-primary'"
          @mousedown.prevent
          @click="setScope(option.value)"
        >
          {{ option.label }}
        </button>
      </div>

      <div class="max-h-80 overflow-y-auto p-1.5">
        <p v-if="!trimmedQuery" class="px-2 py-2 text-xs text-muted">Start typing to see results.</p>
        <p v-else-if="loadingPreview" class="px-2 py-2 text-xs text-muted">Searching...</p>
        <p v-else-if="!previewItems.length" class="px-2 py-2 text-xs text-muted">No results found.</p>
        <button
          v-for="(item, index) in previewItems"
          :key="previewKey(item, index)"
          type="button"
          class="block w-full rounded-md px-2 py-2 text-left hover:bg-surface-100"
          @click="selectPreview(item)"
        >
          <UserRowCompact v-if="item.kind === 'user'" :user="item" />
          <SearchMediaPreviewRow v-else :item="item" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { Search, X } from '@lucide/vue'
import { authAPI, mediaAPI } from '@/api'
import { MEDIA_TYPE } from '@/constants/tracking'
import SearchMediaPreviewRow from '@/components/SearchMediaPreviewRow.vue'
import UserRowCompact from '@/components/UserRowCompact.vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  scope: { type: String, default: 'all' },
  placeholder: { type: String, default: 'Search movies, shows, users, or #id...' },
  autofocus: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  enablePreview: { type: Boolean, default: true },
  inlineScopeSelector: { type: Boolean, default: false },
  maxPreviewResults: { type: Number, default: 10 },
})

const emit = defineEmits(['update:modelValue', 'update:scope', 'submit', 'select-preview'])

const rootRef = ref(null)
const inputRef = ref(null)
const localQuery = ref(props.modelValue || '')
const localScope = ref(props.scope || 'all')
const panelOpen = ref(false)
const loadingPreview = ref(false)
const previewItems = ref([])
let debounceTimer = null
let requestId = 0

const scopeOptions = [
  { label: 'All', value: 'all' },
  { label: 'Movies', value: 'movies' },
  { label: 'Shows', value: 'shows' },
  { label: 'Users', value: 'users' },
]

const trimmedQuery = computed(() => localQuery.value.trim())
const shouldLoadPreview = computed(() => props.enablePreview && !props.inlineScopeSelector)
const showPanel = computed(() => !props.inlineScopeSelector && panelOpen.value)

watch(() => props.modelValue, (value) => {
  if (value !== localQuery.value) {
    localQuery.value = value || ''
  }
})

watch(() => props.scope, (value) => {
  if (value && value !== localScope.value) {
    localScope.value = value
  }
})

onClickOutside(rootRef, () => {
  panelOpen.value = false
})

function openPanel() {
  if (props.inlineScopeSelector) {
    return
  }
  panelOpen.value = true
  debouncedPreview()
}

function onInput(event) {
  localQuery.value = event.target.value
  emit('update:modelValue', localQuery.value)
  if (shouldLoadPreview.value) {
    debouncedPreview()
  }
}

function setScope(scope) {
  localScope.value = scope
  emit('update:scope', scope)
  nextTick(() => {
    if (inputRef.value) {
      inputRef.value.focus()
    }
  })
  if (shouldLoadPreview.value) {
    debouncedPreview()
  }
}

function clearQuery() {
  localQuery.value = ''
  emit('update:modelValue', '')
  previewItems.value = []
}

function submitSearch() {
  emit('submit', {
    query: localQuery.value.trim(),
    scope: localScope.value,
  })
  panelOpen.value = false
}

function selectPreview(item) {
  emit('select-preview', item)
  panelOpen.value = false
}

function previewKey(item, index) {
  if (item.kind === 'user') {
    return `user-${item.id || item.username || index}`
  }
  return `${item.media_type || 'movie'}-${item.id || index}`
}

function debouncedPreview() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(loadPreview, 300)
}

function scopeToMediaType(scope) {
  if (scope === 'movies') return MEDIA_TYPE.MOVIE
  if (scope === 'shows') return MEDIA_TYPE.TV
  return 'multi'
}

async function loadPreview() {
  if (!shouldLoadPreview.value) {
    previewItems.value = []
    return
  }

  const query = trimmedQuery.value
  if (!query) {
    previewItems.value = []
    return
  }

  const currentRequestId = ++requestId
  loadingPreview.value = true

  try {
    if (localScope.value === 'users') {
      if (query.length < 3) {
        previewItems.value = []
        return
      }
      const users = await authAPI.searchUsers(query)
      if (currentRequestId !== requestId) return
      previewItems.value = (users || []).slice(0, props.maxPreviewResults).map((row) => ({
        ...row,
        kind: 'user',
      }))
      return
    }

    const response = await mediaAPI.search(query, scopeToMediaType(localScope.value), 1)
    if (currentRequestId !== requestId) return

    const typedMediaType = localScope.value === 'movies'
      ? MEDIA_TYPE.MOVIE
      : localScope.value === 'shows'
        ? MEDIA_TYPE.TV
        : null

    const rows = (response?.results || [])
      .filter((row) => {
        if (typedMediaType) {
          return row.media_type === typedMediaType
        }
        return row.media_type === MEDIA_TYPE.MOVIE || row.media_type === MEDIA_TYPE.TV
      })
      .map((row) => ({
        ...row,
        media_type: typedMediaType || row.media_type || MEDIA_TYPE.MOVIE,
      }))
      .slice(0, props.maxPreviewResults)

    previewItems.value = rows
  } finally {
    if (currentRequestId === requestId) {
      loadingPreview.value = false
    }
  }
}
</script>
