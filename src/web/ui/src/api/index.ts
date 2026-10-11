import { DATA_TRANSFER_FORMAT, MEDIA_TYPE } from '@/constants/tracking'
import type {
  ApiError,
  CalendarItem,
  CollectionDetail,
  AggregateCredits,
  CustomList,
  DataImportMode,
  DataTransferFormat,
  DataTransferJob,
  DataTransferSource,
  EpisodeCredits,
  EpisodeWatchPayload,
  ExternalIds,
  Genre,
  HeatmapSeason,
  ListItem,
  ListItemsResponse,
  LoginPayload,
  MediaCard,
  MediaSearchResponse,
  MediaType,
  Movie,
  PaginatedResponse,
  PersonCombinedCredits,
  PersonDetail,
  PersonSearchResponse,
  ProfileUpdatePayload,
  QueryParams,
  Rating,
  RegisterPayload,
  Season,
  SeasonWatchPayload,
  ShowProgressItem,
  TVShow,
  User,
  UserActivityHeatmap,
  UserCard,
  UserProfile,
  WatchEntry,
  WatchedEpisode,
} from '@/types/api'

export interface DashboardStats {
  movies_watched: number; episodes_watched: number; shows_watching: number
  average_rating: number | null; recent_activity: WatchEntry[]
}
export interface UpNextItem {
  tmdb_id: number; show_name: string; poster_url: string; is_new: boolean; progress_percent: number
  episodes_left: number | null; runtime_left_minutes: number | null; runtime_left_has_unknown: boolean
  next_episode: { name: string; episode_type: string; season_number: number; episode_number: number; runtime: number | null } | null
}
export interface FollowResult {
  following: boolean; is_friend: boolean; followers_count: number; following_count: number
}
export interface UpcomingItem {
  tmdb_id: number; show_name: string; name: string; episode_type: string; season_number: number
  episode_number: number; poster_url: string; air_date: string | null
}

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
type RequestMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE' | 'HEAD'
type RequestData = object | readonly unknown[] | FormData | null
/** Pass an AbortSignal to cancel a superseded request (see useLatestRequest). */
type RequestOptions = { signal?: AbortSignal }

const SAFE_METHODS = new Set<RequestMethod>(['GET', 'HEAD'])

async function parseResponse<T>(response: Response): Promise<T> {
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (payload && typeof payload === 'object') throw { ...payload, status: response.status } as ApiError
    throw { detail: `Request failed (${response.status})`, status: response.status } satisfies ApiError
  }
  return payload as T
}

function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match?.[1] ? decodeURIComponent(match[1]) : null
}

async function request<T>(method: RequestMethod, url: string, data: RequestData = null, params: QueryParams | null = null, signal?: AbortSignal): Promise<T> {
  const fullUrl = new URL(baseURL + url, window.location.origin)
  if (params) for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== null) fullUrl.searchParams.append(key, String(value))
  const headers: Record<string, string> = {}
  const options: RequestInit = { method, headers, credentials: 'same-origin', signal }
  if (!SAFE_METHODS.has(method)) {
    const token = csrfToken()
    if (token) headers['X-CSRFToken'] = token
    if (data instanceof FormData) options.body = data
    else if (data) {
      headers['Content-Type'] = 'application/json'
      options.body = JSON.stringify(data)
    }
  }
  const response = await fetch(fullUrl.toString(), options)
  if (response.status === 401 && !url.startsWith('/auth/')) {
    const redirect = `${window.location.pathname}${window.location.search}`
    window.location.href = `/login?redirect=${encodeURIComponent(redirect)}`
  }
  return parseResponse<T>(response)
}

const api = {
  get: <T>(url: string, options: { params?: QueryParams; signal?: AbortSignal } = {}) => request<T>('GET', url, null, options.params ?? null, options.signal),
  post: <T>(url: string, data: RequestData = null, options: { params?: QueryParams; signal?: AbortSignal } = {}) =>
    request<T>('POST', url, data, options.params ?? null, options.signal),
  patch: <T>(url: string, data: RequestData) => request<T>('PATCH', url, data),
  delete: <T>(url: string) => request<T>('DELETE', url),
}

export const authAPI = {
  register: (data: RegisterPayload) => api.post<User>('/auth/register/', data),
  login: (data: LoginPayload) => api.post<User>('/auth/login/', data),
  logout: () => api.post<void>('/auth/logout/'),
  me: () => api.get<User>('/auth/me/'),
  updateProfile: (data: ProfileUpdatePayload) => api.patch<User>('/auth/me/', data),
  searchUsers: (q: string) => api.get<UserCard[]>('/auth/users/search/', { params: { q } }),
  getUser: (username: string) => api.get<UserProfile>(`/auth/users/${encodeURIComponent(username)}/`),
  getUserActivity: (username: string) => api.get<UserActivityHeatmap>(`/auth/users/${encodeURIComponent(username)}/activity/`),
  getFollowers: (username: string, params?: QueryParams) =>
    api.get<PaginatedResponse<UserCard>>(`/auth/users/${encodeURIComponent(username)}/followers/`, { params }),
  getFollowing: (username: string, params?: QueryParams) =>
    api.get<PaginatedResponse<UserCard>>(`/auth/users/${encodeURIComponent(username)}/following/`, { params }),
  follow: (username: string) =>
    api.post<FollowResult>(`/auth/users/${encodeURIComponent(username)}/follow/`),
  changePassword: (data: { current_password: string; new_password: string }) => api.post<{ detail: string }>('/auth/password/change/', data),
}

export const mediaAPI = {
  search: (q: string, type: 'movie' | 'tv' | 'multi' = 'multi', page = 1) => api.get<MediaSearchResponse>('/media/search/', { params: { q, type, page } }),
  searchPeople: (q: string, page = 1) => api.get<PersonSearchResponse>('/media/people/search/', { params: { q, page } }),
  genres: () => api.get<Genre[]>('/media/genres/'),
  trending: (type: 'all' | MediaType = 'all', window: 'day' | 'week' = 'week') =>
    api.get<MediaSearchResponse>('/media/trending/', { params: { type, window } }),
  popular: (type: MediaType = MEDIA_TYPE.MOVIE, page = 1) => api.get<MediaSearchResponse>('/media/popular/', { params: { type, page } }),
  getMovie: (id: string | number, region?: string) => api.get<Movie>('/media/movies/' + id + '/', { params: { region } }),
  refreshMovie: (id: string | number) => api.post<Movie>('/media/movies/' + id + '/refresh/', {}),
  getMovieCredits: (id: string | number) => api.get<AggregateCredits>('/media/movies/' + id + '/credits/'),
  getMovieExternalIds: (id: string | number) => api.get<ExternalIds>('/media/movies/' + id + '/external-ids/'),
  getMovieRecommendations: (id: string | number, page = 1) => api.get<MediaSearchResponse>('/media/movies/' + id + '/recommendations/', { params: { page } }),
  getCollection: (id: string | number) => api.get<CollectionDetail>('/media/collections/' + id + '/'),
  getTV: (id: string | number, region?: string) => api.get<TVShow>('/media/tv/' + id + '/', { params: { region } }),
  refreshTV: (id: string | number) => api.post<TVShow>('/media/tv/' + id + '/refresh/', {}),
  getTVCredits: (id: string | number) => api.get<AggregateCredits>('/media/tv/' + id + '/credits/'),
  getTVExternalIds: (id: string | number) => api.get<ExternalIds>('/media/tv/' + id + '/external-ids/'),
  getTVRecommendations: (id: string | number, page = 1) => api.get<MediaSearchResponse>('/media/tv/' + id + '/recommendations/', { params: { page } }),
  getTVHeatmap: (id: string | number) => api.get<HeatmapSeason[]>('/media/tv/' + id + '/heatmap/'),
  getSeason: (showId: string | number, season: string | number) => api.get<Season>('/media/tv/' + showId + '/seasons/' + season + '/'),
  getSeasonCredits: (showId: string | number, season: string | number) => api.get<AggregateCredits>('/media/tv/' + showId + '/seasons/' + season + '/credits/'),
  getEpisodeCredits: (showId: string | number, season: string | number, episode: string | number) =>
    api.get<EpisodeCredits>('/media/tv/' + showId + '/seasons/' + season + '/episodes/' + episode + '/credits/'),
  getEpisodeExternalIds: (showId: string | number, season: string | number, episode: string | number) =>
    api.get<ExternalIds>('/media/tv/' + showId + '/seasons/' + season + '/episodes/' + episode + '/external-ids/'),
  getPerson: (id: string | number) => api.get<PersonDetail>('/media/people/' + id + '/'),
  getPersonCredits: (id: string | number) => api.get<PersonCombinedCredits>('/media/people/' + id + '/credits/'),
  getPersonExternalIds: (id: string | number) => api.get<ExternalIds>('/media/people/' + id + '/external-ids/'),
}

type HistoryPayload = {
  tmdb_id: string | number; media_type: WatchEntry['media_type']; season_number?: string | number
  episode_number?: string | number; watched_at?: string | null
}
type MediaPayload = { tmdb_id: string | number; media_type: MediaType }
export const trackingAPI = {
  getHistory: (params?: QueryParams, options: RequestOptions = {}) => api.get<PaginatedResponse<WatchEntry>>('/tracking/history/', { params, ...options }),
  addToHistory: (data: HistoryPayload) => api.post<WatchEntry>('/tracking/history/', data),
  deleteHistory: (id: string | number) => api.delete<void>('/tracking/history/' + id + '/'),
  removeFromHistory: async (data: HistoryPayload) => {
    const response = await api.get<PaginatedResponse<WatchEntry>>('/tracking/history/',
      { params: { tmdb_id: data.tmdb_id, media_type: data.media_type, season_number: data.season_number, episode_number: data.episode_number } })
    const entry = response.results.find((item) => item.tmdb_id == data.tmdb_id && item.media_type === data.media_type
      && (!data.season_number || item.season_number == data.season_number) && (!data.episode_number || item.episode_number == data.episode_number))
    return entry ? api.delete<void>('/tracking/history/' + entry.id + '/') : undefined
  },
  markEpisodeWatched: (data: EpisodeWatchPayload) => api.post<{ id: number; created: boolean; watched_at: string | null }>('/tracking/episodes/mark/', data),
  unmarkEpisodeWatched: (data: EpisodeWatchPayload) => api.post<{ deleted: boolean }>('/tracking/episodes/unmark/', data),
  markSeasonWatched: (data: SeasonWatchPayload) => api.post<{ marked: number; episodes: WatchEntry[] }>('/tracking/seasons/mark/', data),
  unmarkSeasonWatched: (data: Omit<SeasonWatchPayload, 'watched_at' | 'use_release_date'>) =>
    api.post<{ unmarked: number; episodes: WatchEntry[] }>('/tracking/seasons/unmark/', data),
  markShowWatched: (data: { tmdb_id: string | number; watched_at?: string }) =>
    api.post<{ marked: number; episodes: WatchedEpisode[] }>('/tracking/shows/mark/', data),
  unmarkShowWatched: (data: { tmdb_id: string | number }) => api.post<{ unmarked: number }>('/tracking/shows/unmark/', data),
  getWatchedEpisodes: (tmdbId: string | number) =>
    api.get<{ episodes: WatchedEpisode[] }>('/tracking/episodes/watched/', { params: { tmdb_id: tmdbId } }),

  getWatchlist: (params?: QueryParams, options: RequestOptions = {}) => api.get<PaginatedResponse<MediaCard>>('/tracking/watchlist/', { params, ...options }),
  addToWatchlist: (data: MediaPayload) => api.post<MediaCard>('/tracking/watchlist/', data),
  removeFromWatchlist: (id: string | number) => api.delete<void>('/tracking/watchlist/' + id + '/'),
  getRatings: (params?: QueryParams) => api.get<PaginatedResponse<Rating>>('/tracking/ratings/', { params }),
  rate: (data: MediaPayload & { score: number }) => api.post<Rating>('/tracking/ratings/', data),
  getStats: () => api.get<DashboardStats>('/tracking/stats/'),
  getUpNext: () => api.get<UpNextItem[]>('/tracking/up-next/'),
  getMyShows: (params?: QueryParams, options: RequestOptions = {}) =>
    api.get<PaginatedResponse<ShowProgressItem>>('/tracking/my-shows/', { params, ...options }),
  getMyMovies: (params?: QueryParams, options: RequestOptions = {}) => api.get<PaginatedResponse<MediaCard>>('/tracking/my-movies/', { params, ...options }),
  getUpcoming: () => api.get<UpcomingItem[]>('/tracking/upcoming/'),
  dropMedia: (data: MediaPayload) => api.post<Record<string, unknown>>('/tracking/media/drop/', data),
  getLists: () => api.get<PaginatedResponse<CustomList>>('/tracking/lists/'),
  createList: (data: { name: string; description?: string; privacy?: CustomList['privacy']; collaborator_ids?: number[] }) =>
    api.post<CustomList>('/tracking/lists/', data),
  getList: (id: string | number) => api.get<CustomList>('/tracking/lists/' + id + '/'),
  getListItems: (listId: string | number, params?: QueryParams, options: RequestOptions = {}) =>
    api.get<ListItemsResponse>('/tracking/lists/' + listId + '/items/', { params, ...options }),
  updateList: (id: string | number, data: Partial<{ name: string; description: string; privacy: CustomList['privacy']; collaborator_ids: number[] }>) =>
    api.patch<CustomList>('/tracking/lists/' + id + '/', data),
  deleteList: (id: string | number) => api.delete<void>('/tracking/lists/' + id + '/'),
  addToList: (listId: string | number, data: MediaPayload) => api.post<ListItem>('/tracking/lists/' + listId + '/items/', data),
  removeFromList: (listId: string | number, itemId: string | number) => api.delete<void>('/tracking/lists/' + listId + '/items/' + itemId + '/'),
  reorderList: (listId: string | number, orderedIds: number[]) =>
    api.post<ListItem[]>('/tracking/lists/' + listId + '/items/reorder/', { custom_order: orderedIds }),
  getRecommendations: () => api.get<MediaCard[]>('/tracking/recommendations/'),
  importData: (file: File, format: DataTransferFormat = 'zip', source: DataTransferSource = 'arxmedia') => {
    const form = new FormData()
    form.append('file', file)
    return request<DataTransferJob>('POST', '/tracking/data/import/', form, { data_format: format, source })
  },
  exportData: (format: DataTransferFormat = 'zip') => api.post<DataTransferJob>('/tracking/data/export/', {}, { params: { data_format: format } }),
  listJobs: () => api.get<PaginatedResponse<DataTransferJob>>('/tracking/data/jobs/'),
  getJobStatus: (jobId: string | number) => api.get<DataTransferJob>('/tracking/data/jobs/' + jobId + '/'),
  confirmJobImport: (jobId: string | number, importMode: DataImportMode) =>
    api.post<DataTransferJob>('/tracking/data/jobs/' + jobId + '/confirm/', { import_mode: importMode }),
  cancelJobImport: (jobId: string | number) => api.post<DataTransferJob>('/tracking/data/jobs/' + jobId + '/cancel/', {}),
  deleteExportFile: (jobId: string | number) => api.delete<DataTransferJob>('/tracking/data/jobs/' + jobId + '/file/'),
}

export const calendarAPI = { get: (params?: QueryParams) => api.get<{ results: CalendarItem[] }>('/calendar/', { params }) }
export const socialAPI = { getFeed: () => api.get<WatchEntry[]>('/social/feed/') }
export default api