<template>
  <span class="badge text-[10px] font-medium" :class="badgeClass">
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { useI18n } from '@/i18n'
import type { MediaType } from '@/types/api'

const props = withDefaults(defineProps<{
  mediaType?: MediaType
}>(), {
  mediaType: MEDIA_TYPE.MOVIE,
})

const { t } = useI18n()
const isMovie = computed(() => props.mediaType === MEDIA_TYPE.MOVIE)
const label = computed(() => (isMovie.value ? t('card_badge_movie') : t('card_badge_show')))
const badgeClass = computed(() => (isMovie.value ? 'bg-blue-500/80 text-blue-100' : 'bg-brand-500/80 text-brand-100'))
</script>
