<template>
  <div class="relative inline-block" ref="menuRootRef">
    <button
      type="button"
      class="cursor-pointer transition-colors"
      :class="resolvedButtonClass"
      :title="resolvedButtonTitle"
      :aria-label="resolvedButtonAriaLabel"
      :aria-expanded="menuVisible ? 'true' : 'false'"
      aria-haspopup="menu"
      :disabled="disabled"
      :data-pulsing="pulsing ? 'true' : 'false'"
      @click.stop="toggleMenu"
    >
      <slot />
    </button>

    <div
      v-if="menuVisible"
      class="absolute left-0 mt-1 min-w-[140px] bg-surface border border-surface-200 rounded-md shadow-lg z-50"
      :class="menuClass"
      role="menu"
    >
      <button
        v-for="opt in menuOptions"
        :key="opt.value"
        type="button"
        class="block w-full px-3 py-2 text-left text-sm text-muted hover:bg-surface-200 hover:text-primary transition-colors cursor-pointer border-none bg-transparent"
        role="menuitem"
        @click.stop="selectOption(opt.value)"
      >
        {{ opt.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { useI18n } from '@/i18n'

const props = defineProps({
  releaseDate: { type: String, default: '' },
  buttonTitle: { type: String, default: '' },
  buttonAriaLabel: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  pulsing: { type: Boolean, default: false },
  buttonClass: { type: String, default: '' },
  menuClass: { type: String, default: '' },
})

const emit = defineEmits(['select'])
const menuVisible = ref(false)
const menuRootRef = ref(null)
const { t } = useI18n()
const resolvedButtonAriaLabel = computed(() => props.buttonAriaLabel || t('watch_options'))
const resolvedButtonTitle = computed(() => props.buttonTitle || resolvedButtonAriaLabel.value)
const resolvedButtonClass = computed(() => {
  if (props.buttonClass) {
    return props.buttonClass
  }
  return 'p-1 rounded hover:bg-surface-200 text-muted hover:text-brand-400 border-none bg-transparent'
})

const menuOptions = computed(() => {
  const options = [{ label: t('watch_option_now'), value: 'now' }]
  if (props.releaseDate) {
    options.push({ label: t('watch_option_release'), value: 'release' })
  }
  options.push({ label: t('watch_option_date'), value: 'date' })
  return options
})

function toggleMenu() {
  if (props.disabled) {
    return
  }
  menuVisible.value = !menuVisible.value
}

function selectOption(value) {
  menuVisible.value = false
  emit('select', value)
}

onClickOutside(menuRootRef, () => {
  menuVisible.value = false
})
</script>
