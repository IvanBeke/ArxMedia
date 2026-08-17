import { computed } from 'vue'
import { usePreferencesStore } from '@/stores/preferences'


const messages = {
  en: {
    nav_dashboard: 'Dashboard',
    nav_discover: 'Discover',
    nav_lists: 'Lists',
    nav_calendar: 'Calendar',
    nav_data: 'Data',
    nav_settings: 'Settings',
    settings_language: 'Language',
    settings_spoiler_mode: 'Spoiler mode',
    settings_spoiler_mode_desc: 'Blur unwatched images and descriptions until revealed.',
    settings_privacy: 'Privacy',
    settings_profile: 'Profile',
    tracking_mark_as_watched: 'Mark as watched',
    tracking_watched: 'Watched',
    tracking_watched_on: 'Watched on',
    rating_vote_singular: 'vote',
    rating_vote_plural: 'votes',
    nav_open_search: 'Open search',
    nav_open_user_menu: 'Open user menu',
    nav_toggle_theme: 'Toggle theme',
    watch_options: 'Watch options',
    watch_option_now: 'Just now',
    watch_option_release: 'Release date',
    watch_option_date: 'Select date',
    watchlist_add_movie: 'Add movie to watchlist',
    watchlist_remove_movie: 'Remove movie from watchlist',
    watchlist_add_show: 'Add show to watchlist',
    watchlist_remove_show: 'Remove show from watchlist',
    rating_group_label: 'Rate from 1 to 10',
    rating_item_label: 'Rate {value} out of 10',
    rating_movie_requires_watched: 'Rate this movie after marking it as watched.',
    rating_show_requires_watching: 'Rate this show after you start watching it.',
    profile_tab_activity: 'Activity',
    profile_tab_lists: 'Lists',
    profile_tab_followers: 'Followers',
    profile_tab_following: 'Following',
    profile_tab_about: 'About',
    profile_locked_title: 'This profile is not visible to you.',
    profile_locked_description: 'Only mutual friends can view this account content.',
    profile_locked_private: 'Only this user can view this profile content.',
    profile_locked_followers: 'Followers are hidden by this account privacy setting.',
    profile_locked_following: 'Following is hidden by this account privacy setting.',
    profile_empty_activity: 'No recent activity yet.',
    profile_empty_lists: 'No visible lists.',
    profile_empty_followers: 'No followers yet.',
    profile_empty_following: 'Not following anyone yet.',
    profile_about_joined: 'Joined',
    profile_about_location: 'Location',
    profile_back_to_profile: 'Back to profile',
    profile_followers_page_title: '{username} followers',
    profile_following_page_title: '{username} following',
    profile_followers_count_label: 'followers',
    profile_following_count_label: 'following',
    profile_social_results: '{count} people',
    profile_page_indicator: 'Page {page} of {total}',
    profile_badge_follows_you: 'Follows you',
    profile_badge_friend: 'Friend',
    profile_visibility_public: 'Public',
    profile_visibility_private: 'Private',
    profile_visibility_friends_only: 'Friends only',
  },
  es: {
    nav_dashboard: 'Panel',
    nav_discover: 'Descubrir',
    nav_lists: 'Listas',
    nav_calendar: 'Calendario',
    nav_data: 'Datos',
    nav_settings: 'Configuracion',
    settings_language: 'Idioma',
    settings_spoiler_mode: 'Modo spoilers',
    settings_spoiler_mode_desc: 'Difumina imagenes y descripciones no vistas hasta revelarlas.',
    settings_privacy: 'Privacidad',
    settings_profile: 'Perfil',
    tracking_mark_as_watched: 'Marcar como visto',
    tracking_watched: 'Visto',
    tracking_watched_on: 'Visto el',
    rating_vote_singular: 'voto',
    rating_vote_plural: 'votos',
    nav_open_search: 'Abrir busqueda',
    nav_open_user_menu: 'Abrir menu de usuario',
    nav_toggle_theme: 'Cambiar tema',
    watch_options: 'Opciones de seguimiento',
    watch_option_now: 'Ahora mismo',
    watch_option_release: 'Fecha de estreno',
    watch_option_date: 'Elegir fecha',
    watchlist_add_movie: 'Agregar pelicula a la lista',
    watchlist_remove_movie: 'Quitar pelicula de la lista',
    watchlist_add_show: 'Agregar serie a la lista',
    watchlist_remove_show: 'Quitar serie de la lista',
    rating_group_label: 'Calificar de 1 a 10',
    rating_item_label: 'Calificar {value} de 10',
    rating_movie_requires_watched: 'Califica esta pelicula despues de marcarla como vista.',
    rating_show_requires_watching: 'Califica esta serie despues de empezar a verla.',
    profile_tab_activity: 'Actividad',
    profile_tab_lists: 'Listas',
    profile_tab_followers: 'Seguidores',
    profile_tab_following: 'Siguiendo',
    profile_tab_about: 'Acerca de',
    profile_locked_title: 'Este perfil no es visible para ti.',
    profile_locked_description: 'Solo amigos mutuos pueden ver este contenido.',
    profile_locked_private: 'Solo esta persona puede ver el contenido de su perfil.',
    profile_locked_followers: 'Los seguidores estan ocultos por la privacidad de esta cuenta.',
    profile_locked_following: 'Los seguidos estan ocultos por la privacidad de esta cuenta.',
    profile_empty_activity: 'Sin actividad reciente.',
    profile_empty_lists: 'No hay listas visibles.',
    profile_empty_followers: 'Aun no tiene seguidores.',
    profile_empty_following: 'Aun no sigue a nadie.',
    profile_about_joined: 'Se unio',
    profile_about_location: 'Ubicacion',
    profile_back_to_profile: 'Volver al perfil',
    profile_followers_page_title: 'Seguidores de {username}',
    profile_following_page_title: '{username} sigue a',
    profile_followers_count_label: 'seguidores',
    profile_following_count_label: 'siguiendo',
    profile_social_results: '{count} personas',
    profile_page_indicator: 'Pagina {page} de {total}',
    profile_badge_follows_you: 'Te sigue',
    profile_badge_friend: 'Amigo',
    profile_visibility_public: 'Publica',
    profile_visibility_private: 'Privada',
    profile_visibility_friends_only: 'Solo amigos',
  }
}


export function useI18n() {
  const prefs = usePreferencesStore()
  const locale = computed(() => prefs.locale)
  const t = (key, params = {}) => {
    const template = messages[locale.value]?.[key] ?? messages.en[key] ?? key
    return template.replace(/\{(\w+)\}/g, (_, token) => {
      const value = params[token]
      return value === undefined || value === null ? '' : String(value)
    })
  }
  return { t, locale }
}

export function formatDateByLocale(value) {
  if (!value) return ''
  const prefs = usePreferencesStore()
  const locale = prefs.locale === 'es' ? 'es-ES' : 'en-US'
  return new Date(value).toLocaleDateString(locale, { month: 'long', day: 'numeric', year: 'numeric' })
}

export function formatDateTimeByLocale(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const prefs = usePreferencesStore()
  const locale = prefs.locale === 'es' ? 'es-ES' : 'en-US'
  return date.toLocaleString(locale, {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
