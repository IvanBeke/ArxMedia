import { defineStore } from 'pinia'


export const usePreferencesStore = defineStore('preferences', {
  state: () => ({
    spoilerMode: localStorage.getItem('spoiler_mode') === 'true',
    locale: localStorage.getItem('locale') || 'en',
  }),
  actions: {
    setSpoilerMode(enabled) {
      this.spoilerMode = !!enabled
      localStorage.setItem('spoiler_mode', this.spoilerMode ? 'true' : 'false')
    },
    setLocale(locale) {
      this.locale = locale === 'es' ? 'es' : 'en'
      localStorage.setItem('locale', this.locale)
    },
  }
})
