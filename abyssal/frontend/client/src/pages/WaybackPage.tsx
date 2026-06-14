import { useState, useEffect } from 'react'
import { getWaybackStats, getWaybackSnapshots, viewWaybackSnapshot, captureWayback, type WaybackStats, type WaybackSnapshot } from '../hooks/useAbyssalApi'
import { Archive, Search, Loader2, Clock, HardDrive } from 'lucide-react'

export default function WaybackPage() {
  const [stats, setStats] = useState<WaybackStats | null>(null)
  const [url, setUrl] = useState('')
  const [snapshots, setSnapshots] = useState<WaybackSnapshot[]>([])
  const [snapTotal, setSnapTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [snapLoading, setSnapLoading] = useState(false)
  const [viewing, setViewing] = useState<{ id: number; content: string; url: string } | null>(null)
  const [capturing, setCapturing] = useState(false)

  useEffect(() => {
    getWaybackStats().then(setStats).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const searchSnapshots = async () => {
    if (!url.trim()) return
    setSnapLoading(true)
    try {
      const data = await getWaybackSnapshots(url.trim())
      setSnapshots(data.snapshots)
      setSnapTotal(data.total)
    } catch {}
    setSnapLoading(false)
  }

  const viewSnap = async (id: number) => {
    try {
      const data = await viewWaybackSnapshot(id, false)
      setViewing(data)
    } catch {}
  }

  const doCapture = async () => {
    if (!url.trim()) return
    setCapturing(true)
    try {
      await captureWayback(url.trim())
      await searchSnapshots()
    } catch {}
    setCapturing(false)
  }

  const formatBytes = (b: number) => {
    if (b < 1024) return `${b}B`
    if (b < 1024*1024) return `${(b/1024).toFixed(1)}KB`
    return `${(b/1024/1024).toFixed(1)}MB`
  }

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Archive className="w-6 h-6 text-cyan-400" />
        <h1 className="text-2xl font-bold">Wayback Machine</h1>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="flex items-center gap-6 mb-6 text-sm text-gray-400">
          <span className="flex items-center gap-1"><Archive className="w-3 h-3" /> {stats.total_snapshots.toLocaleString()} snapshots</span>
          <span className="flex items-center gap-1"><GlobeIcon /> {stats.total_urls.toLocaleString()} URLs</span>
          <span className="flex items-center gap-1"><HardDrive className="w-3 h-3" /> {formatBytes(stats.total_size_bytes)}</span>
        </div>
      )}

      {/* URL search + capture */}
      <div className="flex items-center gap-2 mb-6">
        <input type="text" value={url} onChange={e => setUrl(e.target.value)}
          placeholder="Enter a .i2p URL to find snapshots..."
          className="flex-1 bg-gray-900 border border-gray-700 rounded-lg py-2 px-3 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          onKeyDown={e => e.key === 'Enter' && searchSnapshots()}
        />
        <button onClick={searchSnapshots} disabled={snapLoading}
          className="bg-cyan-700 hover:bg-cyan-600 px-3 py-2 rounded-lg text-sm disabled:opacity-50">
          {snapLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
        </button>
        <button onClick={doCapture} disabled={capturing || !url.trim()}
          className="bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm disabled:opacity-50">
          {capturing ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Capture'}
        </button>
      </div>

      <div className="flex gap-6">
        {/* Snapshot list */}
        <div className="flex-1 space-y-2">
          {snapshots.length === 0 && snapLoading && <div className="text-gray-500 text-sm py-4">Searching...</div>}
          {snapshots.length === 0 && !snapLoading && url && <div className="text-gray-500 text-sm py-4">No snapshots found for this URL.</div>}
          {snapshots.map(s => (
            <button key={s.id} onClick={() => viewSnap(s.id)}
              className="w-full text-left border border-gray-800 rounded-lg p-3 hover:border-gray-700">
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-sm text-cyan-400 truncate">{s.title || s.url}</p>
                  <p className="text-xs text-gray-500 truncate">{s.url}</p>
                </div>
                <div className="text-xs text-gray-500 shrink-0 ml-3">
                  <Clock className="w-3 h-3 inline mr-1" />
                  {new Date(s.snapshot_time).toLocaleDateString()}
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Viewer */}
        {viewing && (
          <div className="w-1/2 border border-gray-800 rounded-lg overflow-hidden">
            <div className="bg-gray-900 px-3 py-2 text-xs text-gray-400 truncate border-b border-gray-800">
              {viewing.url}
            </div>
            <iframe srcDoc={viewing.content} className="w-full h-[70vh] bg-white" sandbox="allow-same-origin" title="Snapshot" />
          </div>
        )}
      </div>
    </div>
  )
}

function GlobeIcon() { return <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg> }
