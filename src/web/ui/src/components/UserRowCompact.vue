<template>
  <div class="flex items-center gap-2 min-w-0">
    <UserAvatar :username="user.username" :src="user.avatar" size="xs" />
    <span class="truncate text-sm text-primary">{{ user.username }}</span>
  </div>
</template>

<script setup lang="ts">
import UserAvatar from '@/components/UserAvatar.vue'
import type { UserCard } from '@/types/api'

defineProps<{
  user: UserCard
}>()
</script>
