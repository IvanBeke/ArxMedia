<template>
  <div class="relative">
    <div v-if="$slots.default" class="flex flex-wrap gap-2 mb-4">
      <slot />
    </div>
    <div v-if="$slots.rating" class="mb-4">
      <p class="text-xs text-gray-500 mb-1.5 uppercase tracking-wider">{{ t('media_actions_your_rating') }}</p>
      <slot name="rating" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from '@/i18n'

const { t } = useI18n()
</script>
