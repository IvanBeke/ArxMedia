<template>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
    <div
      v-for="user in users"
      :key="`user-${user.id}`"
      class="card p-3 hover:bg-surface-200/40 transition-colors"
    >
      <div class="flex items-center gap-2.5 min-w-0">
        <UserAvatar :username="user.username" :src="user.avatar" />
        <RouterLink :to="`/profile/${user.username}`" class="text-primary text-sm font-semibold hover:text-brand-400 truncate">
          {{ user.username }}
        </RouterLink>
      </div>

      <p v-if="user.bio" class="text-[11px] text-muted mt-2 truncate">{{ user.bio }}</p>

      <div class="mt-2 flex items-center gap-3 text-[11px] text-muted">
        <span>
          <span class="text-primary font-semibold">{{ user.followers_count }}</span>
          <span class="ml-1">{{ followersLabel || t('profile_tab_followers') }}</span>
        </span>
        <span>
          <span class="text-primary font-semibold">{{ user.following_count }}</span>
          <span class="ml-1">{{ followingLabel || t('profile_tab_following') }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import UserAvatar from '@/components/UserAvatar.vue'
import { useI18n } from '@/i18n'
import type { UserCard } from '@/types/api'

const { t } = useI18n()

withDefaults(defineProps<{
  users?: UserCard[]
  followersLabel?: string
  followingLabel?: string
}>(), {
  users: () => [], followersLabel: '', followingLabel: '',
})
</script>
