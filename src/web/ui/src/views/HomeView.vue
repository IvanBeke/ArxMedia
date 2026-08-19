<template>
  <div>
    <section class="relative overflow-hidden min-h-[60vh] flex items-center">
      <div class="absolute inset-0 z-0">
        <div class="absolute inset-0 bg-gradient-to-b from-surface via-surface/70 to-surface"></div>
        <div class="absolute inset-0 bg-gradient-to-r from-surface/90 to-transparent"></div>
      </div>

      <div class="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div class="max-w-xl">
          <div class="inline-flex items-center gap-2 mb-4 px-3 py-1 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-500 text-xs">
            <span class="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse"></span>
            Track · Rate · Discover
          </div>
          <h1 class="font-display text-5xl md:text-7xl text-primary font-semibold leading-tight mb-4">
            Never lose track of<br />what you're <span class="text-brand-500">watching</span>
          </h1>
          <p class="text-muted text-base mb-6">
            Track every movie and TV show. Build your watchlist, log what you watched, and keep your progress organized in one place.
          </p>
          <div class="flex gap-3">
            <RouterLink to="/login" class="btn-primary px-5 py-2.5 text-sm">
              Log in
            </RouterLink>
            <RouterLink to="/register" class="btn-ghost px-5 py-2.5 text-sm bg-surface-100 border-surface-300 text-secondary hover:bg-surface-200 hover:text-primary">
              Create account
            </RouterLink>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
