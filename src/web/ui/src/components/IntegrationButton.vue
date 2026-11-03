<template>
  <button
    type="button"
    class="inline-flex items-center gap-2 h-9 px-4 text-sm font-medium rounded-lg border bg-transparent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    :class="active ? brand.activeClass : brand.idleClass"
  >
    <span>{{ label }}</span>
    <img :src="brand.icon" alt="" class="w-4 h-4 object-contain" aria-hidden="true">
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { INTEGRATION_BRANDS, type IntegrationService } from '@/constants/integrations'

const props = withDefaults(defineProps<{
  service: IntegrationService
  label: string
  active?: boolean
}>(), { active: false })

const brand = computed(() => INTEGRATION_BRANDS[props.service])
</script>
