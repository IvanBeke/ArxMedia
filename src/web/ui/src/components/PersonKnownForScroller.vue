<template>
  <div v-if="items.length" class="relative">
    <div ref="scroller" class="flex gap-3 overflow-x-auto pb-2 scroll-smooth" role="list" aria-label="Known for titles">
      <RouterLink
        v-for="item in items"
        :key="`${item.media_type}-${item.id}`"
        :to="creditDetailLink(item)"
        :title="creditTitle(item)"
        role="listitem"
        class="w-28 sm:w-32 shrink-0 rounded-md overflow-hidden border border-surface-200 bg-surface-100/70 hover:border-brand-400 transition-colors"
      >
        <img
          v-if="item.poster_path"
          :src="tmdbImageUrl(item.poster_path, 'w185') || ''"
          :alt="creditTitle(item)"
          class="w-full aspect-[2/3] object-cover"
          loading="lazy"
          decoding="async"
        />
        <div v-else class="w-full aspect-[2/3] bg-surface-200 flex items-center justify-center p-2 text-center text-xs text-muted">
          {{ creditTitle(item) }}
        </div>
        <p class="px-2 pt-1.5 text-xs text-secondary leading-snug line-clamp-2 min-h-8" :title="creditTitle(item)">{{ creditTitle(item) }}</p>
        <p v-if="creditRole(item)" class="px-2 pb-1.5 text-[11px] text-muted leading-snug truncate" :title="creditRole(item)">{{ creditRole(item) }}</p>
        <span v-else class="block pb-1.5" aria-hidden="true"></span>
      </RouterLink>
    </div>
    <div class="mt-1 flex justify-end gap-1.5">
      <button
        type="button"
        class="px-2 py-1 rounded-md text-xs border border-surface-200 text-muted hover:text-primary hover:bg-surface-200 transition-colors"
        aria-label="Scroll known-for titles left"
        @click="scrollBy(-1)"
      >
        ←
      </button>
      <button
        type="button"
        class="px-2 py-1 rounded-md text-xs border border-surface-200 text-muted hover:text-primary hover:bg-surface-200 transition-colors"
        aria-label="Scroll known-for titles right"
        @click="scrollBy(1)"
      >
        →
      </button>
    </div>
  </div>
  <p v-else class="text-sm text-muted">No known-for titles.</p>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { tmdbImageUrl } from '@/utils/images'
import { creditDetailLink, creditRole, creditTitle } from '@/utils/person'
import type { PersonCredit } from '@/types/api'

withDefaults(defineProps<{
  items?: PersonCredit[]
}>(), { items: () => [] })

const scroller = ref<HTMLElement | null>(null)

function scrollBy(direction: 1 | -1) {
  const element = scroller.value
  if (!element) return
  element.scrollBy({ left: direction * Math.max(element.clientWidth * 0.8, 200), behavior: 'smooth' })
}
</script>
