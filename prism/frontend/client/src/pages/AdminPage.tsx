import { useState, useEffect, useCallback } from 'react'
import { getJobs, startCrawl, pauseJob, resumeJob, deleteJob, rerunJob, type CrawlJob } from '../hooks/useAdminApi'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Loader2, Play, Pause, RotateCcw, Trash2, ChevronDown, ChevronRight, ExternalLink, AlertTriangle, Ban } from 'lucide-react'

function normalizeI2pUrl(raw: string): string {
  const u = raw.trim()
  if (!u) return u
  const stripped = u.replace(/^https?:\/\//i, '')
  const slashIdx = stripped.indexOf('/')
  let host = slashIdx === -1 ? stripped : stripped.slice(0, slashIdx)
  const rest = slashIdx === -1 ? '' : stripped.slice(slashIdx)
  if (host && !host.toLowerCase().endsWith('.i2p')) host += '.i2p'
  return `http://${host}${rest}`
}

const STATUS_BADGE: Record<string, string> = {
  running:   'bg-green-500/10 text-green-500 border-green-500/20',
  pending:   'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  paused:    'bg-orange-500/10 text-orange-500 border-orange-500/20',
  completed: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  failed:    'bg-red-500/10 text-red-500 border-red-500/20',
}

export default function AdminPage() {
  const [jobs, setJobs]                   = useState<CrawlJob[]>([])
  const [loading, setLoading]             = useState(true)
  const [showCompleted, setShowCompleted] = useState(false)
  const [showFailed, setShowFailed]       = useState(false)

  const [urlInput, setUrlInput]       = useState('')
  const [maxPages, setMaxPages]       = useState(0)
  const [maxDepth, setMaxDepth]       = useState(5)
  const [concurrency, setConcurrency] = useState(3)
  const [delay, setDelay]             = useState(2.0)
  const [submitting, setSubmitting]   = useState(false)
  const [error, setError]             = useState('')

  const normalized  = normalizeI2pUrl(urlInput)
  const showPreview = urlInput.trim() !== '' && normalized !== urlInput.trim()

  const loadJobs = useCallback(() => {
    getJobs().then(setJobs).catch(console.error).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadJobs()
    const iv = setInterval(loadJobs, 5000)
    return () => clearInterval(iv)
  }, [loadJobs])

  const handleStart = async () => {
    const target = normalized
    if (!target) return
    setError('')
    setSubmitting(true)
    try {
      await startCrawl(target, maxPages, maxDepth, concurrency, delay)
      setUrlInput('')
      loadJobs()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start crawl')
    } finally {
      setSubmitting(false)
    }
  }

  const activeJobs      = jobs.filter(j => j.status === 'running' || j.status === 'pending' || j.status === 'paused')
  const completedJobs    = jobs.filter(j => j.status === 'completed')
  const failedJobs      = jobs.filter(j => j.status === 'failed')

  const renderJob = (job: CrawlJob) => (
    <div key={job.id} className="flex items-center gap-3 rounded-lg border border-border p-3 text-sm">
      <Badge variant="outline" className={`shrink-0 ${STATUS_BADGE[job.status] ?? ''}`}>{job.status}</Badge>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{job.url}</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {job.pages_crawled} pages &middot; depth {job.max_depth} &middot; {job.concurrency}w
          {(job.pages_failed ?? 0) > 0 && <> &middot; <span className="text-red-500">{job.pages_failed} failed</span></>}
          {(job.pages_limited ?? 0) > 0 && <> &middot; <span className="text-amber-500">{job.pages_limited} limited</span></>}
          {job.finished_at && <> &middot; done {new Date(job.finished_at).toLocaleDateString()}</>}
        </p>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        {job.status === 'running' && (
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => pauseJob(job.id).then(loadJobs)} title="Pause">
            <Pause className="h-3.5 w-3.5" />
          </Button>
        )}
        {job.status === 'paused' && (
          <Button variant="ghost" size="icon" className="h-8 w-8 text-green-500" onClick={() => resumeJob(job.id).then(loadJobs)} title="Resume">
            <Play className="h-3.5 w-3.5" />
          </Button>
        )}
        {(job.status === 'completed' || job.status === 'failed') && (
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => rerunJob(job.id).then(loadJobs)} title="Re-run">
            <RotateCcw className="h-3.5 w-3.5" />
          </Button>
        )}
        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => deleteJob(job.id).then(loadJobs)} title="Delete">
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Crawl Admin</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">New Crawl Job</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <input
                type="text"
                value={urlInput}
                onChange={e => setUrlInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleStart()}
                placeholder="identiguy.i2p  or  http://notbob.i2p/forum"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              {showPreview && (
                <p className="absolute left-0 -bottom-5 text-xs text-cyan-600 truncate w-full px-1">
                  → {normalized}
                </p>
              )}
            </div>
            <Button onClick={handleStart} disabled={submitting || !urlInput.trim()}>
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Start'}
            </Button>
          </div>

          <div className={`flex flex-wrap items-center gap-3 text-xs text-muted-foreground ${showPreview ? 'mt-4' : ''}`}>
            <label className="flex items-center gap-2">
              Max pages
              <input type="number" min={0} value={maxPages}
                onChange={e => setMaxPages(Number(e.target.value))}
                className="w-16 rounded border border-input bg-background px-2 py-1 text-center" title="0 = unlimited" />
            </label>
            <label className="flex items-center gap-2">
              Depth
              <input type="number" min={1} max={20} value={maxDepth}
                onChange={e => setMaxDepth(Number(e.target.value))}
                className="w-14 rounded border border-input bg-background px-2 py-1 text-center" />
            </label>
            <label className="flex items-center gap-2">
              Workers
              <input type="number" min={1} max={20} value={concurrency}
                onChange={e => setConcurrency(Number(e.target.value))}
                className="w-14 rounded border border-input bg-background px-2 py-1 text-center" />
            </label>
            <label className="flex items-center gap-2">
              Delay (s)
              <input type="number" min={0} max={60} step={0.5} value={delay}
                onChange={e => setDelay(Number(e.target.value))}
                className="w-14 rounded border border-input bg-background px-2 py-1 text-center" />
            </label>
          </div>

          {error && (
            <p className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded px-3 py-2">{error}</p>
          )}
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading jobs…
        </div>
      ) : activeJobs.length === 0 && completedJobs.length === 0 && failedJobs.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground text-sm">No crawl jobs yet.</div>
      ) : (
        <div className="space-y-2">
          {activeJobs.length === 0 && completedJobs.length === 0 && failedJobs.length === 0 && (
            <p className="text-xs text-center text-muted-foreground py-4">No jobs.</p>
          )}

          {activeJobs.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Active ({activeJobs.length})</h2>
              {activeJobs.map(renderJob)}
            </div>
          )}

          {failedJobs.length > 0 && (
            <>
              <Button
                variant="ghost"
                onClick={() => setShowFailed(v => !v)}
                className="w-full flex items-center justify-between text-xs text-muted-foreground hover:text-foreground border border-transparent hover:border-border"
              >
                <span className="flex items-center gap-2">
                  {showFailed ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                  {showFailed ? 'Hide' : 'Show'} failed jobs
                </span>
                <Badge variant="secondary" className="ml-auto">{failedJobs.length}</Badge>
              </Button>
              {showFailed && (
                <div className="space-y-2 pt-1">{failedJobs.map(renderJob)}</div>
              )}
            </>
          )}

          {completedJobs.length > 0 && (
            <>
              <Button
                variant="ghost"
                onClick={() => setShowCompleted(v => !v)}
                className="w-full flex items-center justify-between text-xs text-muted-foreground hover:text-foreground border border-transparent hover:border-border"
              >
                <span className="flex items-center gap-2">
                  {showCompleted ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                  {showCompleted ? 'Hide' : 'Show'} completed jobs
                </span>
                <Badge variant="secondary" className="ml-auto">{completedJobs.length}</Badge>
              </Button>
              {showCompleted && (
                <div className="space-y-2 pt-1">{completedJobs.map(renderJob)}</div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
