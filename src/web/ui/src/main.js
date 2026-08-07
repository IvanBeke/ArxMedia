import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

async function bootstrap() {
  const pinia = createPinia()

  const authStore = useAuthStore(pinia)
  const themeStore = useThemeStore(pinia)

  themeStore.init()
  await authStore.init()

  const app = createApp(App)
  app.use(pinia)
  app.use(router)
  app.mount('#app')
}

bootstrap()
