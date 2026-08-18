<template>
  <div class="flex items-center gap-1" role="radiogroup" :aria-label="t('rating_group_label')">
    <button
      v-for="n in 10"
      :key="n"
      @click="emit('update:modelValue', n)"
      @mouseenter="hovered = n"
      @mouseleave="hovered = 0"
      @focus="hovered = n"
      @blur="hovered = 0"
      class="relative transition-transform hover:scale-110"
      type="button"
      role="radio"
      :aria-checked="modelValue === n ? 'true' : 'false'"
      :aria-label="t('rating_item_label', { value: n })"
    >
      <span
        v-if="hovered === n"
        class="pointer-events-none absolute -translate-y-8 -translate-x-1/2 left-1/2 whitespace-nowrap rounded-md border border-surface-200 bg-surface-100 px-1.5 py-0.5 text-[10px] font-semibold text-primary shadow-lg"
      >
        {{ n }}/10
      </span>
      <svg
        class="w-5 h-5 transition-colors"
        :class="(hovered || modelValue) >= n ? 'text-amber-500' : 'text-surface-300'"
        fill="currentColor"
        viewBox="0 0 24 24"
      >
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
      </svg>
    </button>
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
