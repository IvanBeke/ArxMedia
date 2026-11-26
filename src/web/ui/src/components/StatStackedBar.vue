<template>
  <div>
    <div class="flex h-4 rounded-full overflow-hidden bg-surface-200">
      <div
        v-for="slice in slices"
        :key="slice.key"
        class="h-full bg-current min-w-1 transition-[width] duration-300 ease-out motion-reduce:transition-none"
        :class="slice.colorClass"
        :style="{ width: `${slice.share}%` }"
        :title="`${slice.label}: ${slice.display ?? slice.value} (${slice.percent}%)`"
      ></div>
    </div>
    <StatLegend :slices="slices" class="mt-3 flex flex-wrap gap-x-6 gap-y-2" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import StatLegend from '@/components/StatLegend.vue'
import { toSlices } from '@/utils/statShares'
import type { StatSliceInput } from '@/types/stats'

const props = defineProps<{ items: StatSliceInput[] }>()

const slices = computed(() => toSlices(props.items))
</script>
