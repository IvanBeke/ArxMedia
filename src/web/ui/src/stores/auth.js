import { defineStore } from 'pinia'
import { authAPI } from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    loading: false,
    error: null,
    initPromise: null,
  }),
  getters: {
    isAuthenticated: (state) => !!state.user,
  },
  actions: {
    async fetchMe() {
      try {
        const data = await authAPI.me()
        this.user = data
      } catch {
        this.user = null
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }
    },
    async login(credentials) {
      this.loading = true
      this.error = null
      try {
        const data = await authAPI.login(credentials)
        localStorage.setItem('access_token', data.access)
        localStorage.setItem('refresh_token', data.refresh)
        await this.fetchMe()
        return true
      } catch (e) {
        this.error = e.detail || 'Login failed'
        return false
      } finally {
        this.loading = false
      }
    },
    async register(payload) {
      this.loading = true
      this.error = null
      try {
        await authAPI.register(payload)
        return await this.login({ username: payload.username, password: payload.password })
      } catch (e) {
        this.error = e ? Object.values(e).flat().join(' ') : 'Registration failed'
        return false
      } finally {
        this.loading = false
      }
    },
    logout() {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      this.user = null
    },
    async init() {
      if (!localStorage.getItem('access_token') || this.user) {
        return
      }
      if (!this.initPromise) {
        this.initPromise = this.fetchMe().finally(() => {
          this.initPromise = null
        })
      }
      await this.initPromise
    }
  }
})
