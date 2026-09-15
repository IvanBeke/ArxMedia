<template>
  <div>
    <div v-if="!bare" class="relative h-72 md:h-[28rem]">
      <img v-if="backdropUrl" :src="backdropUrl" :alt="backdropAlt" class="w-full h-full object-cover" />
      <div class="absolute inset-0 bg-gradient-to-t from-surface via-surface/60 to-transparent"></div>
      <div class="absolute inset-0 bg-gradient-to-r from-surface/80 to-transparent"></div>
    </div>

    <div
      class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10"
      :class="bare ? 'py-8' : '-mt-60 md:-mt-96 pb-8'"
    >
      <div class="flex flex-col md:flex-row gap-8">
        <div class="flex-shrink-0">
          <div class="w-36 md:w-48 rounded-md overflow-hidden shadow-2xl border border-surface-200">
            <img v-if="posterUrl" :src="posterUrl" :alt="posterAlt" class="w-full" />
            <div v-else class="aspect-[2/3] bg-surface-200 flex flex-col items-center justify-center text-gray-500 p-4">
              <span class="text-xs text-center">{{ posterAlt }}</span>
            </div>
          </div>
          <div v-if="$slots.posterBelow" class="mt-3">
            <slot name="posterBelow" />
          </div>
        </div>

        <div class="flex-1 pt-2 min-w-0">
          <div v-if="loading" class="space-y-3">
            <div class="h-10 w-3/4 skeleton rounded-md"></div>
            <div class="h-4 w-1/2 skeleton rounded-md"></div>
            <div class="h-20 skeleton rounded-md"></div>
          </div>
          <template v-else>
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <slot name="eyebrow" />
                <slot name="title" />
                <slot name="meta" />
              </div>
              <slot name="overflow" />
            </div>
            <slot name="badges" />
            <slot name="description" />
            <slot name="links" />
            <slot name="actions" />
            <slot name="belowActions" />
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  backdropUrl?: string | null
  backdropAlt?: string
  posterUrl?: string | null
  posterAlt?: string
  loading?: boolean
  bare?: boolean
}>(), { backdropUrl: null, backdropAlt: '', posterUrl: null, posterAlt: '', loading: false, bare: false })
</script>
