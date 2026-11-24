<template>
  <div class="relative inline-block" ref="rootRef">
    <div class="inline-flex" role="group" :aria-label="groupLabel">
      <button
        type="button"
        class="inline-flex items-center gap-2 h-9 pl-4 pr-3 py-2 text-sm font-medium rounded-l-md border transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        :class="mainVisualClass"
        :title="titleText"
        :disabled="disabled || loading"
        @click="emit('trigger')"
      >
        <X v-if="isDanger" class="w-4 h-4" aria-hidden="true" />
        <Check v-else-if="active" class="w-4 h-4" />
        <Plus v-else class="w-4 h-4" aria-hidden="true" />
        {{ label }}
      </button>
      <button
        type="button"
        class="inline-flex items-center h-9 px-2.5 py-2 rounded-r-md border transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        :class="[chevronVisualClass, dividerClass]"
        :title="t('watch_options')"
        :aria-label="t('watch_options')"
        aria-haspopup="menu"
        :aria-expanded="menuOpen"
        :disabled="disabled || loading"
        @click="menuOpen = !menuOpen"
        @keydown.escape="menuOpen = false"
      >
        <ChevronDown class="w-3.5 h-3.5 transition-transform" :class="menuOpen ? 'rotate-180' : ''" aria-hidden="true" />
      </button>
    </div>

    <div
      v-if="menuOpen"
      class="absolute left-0 mt-1 min-w-[180px] bg-surface border border-surface-200 rounded-md shadow-lg z-50 p-1"
      role="menu"
    >
      <button
        v-for="opt in dateOptions"
        :key="opt.value"
        type="button"
        class="block w-full px-3 py-2 text-left text-sm text-muted hover:bg-surface-200 hover:text-primary transition-colors rounded"
        role="menuitem"
        @click="selectOption(opt.value)"
      >
        {{ opt.label }}
      </button>
      <div v-if="$slots.menuFooter" class="border-t border-surface-200 mt-1 pt-1">
        <slot name="menuFooter" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { Check, ChevronDown, Plus, X } from '@lucide/vue'
import { useI18n } from '@/i18n'
import type { WatchedAtOption } from '@/utils/watchOptions'

const props = withDefaults(defineProps<{
  label: string
  active?: boolean
  variant?: 'default' | 'danger'
  releaseDate?: string
  titleText?: string
  groupLabel?: string
  disabled?: boolean
  loading?: boolean
}>(), {
  active: false, variant: 'default', releaseDate: '', titleText: '', groupLabel: '', disabled: false, loading: false,
})

const emit = defineEmits<{
  trigger: []
  select: [option: WatchedAtOption]
}>()

const { t } = useI18n()
const menuOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const idleMainClass = 'border-surface-200 bg-transparent text-primary hover:bg-surface-200'
const idleChevronClass = 'border-surface-200 bg-transparent text-muted hover:bg-surface-200 hover:text-primary'
const activeMainClass = 'border-white/25 bg-brand-500 text-white hover:bg-brand-600'
const activeChevronClass = 'border-white/25 bg-brand-500 text-white hover:bg-brand-600'
const dangerMainClass = 'border-red-500/60 bg-transparent text-red-400 hover:bg-red-500/10'
const dangerChevronClass = 'border-red-500/60 bg-transparent text-red-400 hover:bg-red-500/10'

const isDanger = computed(() => props.variant === 'danger')
const mainVisualClass = computed(() => isDanger.value ? dangerMainClass : props.active ? activeMainClass : idleMainClass)
const chevronVisualClass = computed(() => isDanger.value ? dangerChevronClass : props.active ? activeChevronClass : idleChevronClass)
const dividerClass = computed(() => {
  if (isDanger.value) return 'border-l-red-500/40'
  if (props.active) return 'border-l-white/25'
  return 'border-l-0'
})

const dateOptions = computed<{ label: string; value: WatchedAtOption }[]>(() => {
  const options: { label: string; value: WatchedAtOption }[] = [{ label: t('watch_option_now'), value: 'now' }]
  if (props.releaseDate) {
    options.push({ label: t('watch_option_release'), value: 'release' })
  }
  options.push({ label: t('watch_option_unknown'), value: 'unknown' })
  options.push({ label: t('watch_option_date'), value: 'date' })
  return options
})

function selectOption(option: WatchedAtOption) {
  menuOpen.value = false
  emit('select', option)
}

onClickOutside(rootRef, () => {
  menuOpen.value = false
})
</script>
