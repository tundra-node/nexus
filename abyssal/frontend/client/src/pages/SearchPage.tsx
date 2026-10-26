import { useState, useEffect, useCallback } from 'react'
import { Search, Filter, Globe, ExternalLink, Loader2 } from 'lucide-react'
import { search, getFacets, type SearchResult, type Facets } from '../hooks/useAbyssalApi'
import { Link, useSearchParams } from 'react-router-dom'

export default function SearchPage() {
  const [params] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') || '')
  const [results, setResults] = useState<SearchResult[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [facets, setFacets] = useState<Facets | null>(null)
  const [langFilter, setLangFilter] = useState(params.get('lang') || '')
  const [typeFilter, setTypeFilter] = useState(params.get('type') || '')
  const [showFilters, setShowFilters] = useState(params.get('filters') === '1')
  const [bookmarks, setBookmarks] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('abyssal-bookmarks') || '[]') }
    catch { return [] }
  })

  useEffect(() => {
    getFacets().then(setFacets).catch(() => {})
  }, [])

  useEffect(() => {
    localStorage.setItem('abyssal-bookmarks', JSON.stringify(bookmarks))
  }, [bookmarks])

  const doSearch = useCallback(async (p = 1, term = query) => {
    if (!term.trim()) return
    setLoading(true)
    setPage(p)
    try {
      const data = await search(term.trim(), langFilter, typeFilter, p)
      setResults(data.results)
      setTotal(data.total)
      setTotalPages(data.total_pages)
    } catch {
      setResults([])
      setTotal(0)
    }
    setLoading(false)
  }, [query, langFilter, typeFilter])

  // Deep link support: /?q=tunnel&type=docs&filters=1 runs the search on load
  // and on any change to the URL, so a search is shareable as a plain link.
  useEffect(() => {
    const q = params.get('q')
    if (!q) return
    setQuery(q)
    void doSearch(1, q)
    // doSearch changes with the filters, which are read from the URL too
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    doSearch(1)
  }

  const toggleBookmark = (url: string) => {
    setBookmarks(prev => prev.includes(url) ? prev.filter(b => b !== url) : [...prev, url])
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Search header */}
      <div className={`${results.length > 0 ? 'pt-6 pb-4 px-4' : 'flex-1 flex items-center justify-center px-4'}`}>
        <div className={`${results.length > 0 ? '' : 'w-full max-w-2xl'}`}>
          <div className={`flex items-center gap-3 mb-2 ${results.length > 0 ? '' : 'flex-col text-center'}`}>
            <h1 className={`font-bold text-cyan-400 ${results.length > 0 ? 'text-xl' : 'text-5xl mb-6'}`}>
              abyssal
            </h1>
            <form onSubmit={handleSubmit} className={`relative ${results.length > 0 ? 'flex-1 max-w-xl' : 'w-full max-w-2xl'}`}>
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search .i2p sites..."
                className="w-full bg-gray-900 border border-gray-700 rounded-lg py-3 px-4 pl-12 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                autoFocus
              />
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 w-5 h-5" />
            </form>
          </div>

          {results.length > 0 && (
            <div className="flex items-center gap-4 text-sm text-gray-400 mt-1">
              <span>{total.toLocaleString()} results</span>
              <button onClick={() => setShowFilters(!showFilters)} className="flex items-center gap-1 hover:text-white">
                <Filter className="w-3 h-3" /> Filters
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 flex gap-6 px-4 max-w-6xl mx-auto w-full">
        {/* Facet sidebar */}
        {showFilters && facets && (
          <aside className="w-48 shrink-0 space-y-4 text-sm">
            <div>
              <h3 className="text-gray-400 font-medium mb-2 uppercase text-xs tracking-wider">Language</h3>
              <div className="space-y-1">
                <button onClick={() => setLangFilter('')} className={`block w-full text-left px-2 py-1 rounded ${!langFilter ? 'bg-cyan-900/40 text-cyan-300' : 'text-gray-400 hover:text-white'}`}>All</button>
                {facets.languages.map(f => (
                  <button key={f.language} onClick={() => setLangFilter(f.language!)}
                    className={`block w-full text-left px-2 py-1 rounded ${langFilter === f.language ? 'bg-cyan-900/40 text-cyan-300' : 'text-gray-400 hover:text-white'}`}>
                    {f.language} <span className="text-gray-600">({f.count})</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <h3 className="text-gray-400 font-medium mb-2 uppercase text-xs tracking-wider">Type</h3>
              <div className="space-y-1">
                <button onClick={() => setTypeFilter('')} className={`block w-full text-left px-2 py-1 rounded ${!typeFilter ? 'bg-cyan-900/40 text-cyan-300' : 'text-gray-400 hover:text-white'}`}>All</button>
                {facets.site_types.map(f => (
                  <button key={f.site_type} onClick={() => setTypeFilter(f.site_type!)}
                    className={`block w-full text-left px-2 py-1 rounded ${typeFilter === f.site_type ? 'bg-cyan-900/40 text-cyan-300' : 'text-gray-400 hover:text-white'}`}>
                    {f.site_type} <span className="text-gray-600">({f.count})</span>
                  </button>
                ))}
              </div>
            </div>
          </aside>
        )}

        {/* Results / Bookmarks */}
        <div className="flex-1 min-w-0">
          {loading && (
            <div className="flex items-center gap-2 text-gray-400 py-8">
              <Loader2 className="w-4 h-4 animate-spin" /> Searching...
            </div>
          )}

          {!loading && query && results.length === 0 && total === 0 && (
            <div className="text-center py-16 text-gray-500">
              <Globe className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>No results found. Try a different search.</p>
            </div>
          )}

          {!loading && !query && bookmarks.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Bookmarks</h2>
              <div className="space-y-2">
                {bookmarks.map(url => (
                  <div key={url} className="flex items-center gap-2 text-sm">
                    <a href={url} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline truncate">{url}</a>
                    <button onClick={() => toggleBookmark(url)} className="text-gray-600 hover:text-red-400 shrink-0">✕</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!loading && results.length > 0 && (
            <div className="space-y-4">
              {results.map(r => (
                <div key={r.id} className="border border-gray-800 rounded-lg p-4 hover:border-gray-700">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <a href={r.url} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline font-medium text-lg">
                        {r.title || r.url}
                      </a>
                      <p className="text-sm text-green-500/80 truncate">{r.url}</p>
                      {r.snippet && (
                        <p className="text-sm text-gray-400 mt-1 line-clamp-2" dangerouslySetInnerHTML={{ __html: r.snippet }} />
                      )}
                      {!r.snippet && r.description && (
                        <p className="text-sm text-gray-400 mt-1 line-clamp-2">{r.description}</p>
                      )}
                      <div className="flex items-center gap-2 mt-2 text-xs">
                        {r.language && <span className="bg-gray-800 px-2 py-0.5 rounded text-gray-400">{r.language}</span>}
                        {r.site_type && <span className="bg-gray-800 px-2 py-0.5 rounded text-gray-400">{r.site_type}</span>}
                        {r.b32 && <span className="text-gray-600 truncate max-w-[120px]" title={r.b32}>{r.b32.slice(0, 12)}...</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Link to={`/wayback?url=${encodeURIComponent(r.url)}`} className="text-gray-600 hover:text-cyan-400 text-xs" title="Cached version">
                        Cached
                      </Link>
                      <button onClick={() => toggleBookmark(r.url)} className="text-gray-600 hover:text-yellow-400 text-xs" title="Bookmark">
                        {bookmarks.includes(r.url) ? '★' : '☆'}
                      </button>
                      <a href={`/site/${new URL(r.url).hostname}`} className="text-gray-600 hover:text-white">
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-6 pb-8">
              {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map(p => (
                <button key={p} onClick={() => doSearch(p)}
                  className={`px-3 py-1 rounded text-sm ${p === page ? 'bg-cyan-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
