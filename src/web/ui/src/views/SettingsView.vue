<template>
  <div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="font-display text-2xl text-primary font-semibold mb-6">{{ t('settings_title') }}</h1>

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
            <label class="block text-xs text-gray-400 mb-1">{{ t('settings_username') }}</label>
            <input v-model="form.username" class="input rounded-md" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">{{ t('settings_email') }}</label>
            <input v-model="form.email" type="email" class="input rounded-md" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">{{ t('settings_bio') }}</label>
            <textarea v-model="form.bio" class="input rounded-md resize-none" rows="3" :placeholder="t('settings_bio_placeholder')"></textarea>
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">{{ t('settings_location') }}</label>
            <input v-model="form.location" class="input rounded-md" :placeholder="t('settings_location_placeholder')" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">{{ t('settings_provider_region') }}</label>
            <select v-model="form.preferred_region" class="input rounded-md">
              <option v-for="region in providerRegions" :key="region" :value="region">{{ region }}</option>
            </select>
          </div>
        </div>

        <button @click="saveProfile" class="btn-primary text-sm" :disabled="saving">
          {{ saving ? t('settings_saving') : t('settings_save_profile') }}
        </button>
      </div>

      <!-- Privacy Settings -->
      <div class="card p-6 space-y-4">
        <h2 class="text-sm font-medium text-primary">{{ t('settings_privacy') }}</h2>

        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="min-w-0">
            <p class="text-sm text-primary">{{ t('settings_account_visibility') }}</p>
            <p class="text-xs text-gray-500">{{ t('settings_visibility_hint') }}</p>
          </div>
          <select v-model="form.account_visibility" @change="updateAccountVisibility" class="input rounded-md text-sm w-full sm:w-auto sm:max-w-[220px]">
            <option :value="ACCOUNT_VISIBILITY.PUBLIC">{{ t('common_public') }}</option>
            <option :value="ACCOUNT_VISIBILITY.PRIVATE">{{ t('common_private') }}</option>
            <option :value="ACCOUNT_VISIBILITY.FRIENDS_ONLY">{{ t('settings_friends_only') }}</option>
          </select>
        </div>
      </div>

      <div class="card p-6 space-y-4">
        <h2 class="text-sm font-medium text-primary">{{ t('settings_language') }}</h2>
        <select v-model="selectedLocale" @change="updateLocale" class="input rounded-md text-sm w-full sm:w-auto sm:max-w-[220px]">
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
            :aria-label="t('settings_spoiler_toggle')"
          >
            <div
              class="absolute top-1 w-4 h-4 rounded-full bg-white transition-transform duration-200"
              :class="prefs.spoilerMode ? 'left-7' : 'left-1'"
            ></div>
          </button>
        </div>
      </div>

      <div class="card p-6 space-y-4">
        <h2 class="text-sm font-medium text-primary">{{ t('pwa_settings_title') }}</h2>
        <p class="text-xs text-gray-500">{{ offlineReady ? t('pwa_settings_ready') : t('pwa_settings_not_ready') }}</p>
        <div v-if="canInstall || needRefresh" class="flex flex-wrap gap-2">
          <button v-if="canInstall" @click="install" class="btn-primary text-sm">
            {{ t('pwa_settings_install') }}
          </button>
          <button v-if="needRefresh && installedApp" @click="update" class="btn-primary text-sm">
            {{ t('pwa_settings_update') }}
          </button>
        </div>
      </div>

      <!-- Change Password -->
      <div class="card p-6 space-y-4">
        <h2 class="text-sm font-medium text-primary">{{ t('settings_change_password') }}</h2>

        <div class="space-y-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1">{{ t('settings_current_password') }}</label>
            <input v-model="passwordForm.currentPassword" type="password" class="input rounded-md" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">{{ t('settings_new_password') }}</label>
            <input v-model="passwordForm.newPassword" type="password" class="input rounded-md" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">{{ t('settings_confirm_password') }}</label>
            <input v-model="passwordForm.confirmPassword" type="password" class="input rounded-md" />
          </div>
        </div>

        <button @click="changePassword" class="btn-primary text-sm" :disabled="changingPassword">
          {{ changingPassword ? t('settings_changing') : t('settings_change_password') }}
        </button>
      </div>
    </div>

    <LoadError v-else :message="loadError || t('error_load_settings')" @retry="loadProfile" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { authAPI } from '@/api'
import LoadError from '@/components/LoadError.vue'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { useI18n } from '@/i18n'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { usePwa } from '@/composables/usePwa'
import { ACCOUNT_VISIBILITY } from '@/constants/tracking'
import { getApiErrorMessage } from '@/utils/errors'
import type { ApiError, ProfileUpdatePayload, User } from '@/types/api'

type ProfileForm = Required<Pick<ProfileUpdatePayload, 'username' | 'email' | 'bio' | 'location' | 'preferred_region' | 'account_visibility'>>

const router = useRouter()
const auth = useAuthStore()
const prefs = usePreferencesStore()
const { t } = useI18n()
const user = ref<User | null>(null)
const loading = ref(true)
const saving = ref(false)
const changingPassword = ref(false)
const { successMsg, showSuccess } = useFlashMessages({ successDurationMs: 3000 })
const { offlineReady, canInstall, needRefresh, installedApp, install, update } = usePwa()
const errorMsg = ref('')
const loadError = ref('')
const selectedLocale = ref(prefs.locale)

const form = ref<ProfileForm>({
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

async function loadProfile() {
  loading.value = true
  loadError.value = ''
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
  } catch (error: unknown) {
    loadError.value = getApiErrorMessage(error, t('error_load_settings'))
  } finally {
    loading.value = false
  }
}

onMounted(loadProfile)

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
      showSuccess(t('settings_profile_ok'))
    }
  } catch (error: unknown) {
    errorMsg.value = (error as ApiError).detail || t('settings_update_failed')
  } finally {
    saving.value = false
  }
}

async function updateAccountVisibility() {
  try {
    const data = await authAPI.updateProfile({ account_visibility: form.value.account_visibility })
    if (user.value) {
      user.value.account_visibility = data.account_visibility
    }
    if (auth.user) {
      auth.user.account_visibility = data.account_visibility
    }
    showSuccess(t('settings_visibility_set', { value: data.account_visibility.replace('_', ' ') }))
  } catch (error: unknown) {
    errorMsg.value = getApiErrorMessage(error, t('error_update_visibility'))
    if (user.value) form.value.account_visibility = user.value.account_visibility
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
    errorMsg.value = t('settings_password_mismatch')
    return
  }
  if (!passwordForm.value.currentPassword) {
    errorMsg.value = t('settings_password_required')
    return
  }
  if (passwordForm.value.newPassword.length < 8) {
    errorMsg.value = t('settings_password_short')
    return
  }

  changingPassword.value = true
  errorMsg.value = ''
  try {
    await authAPI.changePassword({
      current_password: passwordForm.value.currentPassword,
      new_password: passwordForm.value.newPassword
    })
    showSuccess(t('settings_password_ok'))
    passwordForm.value = {
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    }
  } catch (error: unknown) {
    const apiError = error as ApiError
    if (Array.isArray(apiError.current_password) && typeof apiError.current_password[0] === 'string') {
      errorMsg.value = apiError.current_password[0]
    } else if (Array.isArray(apiError.new_password) && typeof apiError.new_password[0] === 'string') {
      errorMsg.value = apiError.new_password[0]
    } else if (apiError.detail) {
      errorMsg.value = apiError.detail
    } else {
      errorMsg.value = t('settings_password_failed')
    }
  } finally {
    changingPassword.value = false
  }
}
</script>
