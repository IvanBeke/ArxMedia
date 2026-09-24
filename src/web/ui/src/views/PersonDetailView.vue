<template>
  <div>
    <DetailHero
      :poster-url="person?.profile_url ?? null"
      :poster-alt="person?.name"
      :loading="loading"
    >
      <template #eyebrow>
        <div v-if="person?.known_for_department" class="flex flex-wrap gap-2 mb-3">
          <span class="badge bg-surface-200 text-secondary text-xs">{{ person.known_for_department }}</span>
        </div>
      </template>
      <template #title>
        <h1 v-if="person" class="font-display text-3xl md:text-5xl text-primary font-semibold mb-1">{{ person.name }}</h1>
      </template>
      <template #meta>
        <p v-if="person && heroMeta" class="text-gray-500 text-sm mb-1">
          {{ heroMeta }}
        </p>
      </template>
      <template #description>
        <div v-if="person" class="mt-4 mb-4 max-w-2xl">
          <p v-if="biographyFull" class="text-secondary leading-relaxed whitespace-pre-line">
            {{ biographyText }}
          </p>
          <p v-else class="text-muted text-sm">No biography available.</p>
          <button
            v-if="isBiographyTruncated || biographyExpanded"
            type="button"
            class="mt-2 text-sm text-brand-400 hover:text-brand-300"
            :aria-expanded="biographyExpanded"
            @click="biographyExpanded = !biographyExpanded"
          >
            {{ biographyExpanded ? 'Read Less' : 'Read More' }}
          </button>
        </div>
      </template>
      <template #links>
        <ExternalLinks
          v-if="person"
          :tmdb-url="externalLinks.tmdbUrl"
          :tvmaze-url="externalLinks.tvmazeUrl"
          :imdb-url="externalLinks.imdbUrl"
          class="mb-4"
        />
      </template>
    </DetailHero>

    <div v-if="!loading && person" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-20">
      <div class="grid gap-8 md:grid-cols-[260px_minmax(0,1fr)] items-start">
        <PersonSidebar :person="person" :known-credits="knownCredits" class="self-start" />

        <div class="min-w-0 space-y-10">
          <section aria-label="Known for">
            <h2 class="text-primary font-medium mb-3">Known For</h2>
            <PersonKnownForScroller :items="knownFor" />
          </section>

          <section aria-label="Acting filmography">
            <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
              <h2 class="text-primary font-medium">Acting{{ actingCount ? ` (${actingCount})` : '' }}</h2>
              <div class="flex gap-1.5" role="group" aria-label="Filter acting by media type">
                <button
                  v-for="option in mediaFilterOptions"
                  :key="option.value"
                  type="button"
                  class="px-2.5 py-1 rounded-md text-xs border transition-colors"
                  :class="actingFilter === option.value
                    ? 'border-brand-400 text-primary bg-surface-200'
                    : 'border-surface-200 text-muted hover:text-primary hover:bg-surface-200'"
                  :aria-pressed="actingFilter === option.value"
                  @click="actingFilter = option.value"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>
            <p v-if="loadError" class="text-sm text-muted">Filmography unavailable right now.</p>
            <PersonFilmographyList v-else :items="actingCredits" :media-filter="actingFilter" empty-label="No acting credits available." />
          </section>

          <section v-if="crewCredits.length" aria-label="Crew filmography">
            <h2 class="text-primary font-medium mb-3">Crew{{ crewCredits.length ? ` (${crewCredits.length})` : '' }}</h2>
            <PersonFilmographyList :items="crewCredits" media-filter="all" empty-label="No crew credits available." />
          </section>

          <p v-if="!loadingCredits && !loadError && !actingCount && !crewCredits.length" class="text-sm text-muted">
            No filmography available.
          </p>
        </div>
      </div>
    </div>

    <div v-if="!loading && !person" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-20">
      <p class="text-sm text-muted">Actor not found.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { mediaAPI } from '@/api'
import DetailHero from '@/components/DetailHero.vue'
import ExternalLinks from '@/components/ExternalLinks.vue'
import PersonFilmographyList from '@/components/PersonFilmographyList.vue'
import PersonKnownForScroller from '@/components/PersonKnownForScroller.vue'
import PersonSidebar from '@/components/PersonSidebar.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { formatDateByLocale } from '@/i18n'
import { personExternalLinks } from '@/utils/externalLinks'
import { ageFor, knownCreditsCount, topKnownFor, truncateAtWord, type PersonMediaFilter } from '@/utils/person'
import type { PersonCombinedCredits, PersonDetail } from '@/types/api'

const BIOGRAPHY_PREVIEW_LENGTH = 600

const route = useRoute()
const personId = computed(() => String(route.params.id ?? ''))
const person = ref<PersonDetail | null>(null)
const credits = ref<PersonCombinedCredits | null>(null)
const loading = ref(true)
const loadingCredits = ref(true)
const loadError = ref(false)
const biographyExpanded = ref(false)
const actingFilter = ref<PersonMediaFilter>('all')

const mediaFilterOptions: { label: string; value: PersonMediaFilter }[] = [
  { label: 'All', value: 'all' },
  { label: 'Movies', value: MEDIA_TYPE.MOVIE },
  { label: 'TV Shows', value: MEDIA_TYPE.TV },
]

const externalLinks = computed(() => personExternalLinks(personId.value, person.value?.external_ids))

const heroMeta = computed(() => {
  const birthday = person.value?.birthday
  if (!birthday) return ''
  const formatted = formatDateByLocale(birthday) || birthday
  const age = ageFor(birthday, person.value?.deathday || undefined)
  return age === null ? formatted : `${formatted} (${age} years old)`
})

const biographyFull = computed(() => (person.value?.biography || '').trim())

const biographyText = computed(() => {
  if (biographyExpanded.value) return biographyFull.value
  return truncateAtWord(biographyFull.value, BIOGRAPHY_PREVIEW_LENGTH)
})

const isBiographyTruncated = computed(() => biographyFull.value.length > BIOGRAPHY_PREVIEW_LENGTH)

const actingCredits = computed(() => credits.value?.cast ?? [])
const crewCredits = computed(() => credits.value?.crew ?? [])
const actingCount = computed(() => actingCredits.value.length)
const knownCredits = computed(() => knownCreditsCount(credits.value))
const knownFor = computed(() => topKnownFor(actingCredits.value, 8))

onMounted(async () => {
  try {
    person.value = await mediaAPI.getPerson(personId.value)
  } catch (e) {
    console.error('Failed to load person:', e)
    person.value = null
  } finally {
    loading.value = false
  }
  try {
    credits.value = await mediaAPI.getPersonCredits(personId.value)
  } catch (e) {
    console.error('Failed to load person credits:', e)
    loadError.value = true
  } finally {
    loadingCredits.value = false
  }
})
</script>
