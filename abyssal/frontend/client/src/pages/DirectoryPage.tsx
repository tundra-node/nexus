import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getSites, getFacets, type Site, type Facets } from '../hooks/useAbyssalApi'
import { Globe, Loader2 } from 'lucide-react'

export default function DirectoryPage() {
  const [sites, setSites] = useState<Site[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [facets, setFacets] = useState<Facets | null>(null)
  const [langFilter, setLangFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [page, setPage] = useState(1)

  useEffect(() => {
    getFacets().then(setFacets).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    getSites(langFilter, typeFilter, page).then(data => {
      setSites(data.results)
      setTotal(data.total)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [langFilter, typeFilter, page])

  return (
    <div className="p-4 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-cyan-400 mb-4">Site Directory</h1>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <select value={langFilter} onChange={e => { setLangFilter(e.target.value); setPage(1) }}
          className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-300">
          <option value="">All languages</option>
          {facets?.languages.map(f => <option key={f.language} value={f.language}>{f.language} ({f.count})</option>)}
        </select>
        <select value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPage(1) }}
          className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-300">
          <option value="">All types</option>
          {facets?.site_types.map(f => <option key={f.site_type} value={f.site_type}>{f.site_type} ({f.count})</option>)}
        </select>
        <span className="text-sm text-gray-500">{total} sites</span>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-gray-400 py-8"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>
      ) : sites.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <Globe className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No sites found.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {sites.map(site => (
            <Link key={site.hostname} to={`/site/${site.hostname}`}
              className="border border-gray-800 rounded-lg p-3 hover:border-gray-700 hover:bg-gray-900/50">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full shrink-0 ${site.checks_online > site.checks_offline ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="font-medium text-sm truncate">{site.title || site.hostname}</span>
              </div>
              <p className="text-xs text-gray-500 truncate mt-1">{site.hostname}</p>
              <div className="flex items-center gap-2 mt-2 text-xs">
                {site.language && <span className="bg-gray-800 px-1.5 py-0.5 rounded">{site.language}</span>}
                {site.site_type && <span className="bg-gray-800 px-1.5 py-0.5 rounded">{site.site_type}</span>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
