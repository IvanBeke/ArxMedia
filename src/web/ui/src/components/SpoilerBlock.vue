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

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { usePreferencesStore } from '@/stores/preferences'

const props = withDefaults(defineProps<{
  itemKey: string
  watched?: boolean
}>(), {
  watched: false,
})

const prefs = usePreferencesStore()
const revealed = ref<boolean>(false)

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
