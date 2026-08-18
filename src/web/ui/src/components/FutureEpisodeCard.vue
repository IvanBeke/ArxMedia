<template>
  <div class="group block">
    <div class="relative aspect-[2/3] w-full overflow-hidden bg-surface-200" :class="posterFrameClass">
      <RouterLink
        :to="posterLinkTo"
        class="absolute inset-0 z-10"
        :aria-label="`Open ${showTitle}`"
      />

      <img
        v-if="posterUrl"
        :src="posterUrl"
        :alt="showTitle"
        class="w-full h-full object-cover transition-opacity duration-200 group-hover:opacity-80"
        loading="lazy"
      />
      <div v-else class="w-full h-full flex items-center justify-center">
        <svg class="w-12 h-12 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 16h4m10 0h4M4 4h16v16H4z"/>
        </svg>
      </div>

      <span
        v-if="showNewBadge"
        class="absolute top-2 left-2 z-20 inline-flex items-center rounded-full bg-brand-500/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white shadow ring-1 ring-black/10"
      >
        New
      </span>

      <div class="absolute inset-x-0 bottom-0 z-20 bg-gradient-to-t from-black/80 via-black/45 to-transparent px-2 py-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
        <p class="text-xs text-white font-medium truncate">{{ episodeTitleLabel }}</p>
      </div>

      <div
        v-if="showWatchAction"
        class="pointer-events-none absolute inset-0 z-30 flex items-center justify-center opacity-100 transition-opacity duration-200 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100"
      >
        <button
          type="button"
          class="pointer-events-auto cursor-pointer w-10 h-10 rounded-full flex items-center justify-center border shadow-lg transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-400 focus-visible:ring-offset-surface bg-brand-500/95 border-brand-400 text-white hover:bg-brand-600"
          :disabled="watchLoading"
          aria-label="Mark next episode watched"
          @click.stop.prevent="$emit('watch')"
        >
          <div v-if="watchLoading" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
          <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z"/>
          </svg>
        </button>
      </div>
    </div>

    <div
      v-if="showProgressStrip"
      class="relative overflow-hidden"
      :class="progressStripClass"
      :style="progressStripStyle"
    >
      <div
        class="absolute inset-y-0 left-0 bg-brand-500/60"
        :style="{ width: `${safeProgressPercent}%` }"
      />
      <div class="relative flex items-center justify-between gap-2 px-2 py-1 text-[10px] font-semibold text-white">
        <span class="truncate">{{ formattedEpisodeDuration }}</span>
        <div class="min-w-0 inline-flex items-center justify-end gap-0.5">
          <span class="truncate text-right">{{ formattedEpisodesLeft }}</span>
          <span class="text-white/70">&middot;</span>
          <span class="truncate text-right">{{ formattedRuntimeLeft }}</span>
        </div>
      </div>
    </div>

    <RouterLink :to="resolvedTitleLinkTo" class="block p-2">
      <p class="text-sm text-primary font-medium truncate hover:text-brand-400">{{ showTitle }}</p>
    </RouterLink>

    <div class="px-2 pb-2 space-y-0.5">
      <p class="text-xs text-muted"><EpisodeCodePill :season-number="seasonNumber" :episode-number="episodeNumber" variant="plain" /></p>
      <p v-if="metaText" class="text-xs text-muted">{{ metaText }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'

const props = defineProps({
  showTitle: { type: String, required: true },
  episodeTitle: { type: String, default: '' },
  seasonNumber: { type: [Number, String], required: true },
  episodeNumber: { type: [Number, String], required: true },
  posterUrl: { type: String, default: '' },
  posterLinkTo: { type: String, required: true },
  titleLinkTo: { type: String, default: '' },
  showNewBadge: { type: Boolean, default: false },
  showWatchAction: { type: Boolean, default: false },
  watchLoading: { type: Boolean, default: false },
  metaText: { type: String, default: '' },
  progressPercent: { type: Number, default: null },
  episodeDurationMinutes: { type: Number, default: null },
  episodesLeft: { type: Number, default: null },
  runtimeLeftMinutes: { type: Number, default: null },
  runtimeLeftHasUnknown: { type: Boolean, default: false },
})

defineEmits(['watch'])

const resolvedTitleLinkTo = computed(() => props.titleLinkTo || props.posterLinkTo)

const episodeTitleLabel = computed(() => props.episodeTitle || 'Episode')

const showProgressStrip = computed(() => {
  return props.progressPercent !== null || props.episodesLeft !== null
})

const safeProgressPercent = computed(() => {
  const value = Number(props.progressPercent)
  if (!Number.isFinite(value)) return 0
  if (value < 0) return 0
  if (value > 100) return 100
  return Math.round(value)
})

const progressStripClass = computed(() => 'rounded-lg')

const posterFrameClass = computed(() => {
  if (showProgressStrip.value) {
    return 'rounded-t-lg rounded-b-none'
  }
  return 'rounded-lg'
})

const progressStripStyle = computed(() => {
  return {
    backgroundColor: 'var(--upnext-strip-bg)',
    borderTopLeftRadius: 0,
    borderTopRightRadius: 0,
  }
})

function formatMinutes(value) {
  const minutes = Number(value)
  if (!Number.isFinite(minutes) || minutes < 0) return '--'
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const remainder = minutes % 60
  return remainder ? `${hours}h ${remainder}m` : `${hours}h`
}

const formattedEpisodeDuration = computed(() => formatMinutes(props.episodeDurationMinutes))

const formattedEpisodesLeft = computed(() => {
  const left = Number(props.episodesLeft)
  if (!Number.isFinite(left) || left < 0) return '--'
  return `${left} left`
})

const formattedRuntimeLeft = computed(() => {
  const runtime = formatMinutes(props.runtimeLeftMinutes)
  if (runtime === '--') return runtime
  return props.runtimeLeftHasUnknown ? `~${runtime}` : runtime
})
</script>
