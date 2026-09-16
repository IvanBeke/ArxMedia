<template>
  <div class="border-b border-surface-200 overflow-x-auto">
    <nav class="flex gap-6 whitespace-nowrap min-h-[44px]" role="tablist" :aria-label="ariaLabel" @keydown="onKeydown">
      <button
        v-for="(tab, index) in tabs"
        :key="tab.id"
        ref="tabRefs"
        type="button"
        role="tab"
        :id="`tab-${tab.id}`"
        :aria-selected="tab.id === modelValue"
        :aria-controls="`tabpanel-${tab.id}`"
        :tabindex="tab.id === modelValue ? 0 : -1"
        class="pb-3 text-sm font-medium transition-colors shrink-0 min-h-[44px]"
        :class="tab.id === modelValue ? 'tab-active' : 'tab-inactive'"
        :title="tab.tooltip || undefined"
        @click="select(tab.id)"
      >
        {{ tab.label }}
        <span v-if="typeof tab.count === 'number'" class="ml-1.5 text-xs text-muted">({{ tab.count }})</span>
      </button>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

export interface MediaTab {
  id: string
  label: string
  count?: number
  tooltip?: string
}

const props = withDefaults(defineProps<{
  tabs: MediaTab[]
  modelValue: string
  ariaLabel?: string
}>(), { ariaLabel: 'Detail sections' })

const emit = defineEmits<{ 'update:modelValue': [id: string] }>()

const tabRefs = ref<HTMLElement[]>([])

function select(id: string) {
  if (id !== props.modelValue) emit('update:modelValue', id)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
  event.preventDefault()
  const ids = props.tabs.map((t) => t.id)
  const current = ids.indexOf(props.modelValue)
  const delta = event.key === 'ArrowRight' ? 1 : -1
  const next = ids[(current + delta + ids.length) % ids.length]
  if (!next) return
  select(next)
  const nextIndex = ids.indexOf(next)
  tabRefs.value[nextIndex]?.focus()
}
</script>
