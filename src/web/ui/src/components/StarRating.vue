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
      <Star
        class="w-5 h-5 transition-colors"
        :class="(hovered || modelValue) >= n ? 'text-amber-500' : 'text-surface-300'"
        fill="currentColor"
        :stroke-width="0"
      />
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from '@/i18n'
import { Star } from '@lucide/vue'

withDefaults(defineProps<{
  modelValue?: number
}>(), {
  modelValue: 0,
})
const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()
const hovered = ref<number>(0)
const { t } = useI18n()
</script>
