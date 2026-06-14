const API_KEY = 'dev-key-12345'
const BASE = '/api/abyssal'

async function api<T>(path: string, params?: Record<string, string | number | boolean>, options?: RequestInit): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== '' && v !== undefined && v !== null) url.searchParams.set(k, String(v))
    })
  }
  const res = await fetch(url.toString(), {
    ...options,
    headers: { 'api-key': API_KEY, ...(options?.headers as Record<string, string>) },
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export interface SearchResult {
  id: number
  url: string
  title: string
  description: string
  language: string
  site_type: string
  b32: string
  address_helper: string
  crawled_at: string
  status_code: number
  snippet: string
}

export interface SearchResponse {
  results: SearchResult[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export interface FacetCount {
  language?: string
  site_type?: string
  count: number
}

export interface Facets {
  languages: FacetCount[]
  site_types: FacetCount[]
}

export interface Site {
  hostname: string
  b32: string
  address_helper: string
  checks_online: number
  checks_offline: number
  last_seen_online: string
  last_seen_offline: string
  last_crawled: string
  title: string
  language: string
  site_type: string
  pages?: SitePage[]
}

export interface SitePage {
  id: number
  url: string
  title: string
  language: string
  site_type: string
  crawled_at: string
}

export interface SitesResponse {
  results: Site[]
  total: number
  page: number
  per_page: number
}

export interface CrawlJob {
  id: number
  url: string
  max_pages: number
  max_depth: number
  status: string
  pages_crawled: number
  created_at: string
  finished_at: string | null
  concurrency: number
  delay_seconds: number
}

export interface WaybackSnapshot {
  id: number
  url: string
  snapshot_time: string
  title: string
  status_code: number
  content_type: string
  file_path: string
  size_bytes: number
}

export interface WaybackStats {
  total_snapshots: number
  total_urls: number
  total_size_bytes: number
  recent_snapshots: { url: string; snapshot_time: string; title: string }[]
  snapshots_by_date: { day: string; count: number }[]
}

export interface PageData {
  id: number
  url: string
  title: string
  language: string
  site_type: string
  b32: string
  content: string
  crawled_at: string
}

// Search
export const search = (q: string, lang = '', type = '', page = 1) =>
  api<SearchResponse>('/search', { q, language: lang, site_type: type, page, per_page: 20 })

export const getFacets = () => api<Facets>('/facets')

// Directory
export const getSites = (lang = '', type = '', page = 1) =>
  api<SitesResponse>('/sites', { language: lang, site_type: type, page, per_page: 50 })

export const getSite = (hostname: string) => api<Site>(`/sites/${hostname}`)

// Crawl admin
export const getJobs = () => api<CrawlJob[]>('/crawl/jobs')
export const startCrawl = (url: string, maxPages = 0, maxDepth = 5, concurrency = 3, delay = 2.0) =>
  api<{ job_id: number }>('/crawl/start', {}, { method: 'POST', body: JSON.stringify({ url, max_pages: maxPages, max_depth: maxDepth, concurrency, delay_seconds: delay }) })
export const pauseJob = (id: number) => api(`/crawl/jobs/${id}/pause`, {}, { method: 'POST' })
export const resumeJob = (id: number) => api(`/crawl/jobs/${id}/resume`, {}, { method: 'POST' })
export const deleteJob = (id: number) => api(`/crawl/jobs/${id}`, {}, { method: 'DELETE' })
export const rerunJob = (id: number) => api(`/crawl/jobs/${id}/rerun`, {}, { method: 'POST' })

// Wayback
export const getWaybackStats = () => api<WaybackStats>('/wayback/stats')
export const getWaybackSnapshots = (url: string, limit = 500) =>
  api<{ snapshots: WaybackSnapshot[]; total: number }>('/wayback/snapshots', { url, limit })
export const getWaybackSnapshot = (id: number) => api<WaybackSnapshot>(`/wayback/snapshots/${id}`)
export const viewWaybackSnapshot = (id: number, raw = false) =>
  api<{ content: string; url: string }>(`/wayback/snapshots/${id}/view`, { raw: raw ? '1' : '' })
export const captureWayback = (url: string) =>
  api('/wayback/capture', { url }, { method: 'POST' })

// Page viewer
export const getPage = (id: number) => api<PageData>(`/pages/${id}`)
export const viewPage = (id: number, raw = false) =>
  api<{ content: string; url: string }>(`/pages/${id}/view`, { raw: raw ? '1' : '' })
