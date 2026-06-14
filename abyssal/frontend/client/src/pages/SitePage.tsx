import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getSite, type Site } from '../hooks/useAbyssalApi'
import { Loader2, ExternalLink, Copy } from 'lucide-react'

export default function SitePage() {
  const { hostname } = useParams<{ hostname: string }>()
  const [site, setSite] = useState<Site | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!hostname) return
    setLoading(true)
    getSite(hostname).then(setSite).catch(() => {}).finally(() => setLoading(false))
  }, [hostname])

  const copyB32 = () => {
    if (site?.b32) {
      navigator.clipboard.writeText(site.b32)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }
  }

  if (loading) return <div className="p-4 flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>
  if (!site) return <div className="p-4 text-gray-500">Site not found</div>

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-4">
        <span className={`w-3 h-3 rounded-full ${site.checks_online > site.checks_offline ? 'bg-green-500' : 'bg-red-500'}`} />
        <h1 className="text-2xl font-bold">{site.title || site.hostname}</h1>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="border border-gray-800 rounded-lg p-3">
          <span className="text-xs text-gray-500 uppercase">Hostname</span>
          <p className="text-sm">{site.hostname}</p>
        </div>
        <div className="border border-gray-800 rounded-lg p-3">
          <span className="text-xs text-gray-500 uppercase">Status</span>
          <p className="text-sm">{site.checks_online} online / {site.checks_offline} offline checks</p>
        </div>
        {site.language && (
          <div className="border border-gray-800 rounded-lg p-3">
            <span className="text-xs text-gray-500 uppercase">Language</span>
            <p className="text-sm">{site.language}</p>
          </div>
        )}
        {site.site_type && (
          <div className="border border-gray-800 rounded-lg p-3">
            <span className="text-xs text-gray-500 uppercase">Type</span>
            <p className="text-sm">{site.site_type}</p>
          </div>
        )}
        {site.b32 && (
          <div className="border border-gray-800 rounded-lg p-3 col-span-2">
            <span className="text-xs text-gray-500 uppercase">b32 Address</span>
            <div className="flex items-center gap-2 mt-1">
              <code className="text-sm text-cyan-400 truncate">{site.b32}.b32.i2p</code>
              <button onClick={copyB32} className="text-gray-500 hover:text-white shrink-0">
                {copied ? <span className="text-green-400 text-xs">Copied!</span> : <Copy className="w-3 h-3" />}
              </button>
            </div>
          </div>
        )}
        {site.address_helper && (
          <div className="border border-gray-800 rounded-lg p-3 col-span-2">
            <span className="text-xs text-gray-500 uppercase">Address Helper</span>
            <p className="text-xs text-gray-400 mt-1 break-all">{site.address_helper.slice(0, 80)}...</p>
          </div>
        )}
      </div>

      {site.pages && site.pages.length > 0 && (
        <div>
          <h2 className="text-lg font-medium mb-3">Crawled Pages ({site.pages.length})</h2>
          <div className="space-y-2">
            {site.pages.map(p => (
              <div key={p.id} className="border border-gray-800 rounded-lg p-3 flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-sm text-cyan-400 truncate">{p.title || p.url}</p>
                  <p className="text-xs text-gray-500 truncate">{p.url}</p>
                </div>
                <div className="flex items-center gap-2 text-xs shrink-0">
                  {p.language && <span className="bg-gray-800 px-1.5 py-0.5 rounded">{p.language}</span>}
                  {p.site_type && <span className="bg-gray-800 px-1.5 py-0.5 rounded">{p.site_type}</span>}
                  <a href={p.url} target="_blank" rel="noreferrer"><ExternalLink className="w-3 h-3 text-gray-500" /></a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
