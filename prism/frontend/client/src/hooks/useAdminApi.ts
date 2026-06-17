const API_KEY = import.meta.env.VITE_API_KEY || 'dev-key-12345'

export interface CrawlJob {
  id: number; url: string; max_pages: number; max_depth: number
  status: string; pages_crawled: number; created_at: string
  finished_at: string | null; concurrency: number; delay_seconds: number
  pages_failed?: number; pages_limited?: number
}

async function api<T>(path: string, opts?: { method?: string; body?: unknown }): Promise<T> {
  const method = opts?.method || (opts?.body ? 'POST' : 'GET')
  const res = await fetch(path, {
    headers: { 'api-key': API_KEY, ...(opts?.body ? { 'Content-Type': 'application/json' } : {}) },
    method,
    body: opts?.body ? JSON.stringify(opts.body) : undefined,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text().catch(() => '')}`)
  return res.json()
}

export const getJobs        = ()                      => api<CrawlJob[]>('/api/abyssal/crawl/jobs')
export const startCrawl     = (url: string, maxPages = 0, maxDepth = 5, concurrency = 3, delaySeconds = 2) =>
  api<{ job_id: number }>('/api/abyssal/crawl/start', { body: { url, max_pages: maxPages, max_depth: maxDepth, concurrency, delay_seconds: delaySeconds } })
export const pauseJob       = (id: number)            => api<{ status: string }>(`/api/abyssal/crawl/jobs/${id}/pause`)
export const resumeJob      = (id: number)            => api<{ status: string }>(`/api/abyssal/crawl/jobs/${id}/resume`)
export const rerunJob       = (id: number)            => api<{ job_id: number }>(`/api/abyssal/crawl/jobs/${id}/rerun`)
export const deleteJob      = (id: number)            => api<{ status: string }>(`/api/abyssal/crawl/jobs/${id}`, { method: 'DELETE' })
