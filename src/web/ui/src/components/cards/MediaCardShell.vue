<template>
  <div class="group block">
    <div class="relative isolate aspect-[2/3] bg-surface-100 overflow-hidden" :class="posterFrameClass">
      <RouterLink :to="posterLinkTo" class="absolute inset-0 z-10" :aria-label="posterAriaLabel" />

      <img
        v-if="posterUrl"
        :src="posterUrl"
        :alt="posterAlt || titleText"
        class="w-full h-full object-cover"
        :class="posterImageClass"
        loading="lazy"
      />

      <div v-else class="w-full h-full flex flex-col items-center justify-center text-gray-500 bg-gradient-to-br from-surface-200 to-surface-100 p-4">
        <Film class="w-10 h-10 mb-2 opacity-50" :stroke-width="1" />
        <span class="text-xs text-center line-clamp-3">{{ titleText }}</span>
      </div>

      <slot name="overlay-right" />
      <slot name="overlay-left" />
      <slot name="poster-overlay" />
      <slot name="actions" />
    </div>

    <slot name="after-poster" />

    <slot name="title">
      <RouterLink :to="titleLinkTo || posterLinkTo" class="mt-2 px-0.5 block" :title="titleTooltip || titleText">
        <p class="text-sm font-medium text-primary truncate group-hover:text-brand-400 transition-colors">{{ titleText }}</p>
      </RouterLink>
    </slot>

    <slot name="subtitle">
      <RouterLink
        v-if="subtitleText"
        :to="subtitleLinkTo || titleLinkTo || posterLinkTo"
        class="px-0.5 block"
        :title="subtitleTooltip || subtitleText"
      >
        <p class="text-xs text-muted truncate">{{ subtitleText }}</p>
      </RouterLink>
    </slot>

    <slot name="meta" />
    <slot name="footer" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Film } from '@lucide/vue'

const props = withDefaults(defineProps<{
  posterUrl?: string
  posterAlt?: string
  posterLinkTo: string
  posterAriaLabel: string
  titleLinkTo?: string
  subtitleLinkTo?: string
  titleText: string
  titleTooltip?: string
  subtitleText?: string
  subtitleTooltip?: string
  posterHoverEffect?: string
  posterFrameClass?: string
}>(), {
  posterUrl: '', posterAlt: '', titleLinkTo: '', subtitleLinkTo: '', titleTooltip: '', subtitleText: '', subtitleTooltip: '',
  posterHoverEffect: 'blur', posterFrameClass: 'rounded-md',
})

const posterImageClass = computed(() => {
  if (props.posterHoverEffect === 'dim') {
    return 'transition-opacity duration-200 group-hover:opacity-80'
  }
  if (props.posterHoverEffect === 'none') {
    return ''
  }
  return 'transition-[filter] duration-300 group-hover:blur-[2px]'
})
</script>
