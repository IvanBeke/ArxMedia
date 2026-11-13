<template>
  <div class="flex items-start gap-2">
    <div class="w-[50px] flex-shrink-0 overflow-hidden rounded-sm bg-surface-200">
      <img
        v-if="posterUrl"
        :src="posterUrl"
        :alt="title"
        class="block w-full h-auto"
        loading="lazy"
      />
      <div v-else class="h-[75px] w-full"></div>
    </div>
    <div class="min-w-0 flex-1">
      <p class="truncate text-sm text-primary">{{ title }}</p>
      <div class="mt-0.5 flex items-center gap-1 text-[11px] text-muted">
        <span>{{ year || '-' }}</span>
        <span>•</span>
        <span>{{ typeLabel }}</span>
        <span v-if="statusLabel">•</span>
        <span v-if="statusLabel" class="truncate">{{ statusLabel }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '@/i18n'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { temporalYear } from '@/utils/temporal'
import { tmdbImageUrl } from '@/utils/images'
import type { MediaResult } from '@/types/api'

type SearchMediaPreview = MediaResult & { poster_url?: string | null }

const props = defineProps<{ item: SearchMediaPreview }>()

const { t } = useI18n()

const title = computed(() => props.item?.title || props.item?.name || t('common_untitled'))
const year = computed(() => {
  const raw = props.item?.release_date
  return raw ? (temporalYear(raw) || '') : ''
})

const typeLabel = computed(() => props.item?.media_type === MEDIA_TYPE.TV ? t('search_type_show') : t('search_type_movie'))

const statusLabel = computed(() => {
  const status = props.item?.user_status?.status
  if (status === WATCH_ENTRY_STATUS.WATCHED) return t('tracking_watched')
  if (status === WATCH_ENTRY_STATUS.WATCHING) return t('watch_action_watching')
  if (status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH) return t('page_watchlist')
  if (status === WATCH_ENTRY_STATUS.DROPPED) return t('watch_action_dropped')
  return ''
})

const posterUrl = computed(() => {
  const path = props.item?.poster_path || props.item?.poster_url
  if (!path) return null
  if (path.startsWith('http')) return path
  return tmdbImageUrl(path, 'w185')
})
</script>
