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
          <p v-else class="text-muted text-sm">{{ t('person_no_bio') }}</p>
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
          <section :aria-label="t('person_known_for_label')">
            <h2 class="text-primary font-medium mb-3">{{ t('person_known_for') }}</h2>
            <PersonKnownForScroller :items="knownFor" />
          </section>

          <section :aria-label="t('person_acting_label')">
            <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
              <h2 class="text-primary font-medium">{{ t('person_acting') }}{{ actingCount ? ` (${actingCount})` : '' }}</h2>
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
            <p v-if="creditsError" class="text-sm text-muted">{{ t('common_recs_unavailable') }}</p>
            <PersonFilmographyList v-else :items="actingCredits" :media-filter="actingFilter" :empty-label="t('person_no_acting_credits')" />
          </section>

          <section v-if="crewCredits.length" :aria-label="t('person_crew_label')">
            <h2 class="text-primary font-medium mb-3">{{ t('person_crew') }}{{ crewCredits.length ? ` (${crewCredits.length})` : '' }}</h2>
            <PersonFilmographyList :items="crewCredits" media-filter="all" :empty-label="t('person_no_filmography')" />
          </section>

          <p v-if="!loadingCredits && !creditsError && !actingCount && !crewCredits.length" class="text-sm text-muted">
            {{ t('person_no_filmography') }}
          </p>
        </div>
      </div>
    </div>

    <div v-if="!loading && !person" class="max-w-3xl mx-auto px-4 pb-20">
      <LoadError :message="pageError || t('error_load_person')" @retry="loadPerson" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from '@/i18n'
import { useRoute } from 'vue-router'
import { mediaAPI } from '@/api'
import DetailHero from '@/components/DetailHero.vue'
import LoadError from '@/components/LoadError.vue'
import { getApiErrorMessage } from '@/utils/errors'
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
const { t } = useI18n()
const personId = computed(() => String(route.params.id ?? ''))
const person = ref<PersonDetail | null>(null)
const credits = ref<PersonCombinedCredits | null>(null)
const loading = ref(true)
const loadingCredits = ref(true)
const creditsError = ref(false)
const pageError = ref('')
const biographyExpanded = ref(false)
const actingFilter = ref<PersonMediaFilter>('all')

const mediaFilterOptions: { label: string; value: PersonMediaFilter }[] = [
  { label: t('person_filter_all'), value: 'all' },
  { label: t('person_filter_movies'), value: MEDIA_TYPE.MOVIE },
  { label: t('person_filter_tv'), value: MEDIA_TYPE.TV },
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

async function loadPerson() {
  loading.value = true
  pageError.value = ''
  try {
    person.value = await mediaAPI.getPerson(personId.value)
  } catch (error: unknown) {
    pageError.value = getApiErrorMessage(error, t('error_load_person'))
    person.value = null
    return
  } finally {
    loading.value = false
  }
  loadingCredits.value = true
  creditsError.value = false
  try {
    credits.value = await mediaAPI.getPersonCredits(personId.value)
  } catch {
    creditsError.value = true
  } finally {
    loadingCredits.value = false
  }
}

onMounted(loadPerson)
</script>
