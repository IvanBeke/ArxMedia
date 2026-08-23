<template>
  <div class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-6 sm:py-8 overflow-x-hidden">
    <h1 class="font-display text-2xl text-primary font-semibold mb-6">{{ title }}</h1>

    <Transition name="fade">
      <div v-if="quickActionError" class="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
        {{ quickActionError }}
      </div>
    </Transition>

    <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <div v-for="n in 15" :key="n" class="aspect-[2/3] rounded-md skeleton"></div>
    </div>

    <div v-else-if="items.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <MediaCard
        v-for="item in items"
        :key="item.id"
        :item="item"
        :media-type="mediaType"
        @error="showQuickActionError"
      />
    </div>

    <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-8">
      <button @click="page--; load()" :disabled="page <= 1" class="btn-ghost text-sm px-3 py-1.5 rounded-md" :class="{ 'opacity-50': page <= 1 }">
        Prev
      </button>
      <span class="text-gray-400 text-xs sm:text-sm">Page {{ page }} of {{ totalPages }}</span>
      <button @click="page++; load()" :disabled="page >= totalPages" class="btn-ghost text-sm px-3 py-1.5 rounded-md" :class="{ 'opacity-50': page >= totalPages }">
        Next
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { mediaAPI } from '@/api'
import MediaCard from '@/components/MediaCard.vue'
import { useFlashMessages } from '@/composables/useFlashMessages'

const props = defineProps({
  title: { type: String, required: true },
  mediaType: { type: String, required: true },
})

const items = ref([])
const loading = ref(true)
const page = ref(1)
const totalPages = ref(1)
const { errorMsg: quickActionError, showError: showQuickActionError } = useFlashMessages()

async function load() {
  loading.value = true
  items.value = []
  try {
    const data = await mediaAPI.popular(props.mediaType, page.value)
    if (data) {
      items.value = data.results || []
      totalPages.value = data.total_pages || 1
    }
  } catch (error) {
    console.error('Failed to load popular media:', error)
    items.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
