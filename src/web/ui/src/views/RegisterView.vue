<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-20">
    <div class="w-full max-w-sm">
      <div class="text-center mb-8">
        <img
          :src="'/static/branding/arxmedia/logo-full.svg'"
          alt="ArxMedia logo"
          class="h-10 w-auto mx-auto mb-3"
        />
        <h1 class="font-display text-2xl text-primary font-semibold">Create Account</h1>
        <p class="text-gray-500 text-sm mt-1">Start tracking your watch history</p>
      </div>

      <div class="card p-6">
        <div v-if="auth.error" class="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
          {{ auth.error }}
        </div>

        <div class="space-y-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1">Username</label>
            <input v-model="form.username" type="text" class="input rounded-md" placeholder="cooluser123" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Email</label>
            <input v-model="form.email" type="email" class="input rounded-md" placeholder="you@example.com" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Password</label>
            <input v-model="form.password" type="password" class="input rounded-md" placeholder="At least 8 characters" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Confirm Password</label>
            <input v-model="form.password2" type="password" class="input rounded-md" placeholder="••••••••" @keydown.enter="submit" />
          </div>
        </div>

        <button @click="submit" :disabled="auth.loading" class="btn-primary w-full mt-5 py-2.5 rounded-md">
          <span v-if="auth.loading">Creating account...</span>
          <span v-else>Create Account</span>
        </button>

        <p class="text-center text-sm text-gray-500 mt-5">
          Already have an account?
          <RouterLink to="/login" class="text-brand-400 hover:text-brand-300">Sign in</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const form = ref({ username: '', email: '', password: '', password2: '' })

async function submit() {
  const ok = await auth.register(form.value)
  if (ok) router.push('/dashboard')
}
</script>
