<template>
  <div class="min-h-screen bg-surface">
    <AppNav />
    <main>
      <RouterView v-slot="{ Component }">
        <Transition name="fade">
          <component :is="Component" :key="$route.path" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<script setup lang="ts">
import AppNav from '@/components/AppNav.vue'
</script>
