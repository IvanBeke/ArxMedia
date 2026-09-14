<template>
  <div>
    <div v-if="$slots.default" class="flex flex-wrap gap-2 mb-4">
      <slot />
    </div>
    <div v-if="$slots.rating" class="mb-4">
      <p class="text-xs text-gray-500 mb-1.5 uppercase tracking-wider">Your Rating</p>
      <slot name="rating" />
    </div>
    <div v-if="$slots.messages">
      <slot name="messages" />
    </div>
  </div>
</template>
