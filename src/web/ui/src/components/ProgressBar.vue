<template>
  <div class="progress-bar w-full" :class="$attrs.class">
    <div
      class="progress-fill"
      :style="`width: ${pct}%`"
    />
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  pct?: number
}>(), {
  pct: 0,
})
</script>
