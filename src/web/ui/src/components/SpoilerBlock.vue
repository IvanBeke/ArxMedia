<template>
  <button
    type="button"
    class="w-full text-left rounded"
    :class="shouldBlur ? 'spoiler-blur' : ''"
    @click="reveal"
    :aria-label="shouldBlur ? t('spoiler_reveal_label') : t('spoiler_visible_label')"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from '@/i18n'
import { usePreferencesStore } from '@/stores/preferences'

const props = withDefaults(defineProps<{
  itemKey: string
  watched?: boolean
}>(), {
  watched: false,
})

const { t } = useI18n()
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
