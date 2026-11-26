<template>
  <div v-if="loading" class="skeleton rounded-md" :class="skeletonClass"></div>
  <div v-else-if="error" role="alert" class="text-center py-4">
    <p class="text-muted text-sm mb-3">{{ t('error_load_stats') }}</p>
    <button type="button" class="btn-ghost text-xs border border-surface-200 bg-surface-100/70 hover:bg-surface-100" @click="emit('retry')">
      {{ t('action_try_again') }}
    </button>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
import { useI18n } from '@/i18n'

withDefaults(defineProps<{
  loading?: boolean
  error?: boolean
  /** Size of the skeleton; the default is a block, `flex-1` fills a flex column. */
  skeletonClass?: string
}>(), {
  skeletonClass: 'h-32',
})
const emit = defineEmits<{ retry: [] }>()

const { t } = useI18n()
</script>
