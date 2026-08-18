<template>
  <MediaCardShell
    :poster-url="card.posterUrl"
    :poster-alt="card.posterAlt"
    :poster-link-to="resolvedPosterLinkTo"
    :poster-aria-label="`Open ${card.title}`"
    :title-link-to="resolvedTitleLinkTo"
    :title-text="card.title"
    :title-tooltip="card.titleTooltip"
    :subtitle-link-to="resolvedTitleLinkTo"
    :subtitle-text="showMeta ? card.subtitle : ''"
    :subtitle-tooltip="card.subtitleTooltip"
    poster-hover-effect="dim"
    poster-frame-class="rounded-lg"
  >
    <template #overlay-right>
      <div class="absolute top-2 right-2 z-10 flex flex-col items-end gap-1">
        <CardEpisodeCodePill
          v-if="card.episodeCode.visible"
          :season-number="card.episodeCode.seasonNumber"
          :episode-number="card.episodeCode.episodeNumber"
          variant="pill"
          size="s"
          extra-class="shadow ring-1 ring-black/10"
        />
        <CardUserRating v-if="hasRating" :value="card.userRating" size="xs" />
      </div>
    </template>

    <template #overlay-left>
      <div v-if="card.showMediaTypeBadge || $slots['poster-badge']" class="absolute top-2 left-2 z-10 flex flex-col items-start gap-1">
        <CardMediaTypeBadge v-if="card.showMediaTypeBadge" :media-type="card.mediaType" />
        <slot v-if="$slots['poster-badge']" name="poster-badge" />
      </div>
    </template>

    <template #title>
      <slot name="title" :display-title="card.title" :title-link-to="resolvedTitleLinkTo" :entry="entry">
        <RouterLink :to="resolvedTitleLinkTo" class="block px-2 pt-2 pb-1" :title="card.titleTooltip">
          <p class="text-sm text-primary font-medium leading-snug break-words hover:text-brand-400">{{ card.title }}</p>
        </RouterLink>
      </slot>
    </template>

    <template #subtitle>
      <div class="px-2">
        <slot name="meta" :subtitle="card.subtitle" :timestamp-label="timestampLabel" :entry="entry">
          <p v-if="showMeta && card.subtitle" class="text-xs text-muted leading-snug break-words" :title="card.subtitleTooltip">{{ card.subtitle }}</p>
        </slot>
      </div>
    </template>

    <template #footer>
      <div class="px-2 pb-2 space-y-0.5">
        <slot name="timestamp" :timestamp-label="timestampLabel" :entry="entry">
          <p v-if="showTimestamp && timestampLabel" class="text-xs text-muted">{{ timestampLabel }}</p>
        </slot>
      </div>
    </template>

    <template #actions>
      <MediaCardActions :visible="showRemoveAction">
        <CardActionRemoveHistoryEntry @action:history-remove="$emit('action:history-remove', entry)" />
      </MediaCardActions>
    </template>
  </MediaCardShell>
</template>

<script setup>
import { computed } from 'vue'
import MediaCardActions from '@/components/cards/MediaCardActions.vue'
import MediaCardShell from '@/components/cards/MediaCardShell.vue'
import CardActionRemoveHistoryEntry from '@/components/cards/primitives/CardActionRemoveHistoryEntry.vue'
import CardEpisodeCodePill from '@/components/cards/primitives/CardEpisodeCodePill.vue'
import CardMediaTypeBadge from '@/components/cards/primitives/CardMediaTypeBadge.vue'
import CardUserRating from '@/components/cards/primitives/CardUserRating.vue'
import { useMediaCardModel } from '@/composables/useMediaCardModel'

const props = defineProps({
  entry: { type: Object, required: true },
  linkTo: { type: String, required: true },
  posterLinkTo: { type: String, default: '' },
  titleLinkTo: { type: String, default: '' },
  timestamp: { type: String, default: '' },
  timestampText: { type: String, default: '' },
  showMeta: { type: Boolean, default: true },
  showTimestamp: { type: Boolean, default: true },
  showRemoveAction: { type: Boolean, default: false },
})

defineEmits(['action:history-remove'])

const resolvedPosterLinkTo = computed(() => props.posterLinkTo || props.linkTo)
const resolvedTitleLinkTo = computed(() => props.titleLinkTo || props.linkTo)

const { model } = useMediaCardModel(
  'history',
  computed(() => props.entry),
  computed(() => ({
    posterLinkTo: resolvedPosterLinkTo.value,
    titleLinkTo: resolvedTitleLinkTo.value,
    subtitleLinkTo: resolvedTitleLinkTo.value,
    showMediaTypeBadge: true,
  }))
)

const card = computed(() => model.value)
const hasRating = computed(() => card.value.userRating !== null && card.value.userRating !== undefined)

const timestampLabel = computed(() => {
  if (props.timestampText) {
    return props.timestampText
  }
  const rawTimestamp = props.timestamp || props.entry.watched_at
  if (!rawTimestamp) return ''
  const date = new Date(rawTimestamp)
  if (Number.isNaN(date.getTime())) return ''
  const datePart = date.toLocaleDateString('en-GB')
  const timePart = date.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return `${datePart} · ${timePart}`
})
</script>
