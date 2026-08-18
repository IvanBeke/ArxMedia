<template>
  <div
    v-if="visible"
    :class="containerClass"
  >
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const baseClass = 'pointer-events-none absolute inset-0 flex items-center justify-center gap-3 opacity-100 transition-opacity duration-200 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100'

const props = defineProps({
  visible: { type: Boolean, default: false },
  zIndexClass: { type: String, default: 'z-20' },
})

const containerClass = computed(() => `${baseClass} ${props.zIndexClass}`)
</script>
