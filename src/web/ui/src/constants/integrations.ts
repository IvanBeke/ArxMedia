export const INTEGRATION_SERVICE = {
  RADARR: 'radarr',
  SONARR: 'sonarr',
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
}
