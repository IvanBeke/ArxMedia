<template>
  <aside class="card p-4 space-y-4" aria-label="Personal info">
    <h2 class="text-primary font-medium">Personal Info</h2>
    <dl class="text-sm space-y-3">
      <div>
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">Known For</dt>
        <dd class="text-secondary">{{ knownForDepartment || '—' }}</dd>
      </div>
      <div>
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">Known Credits</dt>
        <dd class="text-secondary">{{ knownCredits }}</dd>
      </div>
      <div>
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">Gender</dt>
        <dd class="text-secondary">{{ genderLabel(person?.gender) }}</dd>
      </div>
      <div>
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">Birthday</dt>
        <dd class="text-secondary">{{ birthdayLabel }}</dd>
      </div>
      <div v-if="person?.deathday">
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">Deathday</dt>
        <dd class="text-secondary">{{ formatDateByLocale(person.deathday) || person.deathday }}</dd>
      </div>
      <div>
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">Place of Birth</dt>
        <dd class="text-secondary">{{ person?.place_of_birth || '—' }}</dd>
      </div>
      <div v-if="alsoKnownAs.length">
        <dt class="text-muted text-xs uppercase tracking-wider mb-0.5">Also Known As</dt>
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
import { formatDateByLocale } from '@/i18n'
import { ageFor, genderLabel } from '@/utils/person'
import type { PersonDetail } from '@/types/api'

const props = withDefaults(defineProps<{
  person?: PersonDetail | null
  knownCredits?: number
}>(), { person: null, knownCredits: 0 })

const knownForDepartment = computed(() => props.person?.known_for_department || '')
const alsoKnownAs = computed(() => props.person?.also_known_as ?? [])

const birthdayLabel = computed(() => {
  const birthday = props.person?.birthday
  if (!birthday) return '—'
  const formatted = formatDateByLocale(birthday) || birthday
  const age = ageFor(birthday, props.person?.deathday || undefined)
  return age === null ? formatted : `${formatted} (${age} years old)`
})
</script>
