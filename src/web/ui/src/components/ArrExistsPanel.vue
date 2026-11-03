<template>
  <div class="space-y-4">
    <div class="rounded-lg border border-surface-200 bg-surface px-4 py-3">
      <p class="text-sm text-primary">{{ message }}</p>
      <p v-if="path" class="text-xs text-muted mt-1 break-all">{{ path }}</p>
    </div>
    <div class="flex flex-col gap-3 sm:flex-row">
      <a
        v-if="url"
        :href="url"
        target="_blank"
        rel="noopener noreferrer"
        class="btn-ghost flex-1 inline-flex items-center justify-center gap-2 text-center"
      >
        {{ openLabel }}
        <ExternalLink class="w-4 h-4" aria-hidden="true" />
      </a>
      <button type="button" class="btn-ghost flex-1 border-red-500/40 text-red-300 hover:bg-red-500/10" @click="emit('remove')">
        {{ removeLabel }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ExternalLink } from '@lucide/vue'

withDefaults(defineProps<{
  message: string
  path?: string
  url?: string
  openLabel: string
  removeLabel: string
}>(), { path: '', url: '' })

const emit = defineEmits<{ remove: [] }>()
</script>
