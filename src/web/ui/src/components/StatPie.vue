<template>
  <div class="flex flex-col sm:flex-row items-center gap-6">
    <svg viewBox="0 0 32 32" class="w-36 h-36 shrink-0 -rotate-90" aria-hidden="true">
      <circle
        v-for="slice in slices"
        :key="slice.key"
        cx="16"
        cy="16"
        r="8"
        fill="none"
        stroke="currentColor"
        stroke-width="16"
        pathLength="100"
        :stroke-dasharray="`${slice.share} ${100 - slice.share}`"
        :stroke-dashoffset="-slice.offset"
        :class="slice.colorClass"
      />
    </svg>
    <StatLegend :slices="slices" class="space-y-2 min-w-0" />
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
