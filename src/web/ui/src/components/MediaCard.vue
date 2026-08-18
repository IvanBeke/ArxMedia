<template>
  <MediaCardShell
    :poster-url="posterUrl"
    :poster-alt="title"
    :poster-link-to="linkTo"
    :poster-aria-label="`Open ${title}`"
    :title-link-to="linkTo"
    :title-text="title"
  >
    <template #overlay-right>
      <div v-if="card.status.visible || card.hasUserRating" class="absolute top-2 right-2 flex items-center gap-1.5">
        <CardUserRating v-if="card.hasUserRating" :value="card.userRating" size="xs" />
        <CardStatusBadge v-if="card.status.visible" :status="card.status.value" />
      </div>
    </template>

    <template #overlay-left>
      <div v-if="card.showMediaTypeBadge" class="absolute top-2 left-2">
        <CardMediaTypeBadge :media-type="card.mediaType" />
      </div>
    </template>

    <template #poster-overlay>
      <div class="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
    </template>

    <template #actions>
      <MediaCardActions :visible="card.actions.watchlist.visible || showWatchedQuickActionButton">
        <CardActionWatchlistToggle
          v-if="card.actions.watchlist.visible"
          :active="card.actions.watchlist.active"
          :loading="card.actions.watchlist.loading"
          :pulsing="card.actions.watchlist.pulsing"
          :aria-label="card.actions.watchlist.ariaLabel"
          @trigger="$emit('quick-action-watchlist')"
        />
        <CardActionWatchedMenu
          v-if="showWatchedQuickActionButton"
          :release-date="card.actions.watchedMenu.releaseDate"
          :loading="card.actions.watchedMenu.loading"
          :pulsing="card.actions.watchedMenu.pulsing"
          :aria-label="card.actions.watchedMenu.ariaLabel"
          @select="selectWatchOption"
        />
      </MediaCardActions>
    </template>

    <template #meta>
      <div class="mt-0.5 flex items-center gap-2 px-0.5">
        <p class="text-xs text-gray-500">{{ card.releaseDate }}</p>
        <CardProviderRating v-if="card.providerRating" :value="card.providerRating" size="xs" />
      </div>
    </template>
  </MediaCardShell>
</template>

<script setup>
import { computed } from 'vue'
import MediaCardShell from '@/components/cards/MediaCardShell.vue'
import MediaCardActions from '@/components/cards/MediaCardActions.vue'
import CardActionWatchlistToggle from '@/components/cards/primitives/CardActionWatchlistToggle.vue'
import CardActionWatchedMenu from '@/components/cards/primitives/CardActionWatchedMenu.vue'
import CardMediaTypeBadge from '@/components/cards/primitives/CardMediaTypeBadge.vue'
import CardProviderRating from '@/components/cards/primitives/CardProviderRating.vue'
import CardStatusBadge from '@/components/cards/primitives/CardStatusBadge.vue'
import CardUserRating from '@/components/cards/primitives/CardUserRating.vue'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { useMediaCardModel } from '@/composables/useMediaCardModel'

const props = defineProps({
  item: { type: Object, required: true },
  mediaType: { type: String, default: MEDIA_TYPE.MOVIE },
  watched: { type: Boolean, default: false },
  status: { type: String, default: 'none' },
  showQuickAction: { type: Boolean, default: false },
  quickActionActive: { type: Boolean, default: false },
  quickActionLoading: { type: Boolean, default: false },
  quickActionPulsing: { type: Boolean, default: false },
  quickActionAriaLabel: { type: String, default: 'Add to watchlist' },
  showWatchedQuickAction: { type: Boolean, default: false },
  watchedQuickActionLoading: { type: Boolean, default: false },
  watchedQuickActionPulsing: { type: Boolean, default: false },
  watchedQuickActionAriaLabel: { type: String, default: 'Mark as watched' },
})

const emit = defineEmits(['quick-action-watchlist', 'quick-action-watch-option'])

const { model } = useMediaCardModel(
  'mixed',
  computed(() => props.item),
  computed(() => ({
    mediaType: props.mediaType,
    watched: props.watched,
    status: props.status,
    showMediaTypeBadge: true,
    showQuickAction: props.showQuickAction,
    quickActionActive: props.quickActionActive,
    quickActionLoading: props.quickActionLoading,
    quickActionPulsing: props.quickActionPulsing,
    quickActionAriaLabel: props.quickActionAriaLabel,
    showWatchedQuickAction: props.showWatchedQuickAction,
    watchedQuickActionLoading: props.watchedQuickActionLoading,
    watchedQuickActionPulsing: props.watchedQuickActionPulsing,
    watchedQuickActionAriaLabel: props.watchedQuickActionAriaLabel,
  }))
)

const card = computed(() => model.value)
const title = computed(() => card.value.title)
const posterUrl = computed(() => card.value.posterUrl)
const linkTo = computed(() => card.value.titleLinkTo)
const showWatchedQuickActionButton = computed(() => {
  if (!card.value.actions.watchedMenu.visible) {
    return false
  }
  return card.value.status.value !== WATCH_ENTRY_STATUS.WATCHING && card.value.status.value !== WATCH_ENTRY_STATUS.WATCHED
})

function selectWatchOption(option) {
  emit('quick-action-watch-option', option)
}
</script>
