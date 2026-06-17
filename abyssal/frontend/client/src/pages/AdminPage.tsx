import { useState, useEffect, useCallback } from 'react'
import {
  getJobs, startCrawl, pauseJob, resumeJob, deleteJob, rerunJob,
  type CrawlJob,
} from '../hooks/useAbyssalApi'
import { Play, Pause, RotateCcw, Trash2, Loader2, ChevronDown, ChevronRight } from 'lucide-react'

// ── URL normalisation ──────────────────────────────────────────────────────────
// "identiguy"            → "http://identiguy.i2p"
// "identiguy.i2p"        → "http://identiguy.i2p"
// "http://notbob"        → "http://notbob.i2p"
// "http://notbob.i2p/p" → unchanged
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

const STATUS_DOT: Record<string, string> = {
  running:   'bg-green-400',
  pending:   'bg-yellow-400',
  paused:    'bg-orange-400',
  completed: 'bg-blue-400',
  failed:    'bg-red-500',
}

export default function AdminPage() {
  const [jobs, setJobs]                   = useState<CrawlJob[]>([])
  const [loading, setLoading]             = useState(true)
  const [showCompleted, setShowCompleted] = useState(false)

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

  // Wired to onClick (not form submit) so nothing can silently swallow the event
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
      console.error('startCrawl failed:', err)
      setError(err instanceof Error ? err.message : 'Failed to start crawl — check console')
    } finally {
      setSubmitting(false)
    }
  }

  const activeJobs    = jobs.filter(j => j.status !== 'completed')
  const completedJobs = jobs.filter(j => j.status === 'completed')

  const renderJob = (job: CrawlJob) => (
    <div
      key={job.id}
      className="border border-gray-800 rounded-lg px-3 py-2.5 flex items-center gap-3 hover:border-gray-700 transition-colors"
    >
      <span className={`w-2 h-2 rounded-full shrink-0 ${STATUS_DOT[job.status] ?? 'bg-gray-500'}`} title={job.status} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-gray-100 truncate">{job.url}</p>
        <p className="text-xs text-gray-500 mt-0.5 flex gap-3">
          <span className="uppercase tracking-wide text-gray-600">{job.status}</span>
          <span>{job.pages_crawled} pages</span>
          <span>depth {job.max_depth}</span>
          <span>{job.concurrency}w</span>
          {job.finished_at && <span>done {new Date(job.finished_at).toLocaleDateString()}</span>}
        </p>
      </div>
      <div className="flex items-center gap-0.5 shrink-0">
        {job.status === 'running' && (
          <button onClick={() => pauseJob(job.id).then(loadJobs)} className="p-1.5 text-gray-500 hover:text-white rounded" title="Pause">
            <Pause className="w-3.5 h-3.5" />
          </button>
        )}
        {job.status === 'paused' && (
          <button onClick={() => resumeJob(job.id).then(loadJobs)} className="p-1.5 text-gray-500 hover:text-green-400 rounded" title="Resume">
            <Play className="w-3.5 h-3.5" />
          </button>
        )}
        {(job.status === 'completed' || job.status === 'failed') && (
          <button onClick={() => rerunJob(job.id).then(loadJobs)} className="p-1.5 text-gray-500 hover:text-cyan-400 rounded" title="Re-run">
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        )}
        <button onClick={() => deleteJob(job.id).then(loadJobs)} className="p-1.5 text-gray-500 hover:text-red-400 rounded" title="Delete">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )

  return (
    <div className="p-4 max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Crawl Admin</h1>

      {/* ── New crawl ── */}
      <div className="border border-gray-800 rounded-xl p-4 space-y-3">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest">New Crawl Job</h2>

        <div className="flex gap-2">
          <div className="flex-1 relative">
            <input
              type="text"
              value={urlInput}
              onChange={e => setUrlInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleStart()}
              placeholder="identiguy.i2p  or  http://notbob.i2p/forum"
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-cyan-600 transition-colors"
            />
            {showPreview && (
              <p className="absolute left-0 -bottom-5 text-xs text-cyan-600 truncate w-full px-1">
                → {normalized}
              </p>
            )}
          </div>
          {/* type="button" prevents any accidental form-submit interference */}
          <button
            type="button"
            onClick={handleStart}
            disabled={submitting || !urlInput.trim()}
            className="bg-cyan-700 hover:bg-cyan-600 disabled:opacity-40 disabled:cursor-not-allowed px-5 py-2 rounded-lg text-sm font-semibold transition-colors shrink-0"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Start'}
          </button>
        </div>

        <div className={`flex items-center gap-2 ${showPreview ? 'mt-6' : ''}`}>
          <label className="text-xs text-gray-500 shrink-0">Max pages</label>
          <input type="number" min={0} value={maxPages}
            onChange={e => setMaxPages(Number(e.target.value))}
            className="w-20 bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-center focus:outline-none focus:border-cyan-600"
            title="0 = unlimited" />
          <label className="text-xs text-gray-500 shrink-0 ml-2">Depth</label>
          <input type="number" min={1} max={20} value={maxDepth}
            onChange={e => setMaxDepth(Number(e.target.value))}
            className="w-16 bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-center focus:outline-none focus:border-cyan-600" />
          <label className="text-xs text-gray-500 shrink-0 ml-2">Workers</label>
          <input type="number" min={1} max={20} value={concurrency}
            onChange={e => setConcurrency(Number(e.target.value))}
            className="w-16 bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-center focus:outline-none focus:border-cyan-600" />
          <label className="text-xs text-gray-500 shrink-0 ml-2">Delay (s)</label>
          <input type="number" min={0} max={60} step={0.5} value={delay}
            onChange={e => setDelay(Number(e.target.value))}
            className="w-16 bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-center focus:outline-none focus:border-cyan-600" />
        </div>

        {error && (
          <p className="text-xs text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">
            ⚠ {error}
          </p>
        )}
      </div>

      {/* ── Job list ── */}
      {loading ? (
        <div className="flex items-center gap-2 text-gray-500 py-10 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading jobs…
        </div>
      ) : activeJobs.length === 0 && completedJobs.length === 0 ? (
        <div className="text-center py-16 text-gray-600 text-sm">No crawl jobs yet.</div>
      ) : (
        <div className="space-y-2">
          {activeJobs.length === 0 && (
            <p className="text-xs text-gray-600 text-center py-4">No active jobs.</p>
          )}
          {activeJobs.map(renderJob)}

          {completedJobs.length > 0 && (
            <>
              <button
                type="button"
                onClick={() => setShowCompleted(v => !v)}
                className="w-full flex items-center justify-between px-3 py-2 mt-1 rounded-lg text-xs text-gray-500 hover:text-gray-300 hover:bg-gray-900 transition-colors border border-transparent hover:border-gray-800"
              >
                <span className="flex items-center gap-2">
                  {showCompleted ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  {showCompleted ? 'Hide' : 'Show'} completed jobs
                </span>
                <span className="bg-gray-800 text-gray-400 rounded-full px-2 py-0.5">{completedJobs.length}</span>
              </button>
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
