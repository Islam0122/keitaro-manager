import type {
  AppSettings,
  CampaignCreateInput,
  CampaignDetail,
  CampaignListResponse,
  CampaignLog,
  CampaignOffersResponse,
  CampaignUpdateInput,
  ConnectionTestResult,
  Domain,
  Group,
  Health,
  Offer,
  SettingsInput,
  Stream,
  StreamInput,
  StreamOffer,
  TrafficSource,
} from '@/types/api'

import { http } from './client'

export interface CampaignFilters {
  search?: string
  group_id?: number
  state?: string
}

export const campaignsApi = {
  list: (filters: CampaignFilters = {}) =>
    http.get<CampaignListResponse>('/campaigns', { params: filters }).then((r) => r.data),
  get: (id: number) => http.get<CampaignDetail>(`/campaigns/${id}`).then((r) => r.data),
  create: (data: CampaignCreateInput) => http.post<CampaignDetail>('/campaigns', data).then((r) => r.data),
  update: (id: number, data: CampaignUpdateInput) =>
    http.put<CampaignDetail>(`/campaigns/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/campaigns/${id}`),
}

export const offersApi = {
  list: (campaignId: number) =>
    http.get<CampaignOffersResponse>(`/campaigns/${campaignId}/offers`).then((r) => r.data),
  add: (campaignId: number, data: { offer_id: number; stream_id?: number; share?: number }) =>
    http.post<CampaignOffersResponse>(`/campaigns/${campaignId}/offers`, data).then((r) => r.data),
  update: (campaignId: number, streamId: number, offers: Omit<StreamOffer, 'id'>[]) =>
    http
      .put<CampaignOffersResponse>(`/campaigns/${campaignId}/offers`, { stream_id: streamId, offers })
      .then((r) => r.data),
  remove: (campaignId: number, offerId: number, streamId?: number) =>
    http
      .delete<CampaignOffersResponse>(`/campaigns/${campaignId}/offers/${offerId}`, {
        params: streamId ? { stream_id: streamId } : undefined,
      })
      .then((r) => r.data),
}

export const streamsApi = {
  list: (campaignId: number) => http.get<Stream[]>(`/campaigns/${campaignId}/streams`).then((r) => r.data),
  create: (campaignId: number, data: StreamInput) =>
    http.post<Stream>(`/campaigns/${campaignId}/streams`, data).then((r) => r.data),
  update: (streamId: number, data: StreamInput) => http.put<Stream>(`/streams/${streamId}`, data).then((r) => r.data),
  setEnabled: (streamId: number, enabled: boolean) =>
    http.post<Stream>(`/streams/${streamId}/${enabled ? 'enable' : 'disable'}`).then((r) => r.data),
  remove: (streamId: number) => http.delete(`/streams/${streamId}`),
}

export const resourcesApi = {
  domains: () => http.get<Domain[]>('/resources/domains').then((r) => r.data),
  groups: () => http.get<Group[]>('/resources/groups').then((r) => r.data),
  sources: () => http.get<TrafficSource[]>('/resources/sources').then((r) => r.data),
  offers: () => http.get<Offer[]>('/resources/offers').then((r) => r.data),
}

export const settingsApi = {
  get: () => http.get<AppSettings>('/settings').then((r) => r.data),
  update: (data: SettingsInput) => http.put<AppSettings>('/settings', data).then((r) => r.data),
  test: (data?: { api_url?: string; api_key?: string }) =>
    http.post<ConnectionTestResult>('/settings/test', data ?? {}).then((r) => r.data),
  health: () => http.get<Health>('/health').then((r) => r.data),
  logs: (campaignId?: number) =>
    http.get<CampaignLog[]>('/logs', { params: campaignId ? { campaign_id: campaignId } : {} }).then((r) => r.data),
}
