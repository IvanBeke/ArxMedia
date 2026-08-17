<template>
  <div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="font-display text-2xl text-primary font-semibold mb-6">Settings</h1>

    <div v-if="loading" class="space-y-4">
      <div v-for="n in 6" :key="n" class="h-12 skeleton rounded-md"></div>
    </div>

    <div v-else-if="user" class="space-y-6">
      <!-- Profile Settings -->
      <div class="card p-6 space-y-5">
        <h2 class="text-sm font-medium text-primary">{{ t('settings_profile') }}</h2>

        <div v-if="successMsg" class="px-3 py-2 bg-green-500/10 border border-green-500/20 text-green-400 rounded-md text-sm">
          {{ successMsg }}
        </div>
        <div v-if="errorMsg" class="px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
          {{ errorMsg }}
        </div>

        <div class="space-y-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1">Username</label>
            <input v-model="form.username" class="input rounded-md" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Email</label>
            <input v-model="form.email" type="email" class="input rounded-md" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Bio</label>
            <textarea v-model="form.bio" class="input rounded-md resize-none" rows="3" placeholder="Tell others about yourself..."></textarea>
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Location</label>
            <input v-model="form.location" class="input rounded-md" placeholder="City, Country" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Provider Region</label>
            <select v-model="form.preferred_region" class="input rounded-md">
              <option v-for="region in providerRegions" :key="region" :value="region">{{ region }}</option>
            </select>
          </div>
        </div>

        <button @click="saveProfile" class="btn-primary text-sm" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save Profile' }}
        </button>
      </div>

      <!-- Privacy Settings -->
      <div class="card p-6 space-y-4">
        <h2 class="text-sm font-medium text-primary">{{ t('settings_privacy') }}</h2>

        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-primary">Account Visibility</p>
            <p class="text-xs text-gray-500">Choose who can view your profile activity and social graph</p>
          </div>
          <select v-model="form.account_visibility" @change="updateAccountVisibility" class="input rounded-md text-sm max-w-[220px]">
            <option :value="ACCOUNT_VISIBILITY.PUBLIC">Public</option>
            <option :value="ACCOUNT_VISIBILITY.PRIVATE">Private</option>
            <option :value="ACCOUNT_VISIBILITY.FRIENDS_ONLY">Friends only</option>
          </select>
        </div>
      </div>

      <div class="card p-6 space-y-4">
        <h2 class="text-sm font-medium text-primary">{{ t('settings_language') }}</h2>
        <select v-model="selectedLocale" @change="updateLocale" class="input rounded-md text-sm max-w-[220px]">
          <option value="en">English</option>
          <option value="es">Español</option>
        </select>
      </div>

      <div class="card p-6 space-y-4">
        <h2 class="text-sm font-medium text-primary">{{ t('settings_spoiler_mode') }}</h2>
        <div class="flex items-center justify-between gap-3">
          <p class="text-xs text-gray-500">{{ t('settings_spoiler_mode_desc') }}</p>
          <button
            @click="toggleSpoilerMode"
            class="relative w-12 h-6 rounded-full transition-colors duration-200"
            :class="prefs.spoilerMode ? 'bg-brand-500' : 'bg-surface-200'"
            aria-label="Toggle spoiler mode"
          >
            <div
              class="absolute top-1 w-4 h-4 rounded-full bg-white transition-transform duration-200"
              :class="prefs.spoilerMode ? 'left-7' : 'left-1'"
            ></div>
          </button>
        </div>
      </div>

      <!-- Change Password -->
      <div class="card p-6 space-y-4">
        <h2 class="text-sm font-medium text-primary">Change Password</h2>

        <div class="space-y-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1">Current Password</label>
            <input v-model="passwordForm.currentPassword" type="password" class="input rounded-md" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">New Password</label>
            <input v-model="passwordForm.newPassword" type="password" class="input rounded-md" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Confirm New Password</label>
            <input v-model="passwordForm.confirmPassword" type="password" class="input rounded-md" />
          </div>
        </div>

        <button @click="changePassword" class="btn-primary text-sm" :disabled="changingPassword">
          {{ changingPassword ? 'Changing...' : 'Change Password' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { authAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { useI18n } from '@/i18n'
import { ACCOUNT_VISIBILITY } from '@/constants/tracking'

const router = useRouter()
const auth = useAuthStore()
const prefs = usePreferencesStore()
const { t } = useI18n()
const user = ref(null)
const loading = ref(true)
const saving = ref(false)
const changingPassword = ref(false)
const successMsg = ref('')
const errorMsg = ref('')
const selectedLocale = ref(prefs.locale)

const form = ref({
  username: '',
  email: '',
  bio: '',
  location: '',
  preferred_region: 'US',
  account_visibility: ACCOUNT_VISIBILITY.PUBLIC,
})

const providerRegions = [
  'AR', 'AT', 'AU', 'BE', 'BR', 'CA', 'CH', 'CL', 'CO', 'CZ', 'DE', 'DK',
  'ES', 'FI', 'FR', 'GB', 'GR', 'HU', 'IE', 'IN', 'IT', 'JP', 'KR', 'MX',
  'NL', 'NO', 'NZ', 'PL', 'PT', 'RO', 'SE', 'TR', 'US', 'ZA'
]

const passwordForm = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

onMounted(async () => {
  try {
    const data = await authAPI.me()
    if (data) {
      user.value = data
      form.value = {
        username: data.username || '',
        email: data.email || '',
        bio: data.bio || '',
        location: data.location || '',
        preferred_region: data.preferred_region || 'US',
        account_visibility: data.account_visibility || ACCOUNT_VISIBILITY.PUBLIC,
      }
    }
  } catch (error) {
    console.error('Failed to load profile:', error)
  } finally {
    loading.value = false
  }
})

async function saveProfile() {
  saving.value = true
  successMsg.value = ''
  errorMsg.value = ''
  try {
    const data = await authAPI.updateProfile(form.value)
    if (data) {
      user.value = data
      auth.user = data
      form.value.preferred_region = data.preferred_region || form.value.preferred_region
      successMsg.value = 'Profile updated successfully!'
      setTimeout(() => successMsg.value = '', 3000)
    }
  } catch (error) {
    errorMsg.value = error.detail || 'Failed to update profile'
  } finally {
    saving.value = false
  }
}

async function updateAccountVisibility() {
  try {
    const data = await authAPI.updateProfile({ account_visibility: form.value.account_visibility })
    user.value.account_visibility = data.account_visibility
    auth.user.account_visibility = data.account_visibility
    successMsg.value = `Account visibility set to ${data.account_visibility.replace('_', ' ')}`
    setTimeout(() => successMsg.value = '', 3000)
  } catch (error) {
    console.error('Failed to update privacy:', error)
  }
}

function updateLocale() {
  prefs.setLocale(selectedLocale.value)
}

function toggleSpoilerMode() {
  prefs.setSpoilerMode(!prefs.spoilerMode)
}

async function changePassword() {
  successMsg.value = ''
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    errorMsg.value = 'New passwords do not match'
    return
  }
  if (!passwordForm.value.currentPassword) {
    errorMsg.value = 'Current password is required'
    return
  }
  if (passwordForm.value.newPassword.length < 8) {
    errorMsg.value = 'Password must be at least 8 characters'
    return
  }

  changingPassword.value = true
  errorMsg.value = ''
  try {
    await authAPI.changePassword({
      current_password: passwordForm.value.currentPassword,
      new_password: passwordForm.value.newPassword
    })
    successMsg.value = 'Password updated successfully!'
    passwordForm.value = {
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    }
    setTimeout(() => successMsg.value = '', 3000)
  } catch (error) {
    if (error?.current_password?.length) {
      errorMsg.value = error.current_password[0]
    } else if (error?.new_password?.length) {
      errorMsg.value = error.new_password[0]
    } else if (error?.detail) {
      errorMsg.value = error.detail
    } else {
      errorMsg.value = 'Failed to change password'
    }
  } finally {
    changingPassword.value = false
  }
}
</script>
