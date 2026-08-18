<template>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
    <div
      v-for="user in users"
      :key="`user-${user.id}`"
      class="card p-3 hover:bg-surface-200/40 transition-colors"
    >
      <div class="flex items-center gap-2.5 min-w-0">
        <img
          v-if="user.avatar"
          :src="user.avatar"
          :alt="`${user.username} avatar`"
          class="w-8 h-8 rounded-full object-cover border border-surface-200 flex-shrink-0"
          loading="lazy"
        />
        <div
          v-else
          class="w-8 h-8 rounded-full bg-brand-500/20 border border-brand-500/30 text-brand-300 text-xs font-semibold flex items-center justify-center flex-shrink-0"
        >
          {{ user.username[0]?.toUpperCase() }}
        </div>
        <RouterLink :to="`/profile/${user.username}`" class="text-primary text-sm font-semibold hover:text-brand-400 truncate">
          {{ user.username }}
        </RouterLink>
      </div>

      <p v-if="user.bio" class="text-[11px] text-muted mt-2 truncate">{{ user.bio }}</p>

      <div class="mt-2 flex items-center gap-3 text-[11px] text-muted">
        <span>
          <span class="text-primary font-semibold">{{ user.followers_count }}</span>
          <span class="ml-1">{{ followersLabel }}</span>
        </span>
        <span>
          <span class="text-primary font-semibold">{{ user.following_count }}</span>
          <span class="ml-1">{{ followingLabel }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  users: { type: Array, default: () => [] },
  followersLabel: { type: String, default: 'Followers' },
  followingLabel: { type: String, default: 'Following' },
})
</script>
