<template>
  <div class="min-h-screen bg-surface">
    <AppNav />
    <main>
      <RouterView v-slot="{ Component }">
        <Transition name="fade">
          <component :is="Component" :key="$route.fullPath" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<script setup>
import AppNav from '@/components/AppNav.vue'
</script>
