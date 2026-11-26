<template>
  <div
    class="w-7 h-7 rounded-md flex items-center justify-center shadow-lg"
    :class="statusBadgeClass"
    :title="statusTooltip"
    :aria-label="statusTooltip"
    tabindex="0"
  >
    <Check v-if="statusValue === WATCH_ENTRY_STATUS.WATCHED" class="w-4 h-4 text-white" :stroke-width="2.5" />
    <CirclePlay v-else-if="statusValue === WATCH_ENTRY_STATUS.WATCHING" class="w-4 h-4 text-white" />
    <Bookmark v-else-if="statusValue === WATCH_ENTRY_STATUS.PLAN_TO_WATCH" class="w-4 h-4 text-white" fill="currentColor" :stroke-width="1.4" />
    <X v-else class="w-4 h-4 text-white" :stroke-width="2.5" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Bookmark, Check, CirclePlay, X } from '@lucide/vue'
import { STATUS_COLOR } from '@/constants/statColors'
import { WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { useI18n } from '@/i18n'
import type { WatchEntryStatus } from '@/types/tracking'

const props = withDefaults(defineProps<{
  status?: WatchEntryStatus
  watched?: boolean
}>(), {
  status: WATCH_ENTRY_STATUS.NONE,
  watched: false,
})

const { t } = useI18n()

const statusValue = computed(() => {
  if (props.status && props.status !== WATCH_ENTRY_STATUS.NONE) {
    return props.status
  }
  return props.watched ? WATCH_ENTRY_STATUS.WATCHED : WATCH_ENTRY_STATUS.NONE
})

// Widened so a status the UI does not know about falls back to the neutral colour instead of throwing.
const statusColors: Record<string, { bg: string } | undefined> = STATUS_COLOR
const statusBadgeClass = computed(() => statusColors[statusValue.value]?.bg ?? 'bg-surface-300')

const statusLabel = computed(() => {
  if (statusValue.value === WATCH_ENTRY_STATUS.WATCHED) return t('watch_action_watched')
  if (statusValue.value === WATCH_ENTRY_STATUS.WATCHING) return t('watch_action_watching')
  if (statusValue.value === WATCH_ENTRY_STATUS.PLAN_TO_WATCH) return t('page_watchlist')
  if (statusValue.value === WATCH_ENTRY_STATUS.DROPPED) return t('watch_action_dropped')
  return ''
})

const statusTooltip = computed(() => {
  if (!statusLabel.value) return ''
  return t('card_status_tooltip', { status: statusLabel.value })
})
</script>
