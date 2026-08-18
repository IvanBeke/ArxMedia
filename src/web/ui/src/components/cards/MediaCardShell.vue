<template>
  <div class="group block">
    <div class="relative aspect-[2/3] bg-surface-100 overflow-hidden" :class="posterFrameClass">
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
        <svg class="w-10 h-10 mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/>
        </svg>
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

<script setup>
import { computed } from 'vue'

const props = defineProps({
  posterUrl: { type: String, default: '' },
  posterAlt: { type: String, default: '' },
  posterLinkTo: { type: String, required: true },
  posterAriaLabel: { type: String, required: true },
  titleLinkTo: { type: String, default: '' },
  subtitleLinkTo: { type: String, default: '' },
  titleText: { type: String, required: true },
  titleTooltip: { type: String, default: '' },
  subtitleText: { type: String, default: '' },
  subtitleTooltip: { type: String, default: '' },
  posterHoverEffect: { type: String, default: 'blur' },
  posterFrameClass: { type: String, default: 'rounded-md' },
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
