<template>
  <component :is="tag" :class="classes" :style="style">
    {{ displayValue }}
  </component>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  seasonNumber: { type: [Number, String], default: null },
  episodeNumber: { type: [Number, String], default: null },
  variant: { type: String, default: 'pill' },
  size: { type: String, default: 'sm' },
  fallback: { type: String, default: '--' },
  as: { type: String, default: 'span' },
})

const PRESET_SIZES = new Set(['xs', 's', 'sm'])

const displayValue = computed(() => {
  const season = Number(props.seasonNumber)
  const episode = Number(props.episodeNumber)
  if (!Number.isInteger(season) || season <= 0 || !Number.isInteger(episode) || episode <= 0) {
    return props.fallback
  }
  return `S${String(season).padStart(2, '0')}·E${String(episode).padStart(2, '0')}`
})

const tag = computed(() => props.as || 'span')

const isPresetSize = computed(() => PRESET_SIZES.has(props.size))

const style = computed(() => (isPresetSize.value ? undefined : { fontSize: props.size }))

const classes = computed(() => {
  if (props.variant === 'plain') {
    if (props.size === 'xs') return 'episode-code-plain episode-code-plain-xs'
    return 'episode-code-plain'
  }
  if (props.size === 's') return 'episode-code-pill episode-code-pill-s'
  if (props.size === 'xs') return 'episode-code-pill episode-code-pill-xs'
  return 'episode-code-pill'
})
</script>

<style scoped>
.episode-code-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 0.35rem;
  padding: 0.24rem 0.5rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  background: var(--brand-500);
  color: #fff;
  border: 1px solid var(--brand-500);
  line-height: 1;
}

.episode-code-pill-xs {
  padding: 0.12rem 0.4rem;
  font-size: 0.62rem;
}

.episode-code-pill-s {
  padding: 0.18rem 0.46rem;
  font-size: 0.68rem;
}

.episode-code-plain {
  display: inline;
  font-weight: 400;
  letter-spacing: 0.01em;
}

.episode-code-plain-xs {
  font-size: 0.75em;
}
</style>
