import { defineStore } from 'pinia'

type Locale = 'en' | 'es'

export const usePreferencesStore = defineStore('preferences', {
  state: () => ({ spoilerMode: localStorage.getItem('spoiler_mode') === 'true', locale: (localStorage.getItem('locale') || 'en') as Locale }),
  actions: {
    setSpoilerMode(enabled: boolean) { this.spoilerMode = !!enabled; localStorage.setItem('spoiler_mode', this.spoilerMode ? 'true' : 'false') },
    setLocale(locale: string) { this.locale = locale === 'es' ? 'es' : 'en'; localStorage.setItem('locale', this.locale) },
  },
})
