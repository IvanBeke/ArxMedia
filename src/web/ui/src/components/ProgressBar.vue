<template>
  <div class="progress-bar w-full" :class="$attrs.class">
    <div
      class="progress-fill"
      :style="`width: ${pct}%`"
    />
  </div>
</template>

<script setup>
defineProps({
  pct: { type: Number, default: 0 }
})
</script>
