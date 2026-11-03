export const INTEGRATION_SERVICE = {
  RADARR: 'radarr',
  SONARR: 'sonarr',
  JELLYFIN: 'jellyfin',
} as const

export type IntegrationService = (typeof INTEGRATION_SERVICE)[keyof typeof INTEGRATION_SERVICE]

interface IntegrationBrand {
  name: string
  icon: string
  idleClass: string
  activeClass: string
}

export const INTEGRATION_BRANDS: Record<IntegrationService, IntegrationBrand> = {
  [INTEGRATION_SERVICE.RADARR]: {
    name: 'Radarr',
    icon: '/static/branding/integrations/radarr.webp',
    idleClass: 'border-radarr/50 text-radarr hover:bg-radarr/10',
    activeClass: 'border-radarr bg-radarr/15 text-radarr hover:bg-radarr/25',
  },
  [INTEGRATION_SERVICE.SONARR]: {
    name: 'Sonarr',
    icon: '/static/branding/integrations/sonarr.webp',
    idleClass: 'border-sonarr/50 text-sonarr hover:bg-sonarr/10',
    activeClass: 'border-sonarr bg-sonarr/15 text-sonarr hover:bg-sonarr/25',
  },
  [INTEGRATION_SERVICE.JELLYFIN]: {
    name: 'Jellyfin',
    icon: '/static/branding/integrations/jellyfin.webp',
    idleClass: 'border-jellyfin/50 text-jellyfin hover:bg-jellyfin/10',
    activeClass: 'border-jellyfin bg-jellyfin/15 text-jellyfin hover:bg-jellyfin/25',
  },
}
