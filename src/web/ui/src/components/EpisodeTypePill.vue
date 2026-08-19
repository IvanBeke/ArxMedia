<template>
  <component v-if="displayValue" :is="tag" :class="classes">
    {{ displayValue }}
  </component>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: String, default: '' },
  variant: { type: String, default: 'pill' },
  size: { type: String, default: 'sm' },
  as: { type: String, default: 'span' },
})

const rawValue = computed(() => String(props.value || '').trim())

const displayValue = computed(() => {
  if (!rawValue.value) return ''
  if (rawValue.value.toLowerCase() === 'standard') return ''
  return rawValue.value.replace(/[_-]+/g, ' ')
})

const tag = computed(() => props.as || 'span')

const classes = computed(() => {
  if (props.variant === 'plain') {
    if (props.size === 'xs') return 'episode-type-plain episode-type-plain-xs'
    return 'episode-type-plain'
  }
  if (props.size === 's') return 'episode-type-pill episode-type-pill-s'
  if (props.size === 'xs') return 'episode-type-pill episode-type-pill-xs'
  return 'episode-type-pill'
})
</script>

<style scoped>
.episode-type-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.35rem;
  padding: 0.24rem 0.5rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  background: var(--brand-500);
  color: #fff;
  border: 1px solid var(--brand-500);
  line-height: 1;
  text-transform: capitalize;
}

.episode-type-pill-xs {
  padding: 0.12rem 0.4rem;
  font-size: 0.62rem;
  line-height: 1;
}

.episode-type-pill-s {
  padding: 0.18rem 0.46rem;
  font-size: 0.68rem;
  line-height: 1;
}

.episode-type-plain {
  display: inline;
  font-weight: 400;
  letter-spacing: 0.01em;
  text-transform: capitalize;
}

.episode-type-plain-xs {
  font-size: 0.75em;
}
</style>
