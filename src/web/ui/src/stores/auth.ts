import { defineStore } from 'pinia'
import { authAPI } from '@/api'
import type { ApiError, LoginPayload, RegisterPayload, User } from '@/types/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null as User | null, loading: false, error: null as string | null, initPromise: null as Promise<void> | null, checked: false }),
  getters: { isAuthenticated: (state) => !!state.user },
  actions: {
    async fetchMe() { try { this.user = await authAPI.me() } catch { this.user = null } finally { this.checked = true } },
    async login(credentials: LoginPayload) { this.loading = true; this.error = null; try { this.user = await authAPI.login(credentials); return true } catch (error: unknown) { const response = error as ApiError; const values = Object.values(response).flat(); this.error = response.detail || response.non_field_errors?.[0] || (Array.isArray(error) ? error[0] : null) || values.find((value): value is string => typeof value === 'string' && Boolean(value)) || 'Login failed'; return false } finally { this.loading = false } },
    async register(payload: RegisterPayload) { this.loading = true; this.error = null; try { this.user = await authAPI.register(payload); return true } catch (error: unknown) { this.error = error && typeof error === 'object' ? Object.values(error).flat().filter((value): value is string => typeof value === 'string').join(' ') : 'Registration failed'; return false } finally { this.loading = false } },
    async logout() { try { await authAPI.logout() } finally { this.user = null } },
    async init() { if (this.checked || this.user) return; if (!this.initPromise) this.initPromise = this.fetchMe().finally(() => { this.initPromise = null }); await this.initPromise },
  },
})
