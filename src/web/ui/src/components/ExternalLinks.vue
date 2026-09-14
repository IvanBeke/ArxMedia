<template>
  <div v-if="hasAny" class="flex flex-wrap items-center gap-2">
    <span class="text-xs text-gray-500 uppercase tracking-wider mr-1">More info</span>
    <a
      v-if="tmdbUrl"
      :href="tmdbUrl"
      target="_blank"
      rel="noopener"
      class="px-2.5 py-1 rounded-md text-xs border border-surface-200 text-muted hover:text-primary hover:bg-surface-200 transition-colors"
    >
      TMDB
    </a>
    <a
      v-if="tvmazeUrl"
      :href="tvmazeUrl"
      target="_blank"
      rel="noopener"
      class="px-2.5 py-1 rounded-md text-xs border border-surface-200 text-muted hover:text-primary hover:bg-surface-200 transition-colors"
    >
      TVMaze
    </a>
    <a
      v-if="imdbUrl"
      :href="imdbUrl"
      target="_blank"
      rel="noopener"
      class="px-2.5 py-1 rounded-md text-xs border border-surface-200 text-muted hover:text-primary hover:bg-surface-200 transition-colors"
    >
      IMDb
    </a>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  tmdbUrl?: string | null
  tvmazeUrl?: string | null
  imdbUrl?: string | null
}>(), { tmdbUrl: null, tvmazeUrl: null, imdbUrl: null })

const hasAny = computed(() => Boolean(props.tmdbUrl || props.tvmazeUrl || props.imdbUrl))
</script>
