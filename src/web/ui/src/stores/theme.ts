import { defineStore } from 'pinia'

export const useThemeStore = defineStore('theme', {
  state: () => ({ isDark: true }),
  actions: {
    init() { const saved = localStorage.getItem('theme'); this.isDark = saved ? saved === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches; this.apply() },
    toggle() { this.isDark = !this.isDark; localStorage.setItem('theme', this.isDark ? 'dark' : 'light'); this.apply() },
    apply() { document.documentElement.classList.toggle('dark', this.isDark) },
  },
})
