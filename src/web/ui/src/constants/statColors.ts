// Full class names, so Tailwind finds them. Movies and shows (and their episodes) keep one colour everywhere.
export const MEDIA_COLOR = Object.freeze({
  movie: { text: 'text-blue-500', bg: 'bg-blue-500' },
  tv: { text: 'text-brand-500', bg: 'bg-brand-500' },
} as const)

export const STATUS_COLOR = Object.freeze({
  watching: { text: 'text-brand-500', bg: 'bg-brand-500' },
  watched: { text: 'text-emerald-600', bg: 'bg-emerald-600' },
  plan_to_watch: { text: 'text-indigo-600', bg: 'bg-indigo-600' },
  dropped: { text: 'text-rose-600', bg: 'bg-rose-600' },
} as const)
