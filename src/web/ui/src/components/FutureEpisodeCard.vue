<template>
  <MediaCardShell
    :poster-url="card.posterUrl || posterUrl"
    :poster-alt="showTitle"
    :poster-link-to="posterLinkTo"
    :poster-aria-label="`Open ${showTitle}`"
    :title-link-to="resolvedTitleLinkTo"
    :title-text="showTitle"
    :title-tooltip="showTitle"
    :subtitle-link-to="resolvedTitleLinkTo"
    :subtitle-text="episodeTitle"
    :subtitle-tooltip="episodeTitleLabel"
    :poster-frame-class="posterFrameClass"
    poster-hover-effect="dim"
  >
    <template #overlay-left>
      <span
        v-if="showNewBadge"
        class="absolute top-2 left-2 z-20 inline-flex items-center rounded-full bg-brand-500/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white shadow ring-1 ring-black/10"
      >
        New
      </span>
    </template>

    <template #overlay-right>
      <div class="absolute top-2 right-2 z-20 inline-flex flex-col items-end gap-1">
        <CardEpisodeCodePill
          :season-number="card.episodeCode.seasonNumber"
          :episode-number="card.episodeCode.episodeNumber"
          variant="pill"
          size="s"
          extra-class="shadow ring-1 ring-black/10"
        />
        <EpisodeTypePill :value="episodeType" class="shadow ring-1 ring-black/10" />
      </div>
    </template>

    <template #actions>
      <MediaCardActions :visible="showWatchAction" z-index-class="z-30">
        <CardActionMarkNextEpisodeWatched
          :loading="watchLoading"
          aria-label="Mark next episode watched"
          @trigger="$emit('watch')"
        />
      </MediaCardActions>
    </template>

    <template #title>
      <RouterLink :to="resolvedTitleLinkTo" class="block px-2 pt-2 pb-1" :title="showTitle">
        <p class="text-sm text-primary font-medium leading-snug break-words hover:text-brand-400">{{ showTitle }}</p>
      </RouterLink>
    </template>

    <template #subtitle>
      <div class="px-2">
        <p v-if="episodeTitle" class="text-xs text-muted leading-snug break-words" :title="episodeTitleLabel">{{ episodeTitleLabel }}</p>
      </div>
    </template>

    <template #meta>
      <div class="px-2 pb-2 space-y-0.5">
        <p v-if="metaText" class="text-xs text-muted">{{ metaText }}</p>
      </div>
    </template>

    <template #after-poster>
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
    </template>
  </MediaCardShell>
</template>

<script setup>
import { computed } from 'vue'
import MediaCardShell from '@/components/cards/MediaCardShell.vue'
import MediaCardActions from '@/components/cards/MediaCardActions.vue'
import CardActionMarkNextEpisodeWatched from '@/components/cards/primitives/CardActionMarkNextEpisodeWatched.vue'
import CardEpisodeCodePill from '@/components/cards/primitives/CardEpisodeCodePill.vue'
import EpisodeTypePill from '@/components/EpisodeTypePill.vue'
import { useMediaCardModel } from '@/composables/useMediaCardModel'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import { formatHoursMinutes } from '@/utils/progress'

const props = defineProps({
  showTitle: { type: String, required: true },
  episodeTitle: { type: String, default: '' },
  episodeType: { type: String, default: '' },
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

const { model } = useMediaCardModel('up-next', computed(() => ({
  media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
  show_title: props.showTitle,
  episode_title: props.episodeTitle,
  season_number: props.seasonNumber,
  episode_number: props.episodeNumber,
  poster_url: props.posterUrl,
})), computed(() => ({
  posterLinkTo: props.posterLinkTo,
  titleLinkTo: resolvedTitleLinkTo.value,
  subtitleLinkTo: resolvedTitleLinkTo.value,
  showMediaTypeBadge: false,
})))

const card = computed(() => model.value)

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
  return formatHoursMinutes(minutes)
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
