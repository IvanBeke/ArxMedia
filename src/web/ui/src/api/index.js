const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
import {
  DATA_TRANSFER_FORMAT,
  MEDIA_TYPE,
} from '@/constants/tracking'

let isRefreshing = false
let refreshSubscribers = []

async function parseResponse(response) {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    if (payload && typeof payload === 'object') {
      throw { ...payload, status: response.status }
    }
    throw { detail: `Request failed (${response.status})`, status: response.status }
  }
  return payload
}

async function refreshAccessToken(origin) {
  const refresh = localStorage.getItem('refresh_token')
  if (!refresh) {
    throw new Error('Missing refresh token')
  }

  if (isRefreshing) {
    return new Promise((resolve, reject) => {
      refreshSubscribers.push({ resolve, reject })
    })
  }

  isRefreshing = true
  try {
    const refreshResp = await fetch(origin + '/api/auth/token/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh })
    })
    const refreshData = await parseResponse(refreshResp)
    if (!refreshData?.access) {
      throw new Error('Refresh token response missing access token')
    }

    localStorage.setItem('access_token', refreshData.access)
    refreshSubscribers.forEach(({ resolve }) => resolve(refreshData.access))
    refreshSubscribers = []
    return refreshData.access
  } catch (error) {
    refreshSubscribers.forEach(({ reject }) => reject(error))
    refreshSubscribers = []
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    window.location.href = '/login'
    throw error
  } finally {
    isRefreshing = false
  }
}

async function request(method, url, data = null, params = null) {
  const fullUrl = new URL(baseURL + url, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        fullUrl.searchParams.append(key, value)
      }
    })
  }

  const options = {
    method,
    headers: { 'Content-Type': 'application/json' }
  }

  const token = localStorage.getItem('access_token')
  if (token) {
    options.headers.Authorization = `Bearer ${token}`
  }

  if (data && method !== 'GET' && method !== 'HEAD') {
    options.body = JSON.stringify(data)
  }

  let response = await fetch(fullUrl.toString(), options)

  if (response.status === 401 && !url.includes('/token/refresh/')) {
    const refreshToken = localStorage.getItem('refresh_token')
    if (refreshToken) {
      const nextToken = await refreshAccessToken(fullUrl.origin)
      options.headers.Authorization = `Bearer ${nextToken}`
      response = await fetch(fullUrl.toString(), options)
    }
  }

  return parseResponse(response)
}

const api = {
  get: (url, options = {}) => request('GET', url, null, options.params),
  post: (url, data) => request('POST', url, data),
  patch: (url, data) => request('PATCH', url, data),
  delete: (url) => request('DELETE', url),
}

// Auth
export const authAPI = {
  register: (data) => api.post('/auth/register/', data),
  login: (data) => api.post('/auth/login/', data),
  me: () => api.get('/auth/me/'),
  updateProfile: (data) => api.patch('/auth/me/', data),
  searchUsers: (q) => api.get('/auth/users/search/', { params: { q } }),
  getUser: (username) => api.get(`/auth/users/${username}/`),
  getFollowers: (username, params) => api.get(`/auth/users/${username}/followers/`, { params }),
  getFollowing: (username, params) => api.get(`/auth/users/${username}/following/`, { params }),
  follow: (username) => api.post(`/auth/users/${username}/follow/`),
  changePassword: (data) => api.post('/auth/password/change/', data),
}

// Media
export const mediaAPI = {
  search: (q, type = 'multi', page = 1) => api.get('/media/search/', { params: { q, type, page } }),
  genres: () => api.get('/media/genres/'),
  trending: (type = 'all', window = 'week') => api.get('/media/trending/', { params: { type, window } }),
  popular: (type = MEDIA_TYPE.MOVIE, page = 1) => api.get('/media/popular/', { params: { type, page } }),
  getMovie: (id, region) => api.get(`/media/movies/${id}/`, { params: { region } }),
  refreshMovie: (id) => api.post(`/media/movies/${id}/refresh/`, {}),
  getMovieCredits: (id) => api.get(`/media/movies/${id}/credits/`),
  getTV: (id, region) => api.get(`/media/tv/${id}/`, { params: { region } }),
  refreshTV: (id) => api.post(`/media/tv/${id}/refresh/`, {}),
  getTVCredits: (id) => api.get(`/media/tv/${id}/credits/`),
  getSeason: (showId, season) => api.get(`/media/tv/${showId}/seasons/${season}/`),
  getEpisodeCredits: (showId, season, episode) => api.get(`/media/tv/${showId}/seasons/${season}/episodes/${episode}/credits/`),
}

// Tracking
export const trackingAPI = {
  getHistory: (params) => api.get('/tracking/history/', { params }),
  addToHistory: (data) => api.post('/tracking/history/', data),
  deleteHistory: (id) => api.delete(`/tracking/history/${id}/`),
  removeFromHistory: async (data) => {
    const resp = await api.get('/tracking/history/', { params: { tmdb_id: data.tmdb_id, media_type: data.media_type } })
    const entries = resp.results || resp
    const entry = entries.find(e => 
      e.tmdb_id == data.tmdb_id && 
      e.media_type === data.media_type &&
      (!data.season_number || e.season_number == data.season_number) &&
      (!data.episode_number || e.episode_number == data.episode_number)
    )
    if (entry) {
      return api.delete(`/tracking/history/${entry.id}/`)
    }
  },
  markEpisodeWatched: (data) => api.post('/tracking/episodes/mark/', data),
  unmarkEpisodeWatched: (data) => api.post('/tracking/episodes/unmark/', data),
  markSeasonWatched: (data) => api.post('/tracking/seasons/mark/', data),
  unmarkSeasonWatched: (data) => api.post('/tracking/seasons/unmark/', data),
  unmarkShowWatched: (data) => api.post('/tracking/shows/unmark/', data),
  getWatchedEpisodes: (tmdbId) => api.get('/tracking/episodes/watched/', { params: { tmdb_id: tmdbId } }),
  getWatchlist: (params) => api.get('/tracking/watchlist/', { params }),
  addToWatchlist: (data) => api.post('/tracking/watchlist/', data),
  removeFromWatchlist: (id) => api.delete(`/tracking/watchlist/${id}/`),
  getRatings: (params) => api.get('/tracking/ratings/', { params }),
  rate: (data) => api.post('/tracking/ratings/', data),
  getStats: () => api.get('/tracking/stats/'),
  getUpNext: () => api.get('/tracking/up-next/'),
  getMyShows: (params) => api.get('/tracking/my-shows/', { params }),
  getMyMovies: (params) => api.get('/tracking/my-movies/', { params }),
  getUpcoming: () => api.get('/tracking/upcoming/'),
  dropMedia: (data) => api.post('/tracking/media/drop/', data),
  getLists: () => api.get('/tracking/lists/'),
  createList: (data) => api.post('/tracking/lists/', data),
  getList: (id) => api.get(`/tracking/lists/${id}/`),
  getListItems: (listId, params) => api.get(`/tracking/lists/${listId}/items/`, { params }),
  updateList: (id, data) => api.patch(`/tracking/lists/${id}/`, data),
  deleteList: (id) => api.delete(`/tracking/lists/${id}/`),
  addToList: (listId, data) => api.post(`/tracking/lists/${listId}/items/`, data),
  removeFromList: (listId, itemId) => api.delete(`/tracking/lists/${listId}/items/${itemId}/`),
  reorderList: (listId, orderedIds) => api.post(`/tracking/lists/${listId}/items/reorder/`, { custom_order: orderedIds }),
  addCollaborator: (listId, userId) => api.post(`/tracking/lists/${listId}/collaborators/`, { user_id: userId }),
  removeCollaborator: (listId, userId) => api.delete(`/tracking/lists/${listId}/collaborators/${userId}/`),
  getRecommendations: () => api.get('/tracking/recommendations/'),
  importData: (file, format = DATA_TRANSFER_FORMAT.JSON, source) => {
    const form = new FormData()
    form.append('file', file)
    const fullUrl = new URL(baseURL + '/tracking/data/import/', window.location.origin)
    fullUrl.searchParams.set('data_format', format)
    fullUrl.searchParams.set('source', source)
    const token = localStorage.getItem('access_token')
    return fetch(fullUrl.toString(), {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form
    }).then(async (r) => {
      const data = await r.json().catch(() => ({}))
      if (!r.ok) throw data
      return data
    })
  },
  exportData: (format = DATA_TRANSFER_FORMAT.JSON) => api.post(`/tracking/data/export/?data_format=${format}`, {}),
  listJobs: () => api.get('/tracking/data/jobs/'),
  getJobStatus: (jobId) => api.get(`/tracking/data/jobs/${jobId}/`),
  confirmJobImport: (jobId, importMode) => api.post(`/tracking/data/jobs/${jobId}/confirm/`, { import_mode: importMode }),
}

export const calendarAPI = {
  get: (params) => api.get('/calendar/', { params }),
}

// Social
export const socialAPI = {
  getFeed: () => api.get('/social/feed/'),
}

export default api
