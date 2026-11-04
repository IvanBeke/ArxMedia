<template>
  <img
    v-if="src"
    :src="src"
    :alt="t('avatar_alt', { username })"
    class="rounded-full object-cover border-surface-200 flex-shrink-0"
    :class="sizeClasses[size].box"
    loading="lazy"
  />
  <div
    v-else
    class="rounded-full bg-brand-500/20 border-brand-500/30 text-brand-300 font-semibold flex items-center justify-center flex-shrink-0"
    :class="[sizeClasses[size].box, sizeClasses[size].text]"
  >
    {{ initial }}
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '@/i18n'

type AvatarSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

const props = withDefaults(defineProps<{
  username: string
  src?: string | null
  size?: AvatarSize
}>(), { src: null, size: 'md' })

const { t } = useI18n()
const initial = computed(() => (props.username[0] || '?').toUpperCase())

const sizeClasses: Record<AvatarSize, { box: string; text: string }> = {
  xs: { box: 'h-6 w-6 border', text: 'text-[10px]' },
  sm: { box: 'h-7 w-7 border', text: 'text-xs' },
  md: { box: 'h-8 w-8 border', text: 'text-xs' },
  lg: { box: 'h-16 w-16 border-2', text: 'text-2xl' },
  xl: { box: 'h-24 w-24 border-2', text: 'text-3xl' },
}
</script>
