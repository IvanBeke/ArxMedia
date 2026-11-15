<template>
  <div class="min-h-screen bg-surface">
    <AppNav />
    <main>
      <RouterView v-slot="{ Component }">
        <Transition name="fade">
          <component :is="Component" :key="`${$route.path}|${locale}`" />
        </Transition>
      </RouterView>
    </main>
    <PwaStatus />
  </div>
</template>

<script setup lang="ts">
import AppNav from '@/components/AppNav.vue'
import PwaStatus from '@/components/PwaStatus.vue'
import { useI18n } from '@/i18n'

// Views remount when the language changes so they reload their data in it.
const { locale } = useI18n()
</script>
