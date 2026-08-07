<template>
  <button
    type="button"
    class="w-full text-left rounded"
    :class="shouldBlur ? 'spoiler-blur' : ''"
    @click="reveal"
    :aria-label="shouldBlur ? 'Reveal hidden spoiler content' : 'Content visible'"
  >
    <slot />
  </button>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { usePreferencesStore } from '@/stores/preferences'

const props = defineProps({
  itemKey: { type: String, required: true },
  watched: { type: Boolean, default: false },
})

const prefs = usePreferencesStore()
const revealed = ref(false)

watch(() => props.itemKey, () => {
  revealed.value = false
})

const shouldBlur = computed(() => prefs.spoilerMode && !props.watched && !revealed.value)

function reveal() {
  if (shouldBlur.value) {
    revealed.value = true
  }
}
</script>
