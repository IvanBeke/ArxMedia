<template>
  <div class="flex items-center gap-1" role="radiogroup" :aria-label="t('rating_group_label')">
    <button
      v-for="n in 10"
      :key="n"
      @click="emit('update:modelValue', n)"
      @mouseenter="hovered = n"
      @mouseleave="hovered = 0"
      class="transition-transform hover:scale-110"
      type="button"
      role="radio"
      :aria-checked="modelValue === n ? 'true' : 'false'"
      :aria-label="t('rating_item_label', { value: n })"
    >
      <svg
        class="w-5 h-5 transition-colors"
        :class="(hovered || modelValue) >= n ? 'text-amber-500' : 'text-surface-300'"
        fill="currentColor"
        viewBox="0 0 24 24"
      >
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
      </svg>
    </button>
    <span v-if="modelValue" class="ml-2 inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700">{{ modelValue }}/10</span>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from '@/i18n'

defineProps({ modelValue: { type: Number, default: 0 } })
const emit = defineEmits(['update:modelValue'])
const hovered = ref(0)
const { t } = useI18n()
</script>
