<template>
  <form class="space-y-4" @submit.prevent="emit('submit', { ...options })">
    <p class="text-sm text-primary">{{ message }}</p>
    <div class="space-y-2">
      <label class="flex items-center gap-2 text-sm text-secondary">
        <input v-model="options.delete_files" type="checkbox" class="accent-brand-500">
        {{ deleteFilesLabel }}
      </label>
      <label class="flex items-center gap-2 text-sm text-secondary">
        <input v-model="options.add_import_exclusion" type="checkbox" class="accent-brand-500">
        {{ t('arr_add_exclusion') }}
      </label>
    </div>

    <p v-if="error" role="alert" class="px-3 py-2 rounded-md text-sm bg-red-500/10 border border-red-500/20 text-red-400">{{ error }}</p>

    <div class="flex gap-3 pt-1">
      <button type="button" class="btn-ghost flex-1" :disabled="submitting" @click="emit('back')">{{ t('arr_back') }}</button>
      <button
        type="submit"
        class="btn-ghost flex-1 border-red-500/40 text-red-300 hover:bg-red-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="submitting"
      >
        {{ submitting ? t('arr_removing') : t('arr_remove_action') }}
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { useI18n } from '@/i18n'
import type { ArrRemovePayload } from '@/types/api'

withDefaults(defineProps<{
  message: string
  deleteFilesLabel: string
  submitting?: boolean
  error?: string
}>(), { submitting: false, error: '' })

const emit = defineEmits<{ back: []; submit: [options: ArrRemovePayload] }>()

const { t } = useI18n()
const options = reactive<ArrRemovePayload>({ delete_files: false, add_import_exclusion: false })
</script>
