<template>
  <aside class="card p-4 space-y-4" :aria-label="t('person_sidebar_label')">
    <h2 class="text-primary font-medium">{{ t('person_sidebar_title') }}</h2>
    <dl class="text-sm space-y-3">
      <div>
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">{{ t('person_known_for') }}</dt>
        <dd class="text-secondary">{{ knownForDepartment || '—' }}</dd>
      </div>
      <div>
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">{{ t('person_known_credits') }}</dt>
        <dd class="text-secondary">{{ knownCredits }}</dd>
      </div>
      <div>
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">{{ t('person_gender') }}</dt>
        <dd class="text-secondary">{{ genderText }}</dd>
      </div>
      <div>
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">{{ t('person_birthday') }}</dt>
        <dd class="text-secondary">{{ birthdayLabel }}</dd>
      </div>
      <div v-if="person?.deathday">
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">{{ t('person_deathday') }}</dt>
        <dd class="text-secondary">{{ formatDateByLocale(person.deathday) || person.deathday }}</dd>
      </div>
      <div>
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">{{ t('person_place_of_birth') }}</dt>
        <dd class="text-secondary">{{ person?.place_of_birth || '—' }}</dd>
      </div>
      <div v-if="alsoKnownAs.length">
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">{{ t('person_also_known_as') }}</dt>
        <dd>
          <ul class="text-secondary space-y-0.5">
            <li v-for="name in alsoKnownAs" :key="name">{{ name }}</li>
          </ul>
        </dd>
      </div>
    </dl>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatDateByLocale, useI18n, type MessageKey } from '@/i18n'
import { ageFor } from '@/utils/person'
import type { PersonDetail } from '@/types/api'

const props = withDefaults(defineProps<{
  person?: PersonDetail | null
  knownCredits?: number
}>(), { person: null, knownCredits: 0 })

const { t } = useI18n()

const GENDER_KEYS: Record<number, MessageKey> = {
  1: 'person_gender_female',
  2: 'person_gender_male',
  3: 'person_gender_non_binary',
}

const knownForDepartment = computed(() => props.person?.known_for_department || '')
const alsoKnownAs = computed(() => props.person?.also_known_as ?? [])

const genderText = computed(() => {
  const gender = props.person?.gender
  const key = typeof gender === 'number' ? GENDER_KEYS[gender] : undefined
  return key ? t(key) : '—'
})

const birthdayLabel = computed(() => {
  const birthday = props.person?.birthday
  if (!birthday) return '—'
  const formatted = formatDateByLocale(birthday) || birthday
  const age = ageFor(birthday, props.person?.deathday || undefined)
  return age === null ? formatted : t('person_birthday_with_age', { date: formatted, age })
})
</script>
