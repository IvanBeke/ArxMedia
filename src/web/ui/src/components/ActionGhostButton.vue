<template>
  <button
    type="button"
    class="btn-ghost inline-flex items-center gap-2 h-9 text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    :class="active ? 'border-brand-500/60 text-brand-400' : ''"
    :disabled="disabled"
    @click="emit('click')"
  >
    <slot name="icon" />
    <slot />
  </button>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  active?: boolean
  disabled?: boolean
}>(), { active: false, disabled: false })

const emit = defineEmits<{
  click: []
}>()
</script>
