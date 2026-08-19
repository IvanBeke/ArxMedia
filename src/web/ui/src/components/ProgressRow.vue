<template>
  <article class="card p-3 md:p-4 progress-row-deferred">
    <div class="progress-row-grid" :class="hasNextEpisode(item) ? 'row-with-episode' : 'row-no-episode'">
      <section class="show-section">
        <RouterLink :to="`/tv/${item.tmdb_id}`" class="w-[113px] h-[170px] rounded-md overflow-hidden bg-surface-200 flex-shrink-0 border border-surface-200">
          <img v-if="item.poster_url" :src="item.poster_url" :alt="item.show_name" class="w-full h-full object-cover" loading="lazy">
        </RouterLink>
        <div class="show-main min-w-0">
          <div class="show-title-row">
            <RouterLink :to="`/tv/${item.tmdb_id}`" class="block text-xl leading-tight font-display text-primary font-semibold hover:text-brand-400 truncate">{{ item.show_name }}</RouterLink>
          </div>

          <div class="show-meta-row mt-1">
            <p class="show-meta-left text-xs text-muted">
                <span class="status-pill" :class="statusClass(item.status)">{{ statusText(item.status) }}</span>
                <UserRating v-if="item.user_rating" :value="item.user_rating" size="xs" />
                <RatingBadge v-if="hasProviderRating(item.vote_average)" :value="item.vote_average" size="xs" out-of-ten />
                <span class="meta-separator" aria-hidden="true">·</span>
                <span class="meta-text">{{ providerShowStatus(item.provider_status) }}</span>
                <span class="meta-separator" aria-hidden="true">·</span>
                <span class="meta-text">{{ minutesPerEpisode(item) }}</span>
            </p>
            <div class="show-headline-meta">
              <div class="show-headline-actions">
                <details class="control-menu">
                  <summary class="row-pill-trigger" title="Manage" aria-label="Manage show">
                    <span>Manage</span>
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                    </svg>
                  </summary>
                  <div class="control-panel right-0 w-52 p-1.5 menu-panel">
                    <button
                      type="button"
                      class="control-option"
                      :disabled="rowBusyId === item.tmdb_id"
                      @click="emit('open-rate', item)"
                    >
                      Rate
                    </button>
                    <button type="button" class="control-option" :disabled="rowBusyId === item.tmdb_id" @click="emit('open-add-to-list', item)">
                      Add to list
                    </button>
                    <button
                      type="button"
                      class="control-option control-option-danger"
                      :disabled="rowBusyId === item.tmdb_id"
                      @click="emit('drop', item.tmdb_id)"
                    >
                      Drop show
                    </button>
                  </div>
                </details>
              </div>
              <p class="show-percent text-2xl font-display text-primary font-semibold">{{ item.progress_percent }}%</p>
            </div>
          </div>

          <div class="mb-3 mt-2">
            <ProgressBar :pct="item.progress_percent" class="progress-row-bar mb-1.5" />
            <p class="text-xs text-muted">{{ progressFraction(item) }} watched · {{ item.episodes_left }} episodes left · {{ formatTimeLeft(item) }} left</p>
          </div>

          <div class="stats-inline">
            <div class="stats-inline-item">
              <p class="stats-inline-label">Last watched</p>
              <p class="stats-inline-value stats-value-with-pill">
                <EpisodeCodePill
                  v-if="hasLastWatchedEpisodeCode(item)"
                  :season-number="item.last_watched_episode?.season_number"
                  :episode-number="item.last_watched_episode?.episode_number"
                  variant="pill"
                  size="xs"
                  class="last-watched-pill"
                />
                <span>{{ formatCompactDate(item.last_watched_at) }}</span>
              </p>
            </div>
            <div class="stats-inline-item">
              <p class="stats-inline-label">Started</p>
              <p class="stats-inline-value">{{ inferredStarted(item.started_at) }}</p>
            </div>
          </div>

          <p class="mt-2 text-[11px] text-muted truncate">{{ item.genres.join(', ') }}<span v-if="item.networks.length"> · {{ item.networks.join(', ') }}</span></p>
        </div>
      </section>

      <section v-if="hasNextEpisode(item)" class="episode-section">
        <div>
          <p class="episode-kicker">Next episode</p>
          <EpisodeCodePill
            as="RouterLink"
            :to="episodeLink(item)"
            :season-number="item.next_episode?.season_number"
            :episode-number="item.next_episode?.episode_number"
            variant="pill"
            class="episode-code"
          />
          <EpisodeTypePill :value="item.next_episode?.episode_type" class="episode-type" />
          <p class="episode-title" :title="item.next_episode?.name || ''">{{ item.next_episode?.name }}</p>
          <p class="episode-air">{{ item.next_episode?.air_date ? formatDateByLocale(item.next_episode.air_date) : '' }}</p>
          <div class="mt-3 flex items-center gap-2">
            <RatingBadge
              v-if="hasProviderRating(item.next_episode?.vote_average)"
              :value="item.next_episode?.vote_average"
              :votes="item.next_episode?.vote_count || 0"
              size="xs"
              out-of-ten
            />
          </div>
        </div>
        <div class="episode-media">
          <RouterLink :to="episodeLink(item)" class="episode-still">
            <img
              v-if="item.next_episode?.still_url"
              :src="item.next_episode.still_url"
              :alt="item.next_episode?.name || item.show_name"
              class="episode-still-image"
              loading="lazy"
            >
            <div v-else class="w-full h-full bg-surface-200"></div>
          </RouterLink>
        </div>
      </section>
    </div>

    <div class="mt-3 pt-3 border-t border-surface-200">
      <RouterLink :to="`/tv/${item.tmdb_id}`" class="inline-flex items-center gap-1 text-sm text-secondary hover:text-primary transition-colors">
        <span>{{ seasonsLabel(item) }}</span>
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
        </svg>
      </RouterLink>
    </div>
  </article>
</template>

<script setup>
import ProgressBar from '@/components/ProgressBar.vue'
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'
import EpisodeTypePill from '@/components/EpisodeTypePill.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import UserRating from '@/components/UserRating.vue'
import { formatDateByLocale } from '@/i18n'
import { formatHoursMinutes } from '@/utils/progress'
import { formatIsoAsDDMMYYYY } from '@/utils/temporal'

defineProps({
  item: { type: Object, required: true },
  rowBusyId: { type: Number, default: null },
})

const emit = defineEmits(['drop', 'open-rate', 'open-add-to-list'])

function hasProviderRating(value) {
  const rating = Number(value)
  return Number.isFinite(rating) && rating > 0
}

function formatCompactDate(value) {
  if (!value) return '--'
  return formatIsoAsDDMMYYYY(value) || '--'
}

function inferredStarted(value) {
  if (!value) return '--'
  return formatIsoAsDDMMYYYY(value) || '--'
}

function minutesPerEpisode(item) {
  const runtime = Number(item.episode_runtime)
  if (!Number.isFinite(runtime) || runtime <= 0) return '-- min/ep'
  return `${runtime} min/ep`
}

function statusClass(value) {
  if (value === 'watching') return 'status-watching'
  if (value === 'watched') return 'status-watched'
  if (value === 'dropped') return 'status-dropped'
  return 'status-default'
}

function statusText(value) {
  if (value === 'watching') return 'Watching'
  if (value === 'watched') return 'Watched'
  if (value === 'dropped') return 'Dropped'
  return value
}

function providerShowStatus(value) {
  const text = String(value || '').trim()
  return text || '--'
}

function progressFraction(item) {
  const watched = item.watched_episodes || 0
  const total = item.total_episodes || 0
  return total > 0 ? `${watched}/${total}` : `${watched}/?`
}

function formatTimeLeft(item) {
  const minutes = Number(item.runtime_left_minutes || 0)
  const episodesLeft = Number(item.episodes_left || 0)
  if (episodesLeft <= 0) return '0m'
  if (!Number.isFinite(minutes) || minutes <= 0) return `${episodesLeft} eps`
  return formatHoursMinutes(minutes, item.runtime_left_has_unknown)
}

function hasLastWatchedEpisodeCode(item) {
  const season = item.last_watched_episode?.season_number
  const episode = item.last_watched_episode?.episode_number
  return Boolean(season && episode)
}

function hasNextEpisode(item) {
  return Boolean(item.next_episode?.season_number && item.next_episode?.episode_number)
}

function episodeLink(item) {
  if (item.next_episode?.season_number && item.next_episode?.episode_number) {
    return `/tv/${item.tmdb_id}/season/${item.next_episode.season_number}/episode/${item.next_episode.episode_number}`
  }
  return `/tv/${item.tmdb_id}`
}

function seasonsLabel(item) {
  const seasons = Number(item.number_of_seasons)
  if (Number.isFinite(seasons) && seasons > 0) {
    return `${seasons} ${seasons === 1 ? 'Season' : 'Seasons'}`
  }
  return 'Show details'
}
</script>

<style scoped>
.progress-row-deferred {
  content-visibility: auto;
  contain-intrinsic-size: auto none auto 220px;
  --progress-pill-bg: var(--bg-surface-200);
  --progress-pill-hover: color-mix(in srgb, var(--brand-500) 14%, var(--bg-surface-200));
  --progress-accent-bg: var(--brand-500);
  --progress-accent-border: var(--brand-500);
  --progress-accent-text: #ffffff;
  --progress-track-bg: var(--bg-surface-300);
  --progress-muted-block: var(--bg-surface-100);
}

.control-menu {
  position: relative;
}

.control-menu[open] {
  z-index: 80;
}

.control-panel {
  position: absolute;
  z-index: 60;
  margin-top: 0.35rem;
  border-radius: 0.75rem;
  border: 1px solid var(--bg-surface-200);
  background: var(--bg-surface-100);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.34);
}

.control-option {
  width: 100%;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  font-size: 0.8125rem;
  border-radius: 0.5rem;
  padding: 0.5rem 0.6rem;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
}

.control-option:hover {
  background: var(--bg-surface-200);
  color: var(--text-primary);
}

.control-option-danger {
  color: var(--text-secondary);
}

.control-option-danger:hover,
.control-option-danger:focus-visible {
  color: var(--text-primary);
}

.progress-row-grid {
  display: grid;
  gap: 1rem;
}

.show-section {
  display: flex;
  gap: 0.8rem;
  min-width: 0;
}

.show-main {
  flex: 1;
  min-width: 0;
}

.row-pill-trigger {
  list-style: none;
  min-height: 1.8rem;
  border: 1px solid var(--bg-surface-200);
  background: var(--progress-pill-bg);
  border-radius: 0.45rem;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.25rem 0.55rem;
  font-size: 0.82rem;
  line-height: 1;
  cursor: pointer;
}

.row-pill-trigger::-webkit-details-marker {
  display: none;
}

.menu-panel {
  margin-top: 0.2rem;
}

.row-pill-trigger:hover,
.row-pill-trigger:focus-visible {
  background: var(--progress-pill-hover);
  color: var(--text-primary);
}

.show-title-row {
  min-width: 0;
}

.show-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6rem;
}

.show-meta-left {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meta-text {
  display: inline-flex;
  align-items: center;
}

.meta-separator {
  display: inline-flex;
  align-items: center;
  color: var(--text-muted);
}

.show-headline-meta {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-shrink: 0;
}

.show-headline-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.show-percent {
  line-height: 1;
}

.progress-row-bar {
  height: 0.32rem;
  background: var(--progress-track-bg);
}

.progress-row-bar :deep(.progress-fill) {
  background: var(--progress-accent-border);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 0.45rem;
  padding: 0.28rem 0.5rem;
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  border: 1px solid transparent;
}

.status-default { background: var(--bg-surface-200); color: var(--text-secondary); border-color: var(--bg-surface-300); }
.status-watching { background: color-mix(in srgb, var(--brand-500) 22%, var(--bg-surface-100)); color: var(--text-primary); border-color: color-mix(in srgb, var(--brand-500) 68%, var(--bg-surface-300)); }
.status-watched {
  background: color-mix(in srgb, #86efac 18%, var(--bg-surface-100));
  color: var(--text-secondary);
  border-color: color-mix(in srgb, #22c55e 40%, var(--bg-surface-300));
}
.status-dropped { background: color-mix(in srgb, var(--action-danger) 14%, var(--bg-surface-100)); color: var(--text-secondary); border-color: color-mix(in srgb, var(--action-danger) 45%, var(--bg-surface-300)); }

.stats-inline {
  display: flex;
  align-items: flex-start;
  gap: 1.1rem;
  margin-top: 0.1rem;
}

.stats-inline-item {
  min-width: 0;
}

.stats-inline-label {
  color: var(--text-muted);
  font-size: 0.72rem;
  line-height: 1;
  margin-bottom: 0.22rem;
}

.stats-inline-value {
  color: var(--text-primary);
  font-size: 0.86rem;
  line-height: 1.1;
  font-weight: 560;
  display: inline-flex;
  align-items: center;
  min-height: 1.35rem;
}

.stats-value-with-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  flex-wrap: wrap;
}

.last-watched-pill {
  --brand-500: var(--progress-accent-bg);
}

.episode-section {
  display: grid;
  gap: 0.65rem;
  border-left: 1px solid var(--bg-surface-200);
  padding-left: 0.85rem;
  grid-template-columns: minmax(0, 1fr) 272px;
}

.episode-kicker {
  margin-bottom: 0.35rem;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--progress-accent-border);
  font-weight: 700;
}

.episode-code {
  --brand-500: var(--progress-accent-bg);
}

.episode-title {
  margin-top: 0.45rem;
  font-size: 1.12rem;
  line-height: 1.2;
  font-family: var(--font-display);
  color: var(--text-primary);
  font-weight: 650;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.episode-type {
  margin-left: 0.45rem;
}

.episode-air {
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.episode-media {
  display: grid;
  gap: 0.35rem;
  align-content: start;
}

.episode-still {
  width: 100%;
  height: 170px;
  border-radius: 0.35rem;
  overflow: hidden;
  border: 1px solid var(--bg-surface-200);
  background: var(--bg-surface-200);
}

.episode-still-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

@media (max-width: 1099px) {
  .show-section {
    align-items: flex-start;
  }

  .progress-row-grid {
    gap: 0.8rem;
  }

  .show-meta-row {
    align-items: flex-start;
    flex-wrap: wrap;
    row-gap: 0.4rem;
  }

  .show-headline-meta {
    align-items: flex-end;
    gap: 0.45rem;
    margin-left: auto;
  }

  .show-headline-actions {
    gap: 0.35rem;
  }

  .episode-section {
    border-left: 0;
    padding-left: 0;
    border-top: 1px solid var(--bg-surface-200);
    padding-top: 0.75rem;
    grid-template-columns: minmax(0, 1fr);
  }

  .episode-title {
    font-size: 1.25rem;
  }

  .episode-media {
    margin-top: 0.1rem;
  }
}

@media (min-width: 1100px) {
  .progress-row-grid.row-with-episode {
    grid-template-columns: minmax(0, 1fr) 470px;
    align-items: start;
  }

  .progress-row-grid.row-no-episode {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
