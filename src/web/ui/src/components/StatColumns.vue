<template>
  <ul class="flex items-end" :class="compact ? 'gap-0.5 sm:gap-1' : 'gap-1.5 sm:gap-2'">
    <!-- Keyed by position so the same nodes are reused when a year changes: their heights can then animate. -->
    <li v-for="(item, index) in items" :key="index" class="flex-1 min-w-0 flex flex-col items-center gap-1.5" :title="item.title">
      <span class="text-muted h-3.5 truncate max-w-full" :class="compact ? 'text-[8px] sm:text-[10px]' : 'text-[10px]'">{{ item.value > 0 ? item.display ?? item.value : '' }}</span>
      <div class="w-full h-28 flex items-end">
        <div
          v-if="item.segments && item.value > 0"
          class="w-full rounded-t-sm overflow-hidden flex flex-col-reverse transition-[height] duration-300 ease-out motion-reduce:transition-none"
          :style="{ height: barHeight(item) }"
        >
          <div
            v-for="(segment, segmentIndex) in item.segments"
            :key="segmentIndex"
            class="transition-[height] duration-300 ease-out motion-reduce:transition-none"
            :class="segment.barClass"
            :style="{ height: `${(segment.value / item.value) * 100}%` }"
          ></div>
        </div>
        <div
          v-else
          class="w-full rounded-t-sm transition-[height] duration-300 ease-out motion-reduce:transition-none"
          :class="item.value > 0 ? barClass : 'bg-surface-200'"
          :style="{ height: barHeight(item) }"
        ></div>
      </div>
      <span class="text-muted max-w-full" :class="compact ? 'text-[8px] sm:text-[10px]' : 'text-[10px] truncate'">{{ item.label }}</span>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StatColumnItem } from '@/types/stats'

const props = withDefaults(defineProps<{
  items: StatColumnItem[]
  barClass?: string
  compact?: boolean
}>(), {
  barClass: 'bg-brand-500',
  compact: false,
})

const max = computed(() => Math.max(0, ...props.items.map((item) => item.value)))

function barHeight(item: StatColumnItem): string {
  if (item.value <= 0) return '2%'
  const percent = max.value > 0 ? Math.round((item.value / max.value) * 100) : 0
  return `${Math.max(percent, 4)}%`
}
</script>
