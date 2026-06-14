import { useState, useEffect } from 'react'
import { getJobs, startCrawl, pauseJob, resumeJob, deleteJob, rerunJob, type CrawlJob } from '../hooks/useAbyssalApi'
import { Play, Pause, RotateCcw, Trash2, Loader2 } from 'lucide-react'

export default function AdminPage() {
  const [jobs, setJobs] = useState<CrawlJob[]>([])
  const [loading, setLoading] = useState(true)
  const [url, setUrl] = useState('')
  const [maxPages, setMaxPages] = useState(0)
  const [maxDepth, setMaxDepth] = useState(5)
  const [concurrency, setConcurrency] = useState(3)

  const loadJobs = () => {
    getJobs().then(setJobs).catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => { loadJobs(); const iv = setInterval(loadJobs, 5000); return () => clearInterval(iv) }, [])

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    try {
      await startCrawl(url.trim(), maxPages, maxDepth, concurrency)
      setUrl('')
      loadJobs()
    } catch {}
  }

  const statusColor: Record<string, string> = {
    running: 'text-green-400',
    pending: 'text-yellow-400',
    paused: 'text-orange-400',
    completed: 'text-blue-400',
    failed: 'text-red-400',
  }

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Crawl Admin</h1>

      {/* New crawl form */}
      <form onSubmit={handleStart} className="border border-gray-800 rounded-lg p-4 mb-6">
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">New Crawl Job</h2>
        <div className="flex items-center gap-3">
          <input type="text" value={url} onChange={e => setUrl(e.target.value)}
            placeholder="Seed URL (e.g. identiguy.i2p)"
            className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          />
          <input type="number" value={maxPages} onChange={e => setMaxPages(Number(e.target.value))}
            className="w-20 bg-gray-900 border border-gray-700 rounded px-2 py-2 text-sm text-center" title="Max pages (0 = unlimited)" placeholder="∞" />
          <input type="number" value={maxDepth} onChange={e => setMaxDepth(Number(e.target.value))}
            className="w-16 bg-gray-900 border border-gray-700 rounded px-2 py-2 text-sm text-center" title="Max depth" placeholder="5" />
          <input type="number" value={concurrency} onChange={e => setConcurrency(Number(e.target.value))}
            className="w-16 bg-gray-900 border border-gray-700 rounded px-2 py-2 text-sm text-center" title="Concurrency" placeholder="3" />
          <button type="submit" className="bg-cyan-700 hover:bg-cyan-600 px-4 py-2 rounded-lg text-sm font-medium">Start</button>
        </div>
        <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
          <span>max_pages (0=∞)</span>
          <span>max_depth</span>
          <span>workers</span>
        </div>
      </form>

      {/* Job list */}
      {loading ? (
        <div className="flex items-center gap-2 text-gray-400 py-8"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-16 text-gray-500">No crawl jobs yet.</div>
      ) : (
        <div className="space-y-2">
          {jobs.map(job => (
            <div key={job.id} className="border border-gray-800 rounded-lg p-3 flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${statusColor[job.status] || 'text-gray-500'}`} />
                  <span className="text-sm font-medium truncate">{job.url}</span>
                  <span className="text-xs text-gray-500 uppercase">{job.status}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500 mt-1">
                  <span>{job.pages_crawled} pages</span>
                  <span>depth {job.max_depth}</span>
                  <span>{job.concurrency} workers</span>
                  {job.finished_at && <span>finished {new Date(job.finished_at).toLocaleDateString()}</span>}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {job.status === 'running' && (
                  <button onClick={() => pauseJob(job.id)} className="p-1.5 text-gray-400 hover:text-white rounded" title="Pause"><Pause className="w-3 h-3" /></button>
                )}
                {job.status === 'paused' && (
                  <button onClick={() => resumeJob(job.id)} className="p-1.5 text-gray-400 hover:text-white rounded" title="Resume"><Play className="w-3 h-3" /></button>
                )}
                {(job.status === 'completed' || job.status === 'failed') && (
                  <button onClick={() => rerunJob(job.id)} className="p-1.5 text-gray-400 hover:text-white rounded" title="Rerun"><RotateCcw className="w-3 h-3" /></button>
                )}
                <button onClick={() => deleteJob(job.id)} className="p-1.5 text-gray-400 hover:text-red-400 rounded" title="Delete"><Trash2 className="w-3 h-3" /></button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
