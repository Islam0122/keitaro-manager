export type CampaignState = 'active' | 'disabled' | 'deleted'
export type StreamType = 'regular' | 'forced' | 'default'
export type StreamSchema = 'redirect' | 'landings' | 'action'
export type ItemState = 'active' | 'disabled'

export interface CampaignListItem {
  id: number
  alias: string | null
  name: string
  type: string | null
  state: CampaignState | null
  group_id: number | null
  group_name: string | null
  traffic_source_id: number | null
  traffic_source_name: string | null
  domain_id: number | null
  domain_name: string | null
  streams_count: number | null
  offers_count: number | null
  updated_at: string | null
}

export interface CampaignListResponse {
  items: CampaignListItem[]
  total: number
  offers_total: number | null
}

export interface StreamFilter {
  id?: number | null
  name: string
  mode: 'accept' | 'reject'
  payload: unknown
}

export interface StreamOffer {
  id?: number | null
  offer_id: number
  share: number
  state: ItemState
}

export interface Stream {
  id: number
  campaign_id: number
  name: string | null
  type: StreamType | null
  position: number | null
  weight: number | null
  state: ItemState | null
  schema: StreamSchema | null
  action_type: string | null
  action_payload: unknown
  filter_or: boolean
  collect_clicks: boolean
  comments: string | null
  filters: StreamFilter[]
  offers: StreamOffer[]
}

export interface StreamInput {
  name: string
  type: StreamType
  position?: number | null
  state: ItemState
  schema: StreamSchema
  action_type: string
  action_payload?: string | null
  filter_or: boolean
  collect_clicks: boolean
  comments?: string | null
  filters: Omit<StreamFilter, 'id'>[]
  offers: Omit<StreamOffer, 'id'>[]
}

export interface CampaignOffer {
  stream_id: number
  stream_name: string | null
  offer_id: number
  offer_name: string | null
  share: number
  state: ItemState
}

export interface CampaignDetail {
  campaign: CampaignListItem
  streams: Stream[]
  offers: CampaignOffer[]
  local: { country: string; offer_id: number; created_at: string } | null
}

export interface OfferStreamSummary {
  stream_id: number
  name: string | null
  state: string | null
  total_share: number
  offers_count: number
}

export interface CampaignOffersResponse {
  campaign_id: number
  items: CampaignOffer[]
  streams: OfferStreamSummary[]
}

export interface CampaignCreateInput {
  name: string
  country: string
  offer_id: number
  domain_id: number
  group_id: number
  traffic_source_id: number
}

export interface CampaignUpdateInput {
  name?: string
  group_id?: number
  traffic_source_id?: number
  domain_id?: number
  state?: ItemState
}

export interface Domain {
  id: number
  name: string
  state: string | null
  network_status: string | null
  default_campaign_id: number | null
  is_ssl: boolean | null
}

export interface Group {
  id: number
  name: string
  type: string | null
}

export interface TrafficSource {
  id: number
  name: string
  state: string | null
}

export interface Offer {
  id: number
  name: string
  group_id: number | null
  state: string | null
  country: string[]
  payout_value: number | null
  payout_currency: string | null
  action_type: string | null
  action_payload: unknown
}

export interface AppSettings {
  api_url: string | null
  api_key_set: boolean
  api_key_masked: string | null
  timeout: number
  default_safe_url: string
  source: 'database' | 'environment' | 'none'
  updated_at: string | null
}

export interface SettingsInput {
  api_url: string
  api_key?: string | null
  timeout: number
  default_safe_url: string
}

export interface ConnectionTestResult {
  ok: boolean
  message: string
  latency_ms: number | null
  campaigns_count: number | null
}

export interface Health {
  status: string
  version: string
  database: string
  keitaro_configured: boolean
}

export interface CampaignLog {
  id: number
  campaign_keitaro_id: number | null
  action: string
  status: 'success' | 'error'
  message: string | null
  details: Record<string, unknown> | null
  created_at: string
}
