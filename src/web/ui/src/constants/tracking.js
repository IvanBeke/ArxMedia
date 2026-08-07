export const MEDIA_TYPE = Object.freeze({
  MOVIE: 'movie',
  TV: 'tv',
})

export const WATCH_ENTRY_MEDIA_TYPE = Object.freeze({
  MOVIE: 'movie',
  EPISODE: 'episode',
})

export const WATCH_ENTRY_STATUS = Object.freeze({
  WATCHED: 'watched',
  WATCHING: 'watching',
  PLAN_TO_WATCH: 'plan_to_watch',
  ON_HOLD: 'on_hold',
  DROPPED: 'dropped',
})

export const LIST_PRIVACY = Object.freeze({
  PUBLIC: 'public',
  PRIVATE: 'private',
  FOLLOWERS: 'followers',
})

export const DATA_TRANSFER_FORMAT = Object.freeze({
  JSON: 'json',
  CSV: 'csv',
  ZIP: 'zip',
})

export const DATA_TRANSFER_STATUS = Object.freeze({
  PENDING: 'pending',
  PROCESSING: 'processing',
  AWAITING_CONFIRMATION: 'awaiting_confirmation',
  DONE: 'done',
  FAILED: 'failed',
})

export const DATA_IMPORT_MODE = Object.freeze({
  NEW_ITEMS: 'new_items',
  UPDATE_EXISTING: 'update_existing',
  MIRROR_IMPORTED_SET: 'mirror_imported_set',
})
