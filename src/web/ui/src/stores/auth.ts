import { defineStore } from 'pinia'
import { authAPI } from '@/api'
import type { ApiError, LoginPayload, RegisterPayload, User } from '@/types/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null as User | null, loading: false, error: null as string | null, initPromise: null as Promise<void> | null }),
  getters: { isAuthenticated: (state) => !!state.user },
  actions: {
    async fetchMe() { try { this.user = await authAPI.me() } catch { this.user = null; localStorage.removeItem('access_token'); localStorage.removeItem('refresh_token') } },
    async login(credentials: LoginPayload) { this.loading = true; this.error = null; try { const data = await authAPI.login(credentials); localStorage.setItem('access_token', data.access); localStorage.setItem('refresh_token', data.refresh); await this.fetchMe(); return true } catch (error: unknown) { const response = error as ApiError; const values = Object.values(response).flat(); this.error = response.detail || response.non_field_errors?.[0] || (Array.isArray(error) ? error[0] : null) || values.find((value): value is string => typeof value === 'string' && Boolean(value)) || 'Login failed'; return false } finally { this.loading = false } },
    async register(payload: RegisterPayload) { this.loading = true; this.error = null; try { await authAPI.register(payload); return await this.login({ username: payload.username, password: payload.password }) } catch (error: unknown) { this.error = error && typeof error === 'object' ? Object.values(error).flat().filter((value): value is string => typeof value === 'string').join(' ') : 'Registration failed'; return false } finally { this.loading = false } },
    logout() { localStorage.removeItem('access_token'); localStorage.removeItem('refresh_token'); this.user = null },
    async init() { if (!localStorage.getItem('access_token') || this.user) return; if (!this.initPromise) this.initPromise = this.fetchMe().finally(() => { this.initPromise = null }); await this.initPromise },
  },
})
