export const MEDIA_TYPE = Object.freeze({
  MOVIE: 'movie',
  TV: 'tv',
} as const)

export const WATCH_ENTRY_MEDIA_TYPE = Object.freeze({
  MOVIE: 'movie',
  EPISODE: 'episode',
} as const)

export const WATCH_ENTRY_STATUS = Object.freeze({
  NONE: 'none',
  WATCHED: 'watched',
  WATCHING: 'watching',
  PLAN_TO_WATCH: 'plan_to_watch',
  DROPPED: 'dropped',
} as const)

export const LIST_PRIVACY = Object.freeze({
  PUBLIC: 'public',
  PRIVATE: 'private',
} as const)

export const ACCOUNT_VISIBILITY = Object.freeze({
  PUBLIC: 'public',
  PRIVATE: 'private',
  FRIENDS_ONLY: 'friends_only',
} as const)

export const DATA_TRANSFER_FORMAT = Object.freeze({
  JSON: 'json',
  CSV: 'csv',
  ZIP: 'zip',
} as const)

export const DATA_TRANSFER_STATUS = Object.freeze({
  PENDING: 'pending',
  PROCESSING: 'processing',
  AWAITING_CONFIRMATION: 'awaiting_confirmation',
  DONE: 'done',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const)

export const DATA_IMPORT_MODE = Object.freeze({
  NEW_ITEMS: 'new_items',
  UPDATE_EXISTING: 'update_existing',
  MIRROR_IMPORTED_SET: 'mirror_imported_set',
} as const)
