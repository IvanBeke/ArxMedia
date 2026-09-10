import type { MEDIA_TYPE, WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import type { WatchEntryStatus } from '@/types/tracking'

export type MediaType = (typeof MEDIA_TYPE)[keyof typeof MEDIA_TYPE]
export type WatchEntryMediaType = (typeof WATCH_ENTRY_MEDIA_TYPE)[keyof typeof WATCH_ENTRY_MEDIA_TYPE]
export type QueryValue = string | number | boolean | readonly (string | number | boolean)[] | null | undefined
export type QueryParams = Record<string, QueryValue>
export type ApiError = Record<string, unknown> & { detail?: string; non_field_errors?: string[]; status?: number }

export interface Tokens { access: string; refresh: string }
export interface User {
  id: number; username: string; email: string; bio: string; avatar: string | null; location: string
  website: string; preferred_region: string; account_visibility: 'public' | 'private' | 'friends_only'
  followers_count: number; following_count: number; total_watched_movies: number; total_watched_episodes: number; created_at: string
}
export interface UserProfile extends User {
  permissions?: { can_view_activity: boolean; can_view_lists: boolean }
  recent_activity?: WatchEntry[]
  visible_lists?: Pick<CustomList, 'id' | 'name' | 'description' | 'item_count'>[]
  stats?: { ratings_count: number; watchlist_count: number; average_rating: number }
  viewer_relationship?: { follows_you: boolean; is_friend: boolean; is_self: boolean; is_following: boolean }
}
export interface LoginPayload { username: string; password: string }
export interface RegisterPayload extends LoginPayload { email: string; password2: string }
export interface ProfileUpdatePayload { username?: string; email?: string; bio?: string; avatar?: string | null; location?: string; website?: string; preferred_region?: string; account_visibility?: User['account_visibility'] }
export interface UserCard { id: number; username: string; bio: string; avatar: string | null; followers_count: number; following_count: number }
export interface PaginatedResponse<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Genre { id?: number; tmdb_id: number; name: string }
export interface MediaUserStatus { status: WatchEntryStatus; watched_at?: string | null; status_changed_at?: string | null; rating?: number | null }
export interface MediaResult { id: number; media_type: MediaType; title?: string; name?: string; overview?: string; poster_path?: string | null; backdrop_path?: string | null; release_date?: string | null; first_air_date?: string | null; vote_average?: number; vote_count?: number; user_status?: MediaUserStatus }
export interface MediaSearchResponse { results: MediaResult[]; page: number; total_pages: number; total_results: number }
export interface Person { id: number; credit_id?: string; name: string; profile_path?: string | null; character?: string; job?: string; department?: string; total_episode_count?: number }
export interface Credits { cast: Person[]; crew: Person[]; guest_stars: Person[] }
export interface WatchProvider { provider_id: number; provider_name: string; logo_path: string | null; display_priority?: number }
export interface WatchProviders { region: string; link: string | null; flatrate: WatchProvider[]; rent: WatchProvider[]; buy: WatchProvider[]; free: WatchProvider[]; ads: WatchProvider[] }
export interface Movie extends MediaResult { title: string; tmdb_id: number; genres: Genre[]; poster_url: string | null; backdrop_url: string | null; runtime: number | null; language: string; tagline: string; status: string; metadata_updated_at: string; watch_providers?: WatchProviders }
export interface Episode { id: number; tmdb_id: number; episode_number: number; name: string; overview: string; still_path: string | null; still_url: string | null; air_date: string | null; air_time: string | null; broadcast_start: string | null; runtime: number | null; vote_average: number; vote_count: number; episode_type: string; guest_stars: Person[]; crew: Person[] }
export interface SeasonBrief { id: number; season_number: number; name: string; poster_path: string | null; poster_url: string | null; air_date: string | null; episode_count: number }
export interface SeasonProgress { watched_episodes?: number }
export interface Season extends SeasonBrief { tmdb_id: number; overview: string; episodes: Episode[]; show_name?: string; user_status?: MediaUserStatus & { progress?: SeasonProgress } }
export interface TVShow extends MediaResult { name: string; tmdb_id: number; genres: Genre[]; poster_url: string | null; backdrop_url: string | null; first_air_date: string | null; last_air_date: string | null; number_of_seasons: number; number_of_episodes: number; language: string; status: string; networks: string[]; episode_runtime: number | null; metadata_updated_at: string; seasons: SeasonBrief[]; watch_providers?: WatchProviders }
export interface WatchEntry { id: number; media_type: WatchEntryMediaType; tmdb_id: number; watched_at: string; season_number: number | null; episode_number: number | null; created_at: string; title: string; poster_path: string | null; poster_url: string | null; vote_average: number; show_name: string | null; rating?: number | null }
export interface MediaCard { id: number; media_type: MediaType; tmdb_id: number; title: string; poster_path: string | null; poster_url: string | null; vote_average: number; release_date: string | null; user_status: MediaUserStatus | null; added_at: string }
export interface ShowProgressEpisode {
  season_number: number | null; episode_number: number | null; name: string | null; still_url: string | null
  air_date: string | null; episode_type: string | null; vote_average: number | null; vote_count: number | null
}
export interface ShowProgressItem extends Pick<MediaCard, 'tmdb_id' | 'poster_url' | 'vote_average'> {
  show_name: string; number_of_seasons: number | null; status: WatchEntryStatus; provider_status: string | null
  user_rating: number | null; genres: string[]; networks: string[]; episode_runtime: number | null
  progress_percent?: number | null; watched_episodes?: number | null; total_episodes?: number | null
  last_watched_at?: string | null; started_at?: string | null; episodes_left?: number | null
  runtime_left_minutes?: number | null; runtime_left_has_unknown?: boolean; next_episode?: ShowProgressEpisode | null
  last_watched_episode?: Pick<ShowProgressEpisode, 'season_number' | 'episode_number'> | null
}
export interface Rating { id: number; media_type: MediaType; tmdb_id: number; score: number; created_at: string; updated_at: string }
export interface EpisodeWatchPayload { tmdb_id: number | string; season_number: number | string; episode_number: number | string; watched_at?: string | null }
export interface SeasonWatchPayload { tmdb_id: number | string; season_number: number | string; watched_at?: string; use_release_date?: boolean }
export interface CustomList { id: number; username: string; name: string; description: string; privacy: 'public' | 'private'; item_count: number; collaborators: number[]; collaborator_users: UserCard[]; created_at: string; updated_at: string }
export interface ListItem extends MediaCard { custom_order: number }
export interface ListItemsResponse extends PaginatedResponse<ListItem> {
  total_runtime_minutes?: number
  counts?: { shows?: number; movies?: number }
}
export type DataTransferStatus = 'pending' | 'processing' | 'awaiting_confirmation' | 'done' | 'failed' | 'cancelled'
export type DataTransferJobType = 'import' | 'export'
export type DataTransferSource = 'arxmedia' | 'trakt' | 'yamtrack'
export type DataTransferFormat = 'json' | 'csv' | 'zip'
export type DataImportMode = 'new_items' | 'update_existing' | 'mirror_imported_set'
export interface DataTransferFileReport { file: string; status: string; error?: string; records_seen?: number }
export interface DataTransferWarning { code?: string; location?: { kind?: string; file?: string; row?: number; column?: string | number; record?: number; collection?: string; index?: number; field?: string }; message?: string }
export interface DataTransferReport {
  records_seen?: number; records_imported?: number; records_skipped?: number; records_unchanged?: number; deleted_total?: number; metadata_errors?: number
  summary?: { watch_history?: number; watchlist?: number; ratings?: number; lists?: number }
  deleted?: { watch_history?: number; watchlist?: number; ratings?: number; lists?: number }
  lists_imported?: number; list_items_seen?: number; list_items_imported?: number
  invalid_count?: number; unsupported_files?: number; unsupported_records?: number; skipped_non_tmdb?: number
  skipped_unsupported_media_type?: number; skipped_invalid_status?: number; skipped_missing_tmdb_id?: number; files_failed?: number
  warnings?: DataTransferWarning[]; files?: DataTransferFileReport[]
  [key: string]: unknown
}
export interface DataTransferJob {
  id: number; job_type: DataTransferJobType; status: DataTransferStatus; created_at: string; updated_at: string; processed_items: number; total_items: number; error_message?: string | null
  source?: DataTransferSource; data_format?: DataTransferFormat; import_mode?: DataImportMode; overwrite_existing?: boolean; output_url?: string | null
  metadata?: { summary?: DataTransferReport['summary']; pipeline?: { stage?: string }; report?: DataTransferReport } & DataTransferReport
}
export interface CalendarMovie { kind: 'movie'; date: string; tmdb_id: number; title: string; poster_url: string | null }
export interface CalendarEpisode { kind: 'episode'; date: string; tmdb_id: number; show_name: string; season_number: number; episode_number: number; episode_name: string; poster_url: string | null }
export type CalendarItem = CalendarMovie | CalendarEpisode
export interface WatchedEpisode { season_number: number | null; episode_number: number | null; watched_at: string | null }
