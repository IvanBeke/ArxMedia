import { DATA_TRANSFER_FORMAT, MEDIA_TYPE } from '@/constants/tracking'
import type { ApiError, CalendarItem, Credits, CustomList, DataTransferJob, EpisodeWatchPayload, Genre, ListItem, ListItemsResponse, LoginPayload, MediaCard, MediaSearchResponse, MediaType, Movie, PaginatedResponse, ProfileUpdatePayload, QueryParams, RegisterPayload, Rating, Season, SeasonWatchPayload, ShowProgressItem, Tokens, TVShow, User, UserCard, UserProfile, WatchedEpisode, WatchEntry } from '@/types/api'

export interface DashboardStats {
  movies_watched: number; episodes_watched: number; shows_watching: number
  average_rating: number | null; recent_activity: WatchEntry[]
}
export interface UpNextItem {
  tmdb_id: number; show_name: string; poster_url: string; is_new: boolean; progress_percent: number
  episodes_left: number | null; runtime_left_minutes: number | null; runtime_left_has_unknown: boolean
  next_episode: { name: string; episode_type: string; season_number: number; episode_number: number; runtime: number | null } | null
}
export interface UpcomingItem {
  tmdb_id: number; show_name: string; name: string; episode_type: string; season_number: number
  episode_number: number; poster_url: string; air_date: string | null
}

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
type RequestMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE' | 'HEAD'
type RequestData = object | readonly unknown[] | null
type RefreshSubscriber = { resolve: (token: string) => void; reject: (reason?: unknown) => void }

let isRefreshing = false
let refreshSubscribers: RefreshSubscriber[] = []

async function parseResponse<T>(response: Response): Promise<T> {
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (payload && typeof payload === 'object') throw { ...payload, status: response.status } as ApiError
    throw { detail: `Request failed (${response.status})`, status: response.status } satisfies ApiError
  }
  return payload as T
}

async function refreshAccessToken(origin: string): Promise<string> {
  const refresh = localStorage.getItem('refresh_token')
  if (!refresh) throw new Error('Missing refresh token')
  if (isRefreshing) return new Promise<string>((resolve, reject) => refreshSubscribers.push({ resolve, reject }))
  isRefreshing = true
  try {
    const refreshData = await parseResponse<Partial<Tokens>>(await fetch(origin + '/api/auth/token/refresh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh }) }))
    if (!refreshData.access) throw new Error('Refresh token response missing access token')
    localStorage.setItem('access_token', refreshData.access)
    refreshSubscribers.forEach(({ resolve }) => resolve(refreshData.access as string))
    refreshSubscribers = []
    return refreshData.access
  } catch (error: unknown) {
    refreshSubscribers.forEach(({ reject }) => reject(error))
    refreshSubscribers = []
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    const redirect = `${window.location.pathname}${window.location.search}`
    window.location.href = `/login?redirect=${encodeURIComponent(redirect)}`
    throw error
  } finally { isRefreshing = false }
}

async function request<T>(method: RequestMethod, url: string, data: RequestData = null, params: QueryParams | null = null): Promise<T> {
  const fullUrl = new URL(baseURL + url, window.location.origin)
  if (params) for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== null) fullUrl.searchParams.append(key, String(value))
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem('access_token')
  if (token) headers.Authorization = `Bearer ${token}`
  const options: RequestInit = { method, headers }
  if (data && method !== 'GET' && method !== 'HEAD') options.body = JSON.stringify(data)
  let response = await fetch(fullUrl.toString(), options)
  if (response.status === 401 && !url.includes('/token/refresh/')) {
    if (localStorage.getItem('refresh_token')) {
      headers.Authorization = `Bearer ${await refreshAccessToken(fullUrl.origin)}`
      response = await fetch(fullUrl.toString(), options)
    }
  }
  return parseResponse<T>(response)
}

const api = {
  get: <T>(url: string, options: { params?: QueryParams } = {}) => request<T>('GET', url, null, options.params ?? null),
  post: <T>(url: string, data: RequestData = null) => request<T>('POST', url, data),
  patch: <T>(url: string, data: RequestData) => request<T>('PATCH', url, data),
  delete: <T>(url: string) => request<T>('DELETE', url),
}

export const authAPI = {
  register: (data: RegisterPayload) => api.post<User>('/auth/register/', data), login: (data: LoginPayload) => api.post<Tokens>('/auth/login/', data), me: () => api.get<User>('/auth/me/'), updateProfile: (data: ProfileUpdatePayload) => api.patch<User>('/auth/me/', data),
  searchUsers: (q: string) => api.get<UserCard[]>('/auth/users/search/', { params: { q } }), getUser: (username: string) => api.get<UserProfile>('/auth/users/' + username + '/'), getFollowers: (username: string, params?: QueryParams) => api.get<PaginatedResponse<UserCard>>('/auth/users/' + username + '/followers/', { params }), getFollowing: (username: string, params?: QueryParams) => api.get<PaginatedResponse<UserCard>>('/auth/users/' + username + '/following/', { params }), follow: (username: string) => api.post<{ following: boolean; is_friend: boolean; followers_count: number; following_count: number }>('/auth/users/' + username + '/follow/'), changePassword: (data: { current_password: string; new_password: string }) => api.post<{ detail: string }>('/auth/password/change/', data),
}

export const mediaAPI = {
  search: (q: string, type: 'movie' | 'tv' | 'multi' = 'multi', page = 1) => api.get<MediaSearchResponse>('/media/search/', { params: { q, type, page } }), genres: () => api.get<Genre[]>('/media/genres/'), trending: (type: 'all' | MediaType = 'all', window: 'day' | 'week' = 'week') => api.get<MediaSearchResponse>('/media/trending/', { params: { type, window } }), popular: (type: MediaType = MEDIA_TYPE.MOVIE, page = 1) => api.get<MediaSearchResponse>('/media/popular/', { params: { type, page } }),
  getMovie: (id: string | number, region?: string) => api.get<Movie>('/media/movies/' + id + '/', { params: { region } }), refreshMovie: (id: string | number) => api.post<Movie>('/media/movies/' + id + '/refresh/', {}), getMovieCredits: (id: string | number) => api.get<Credits>('/media/movies/' + id + '/credits/'), getTV: (id: string | number, region?: string) => api.get<TVShow>('/media/tv/' + id + '/', { params: { region } }), refreshTV: (id: string | number) => api.post<TVShow>('/media/tv/' + id + '/refresh/', {}), getTVCredits: (id: string | number) => api.get<Credits>('/media/tv/' + id + '/credits/'), getSeason: (showId: string | number, season: string | number) => api.get<Season>('/media/tv/' + showId + '/seasons/' + season + '/'), getEpisodeCredits: (showId: string | number, season: string | number, episode: string | number) => api.get<Credits>('/media/tv/' + showId + '/seasons/' + season + '/episodes/' + episode + '/credits/'),
}

type HistoryPayload = { tmdb_id: string | number; media_type: WatchEntry['media_type']; season_number?: string | number; episode_number?: string | number; watched_at?: string | null }
type MediaPayload = { tmdb_id: string | number; media_type: MediaType }
export const trackingAPI = {
  getHistory: (params?: QueryParams) => api.get<PaginatedResponse<WatchEntry> | WatchEntry[]>('/tracking/history/', { params }), addToHistory: (data: HistoryPayload) => api.post<WatchEntry>('/tracking/history/', data), deleteHistory: (id: string | number) => api.delete<void>('/tracking/history/' + id + '/'),
  removeFromHistory: async (data: HistoryPayload) => { const response = await api.get<PaginatedResponse<WatchEntry> | WatchEntry[]>('/tracking/history/', { params: { tmdb_id: data.tmdb_id, media_type: data.media_type } }); const entries = Array.isArray(response) ? response : response.results; const entry = entries.find((item) => item.tmdb_id == data.tmdb_id && item.media_type === data.media_type && (!data.season_number || item.season_number == data.season_number) && (!data.episode_number || item.episode_number == data.episode_number)); return entry ? api.delete<void>('/tracking/history/' + entry.id + '/') : undefined },
  markEpisodeWatched: (data: EpisodeWatchPayload) => api.post<{ id: number; created: boolean }>('/tracking/episodes/mark/', data), unmarkEpisodeWatched: (data: EpisodeWatchPayload) => api.post<{ deleted: boolean }>('/tracking/episodes/unmark/', data), markSeasonWatched: (data: SeasonWatchPayload) => api.post<{ marked: number; episodes: WatchEntry[] }>('/tracking/seasons/mark/', data), unmarkSeasonWatched: (data: Omit<SeasonWatchPayload, 'watched_at' | 'use_release_date'>) => api.post<{ unmarked: number; episodes: WatchEntry[] }>('/tracking/seasons/unmark/', data), unmarkShowWatched: (data: { tmdb_id: string | number }) => api.post<{ unmarked: number }>('/tracking/shows/unmark/', data), getWatchedEpisodes: (tmdbId: string | number) => api.get<{ episodes: WatchedEpisode[] }>('/tracking/episodes/watched/', { params: { tmdb_id: tmdbId } }),
  getWatchlist: (params?: QueryParams) => api.get<PaginatedResponse<MediaCard>>('/tracking/watchlist/', { params }), addToWatchlist: (data: MediaPayload) => api.post<MediaCard>('/tracking/watchlist/', data), removeFromWatchlist: (id: string | number) => api.delete<void>('/tracking/watchlist/' + id + '/'), getRatings: (params?: QueryParams) => api.get<PaginatedResponse<Rating> | Rating[]>('/tracking/ratings/', { params }), rate: (data: MediaPayload & { score: number }) => api.post<Rating>('/tracking/ratings/', data),
  getStats: () => api.get<DashboardStats>('/tracking/stats/'), getUpNext: () => api.get<UpNextItem[]>('/tracking/up-next/'), getMyShows: (params?: QueryParams) => api.get<PaginatedResponse<ShowProgressItem>>('/tracking/my-shows/', { params }), getMyMovies: (params?: QueryParams) => api.get<PaginatedResponse<MediaCard>>('/tracking/my-movies/', { params }), getUpcoming: () => api.get<UpcomingItem[]>('/tracking/upcoming/'), dropMedia: (data: MediaPayload) => api.post<Record<string, unknown>>('/tracking/media/drop/', data),
  getLists: () => api.get<PaginatedResponse<CustomList> | CustomList[]>('/tracking/lists/'), createList: (data: { name: string; description?: string; privacy?: CustomList['privacy']; collaborator_ids?: number[] }) => api.post<CustomList>('/tracking/lists/', data), getList: (id: string | number) => api.get<CustomList>('/tracking/lists/' + id + '/'), getListItems: (listId: string | number, params?: QueryParams) => api.get<ListItemsResponse>('/tracking/lists/' + listId + '/items/', { params }), updateList: (id: string | number, data: Partial<{ name: string; description: string; privacy: CustomList['privacy']; collaborator_ids: number[] }>) => api.patch<CustomList>('/tracking/lists/' + id + '/', data), deleteList: (id: string | number) => api.delete<void>('/tracking/lists/' + id + '/'), addToList: (listId: string | number, data: MediaPayload) => api.post<ListItem>('/tracking/lists/' + listId + '/items/', data), removeFromList: (listId: string | number, itemId: string | number) => api.delete<void>('/tracking/lists/' + listId + '/items/' + itemId + '/'), reorderList: (listId: string | number, orderedIds: number[]) => api.post<ListItem[]>('/tracking/lists/' + listId + '/items/reorder/', { custom_order: orderedIds }), getRecommendations: () => api.get<MediaCard[]>('/tracking/recommendations/'),
  importData: (file: File, format: (typeof DATA_TRANSFER_FORMAT)[keyof typeof DATA_TRANSFER_FORMAT] = DATA_TRANSFER_FORMAT.JSON, source = '') => { const form = new FormData(); form.append('file', file); const fullUrl = new URL(baseURL + '/tracking/data/import/', window.location.origin); fullUrl.searchParams.set('data_format', format); fullUrl.searchParams.set('source', source); const token = localStorage.getItem('access_token'); return fetch(fullUrl.toString(), { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form }).then((response) => parseResponse<DataTransferJob>(response)) }, exportData: (format: (typeof DATA_TRANSFER_FORMAT)[keyof typeof DATA_TRANSFER_FORMAT] = DATA_TRANSFER_FORMAT.JSON) => api.post<DataTransferJob>('/tracking/data/export/?data_format=' + format, {}), listJobs: () => api.get<DataTransferJob[]>('/tracking/data/jobs/'), getJobStatus: (jobId: string | number) => api.get<DataTransferJob>('/tracking/data/jobs/' + jobId + '/'), confirmJobImport: (jobId: string | number, importMode: string) => api.post<DataTransferJob>('/tracking/data/jobs/' + jobId + '/confirm/', { import_mode: importMode }), cancelJobImport: (jobId: string | number) => api.post<DataTransferJob>('/tracking/data/jobs/' + jobId + '/cancel/', {}),
}

export const calendarAPI = { get: (params?: QueryParams) => api.get<{ results: CalendarItem[] }>('/calendar/', { params }) }
export const socialAPI = { getFeed: () => api.get<WatchEntry[]>('/social/feed/') }
export default api
