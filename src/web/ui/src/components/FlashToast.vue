<template>
  <div class="fixed bottom-4 inset-x-0 z-50 flex flex-col items-center gap-2 px-4 pointer-events-none">
    <TransitionGroup name="fade">
      <div
        v-for="message in visibleMessages"
        :key="`${message.kind}:${message.text}`"
        :role="message.kind === 'error' ? 'alert' : 'status'"
        class="pointer-events-auto max-w-md px-3 py-2 rounded-md border shadow-lg bg-surface-100 text-sm"
        :class="message.kind === 'error' ? 'border-red-500/40 text-red-400' : 'border-green-500/40 text-green-400'"
      >
        {{ message.text }}
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

// Fixed to the viewport so showing or hiding a message never shifts the page layout.
type FlashMessage = { text: string | null | undefined; kind: 'success' | 'error' }

const props = defineProps<{ messages: FlashMessage[] }>()

const visibleMessages = computed(() =>
  props.messages.filter((message): message is { text: string; kind: FlashMessage['kind'] } => Boolean(message.text)),
)
</script>
