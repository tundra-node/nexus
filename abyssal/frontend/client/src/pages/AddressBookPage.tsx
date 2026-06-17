import { useState, useEffect, useCallback } from 'react'
import { getAddressbook, type AddressbookEntry } from '../hooks/useAbyssalApi'
import { Search, Copy, Check, Download, RefreshCw, ExternalLink, Link as LinkIcon } from 'lucide-react'

function fullB32(b32: string) {
  if (!b32) return ''
  return b32.endsWith('.b32.i2p') ? b32 : `${b32}.b32.i2p`
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(text).then(() => {
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        })
      }}
      title={`Copy`}
      className="p-0.5 rounded text-gray-600 hover:text-gray-300 transition-colors shrink-0"
    >
      {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
    </button>
  )
}

function StatusDot({ entry }: { entry: AddressbookEntry }) {
  if (!entry.last_crawled) return <span className="w-1.5 h-1.5 rounded-full bg-gray-700 inline-block" title="unknown" />
  if (entry.likely_online) return <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" title="online" />
  if (entry.ever_online)   return <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 inline-block" title="intermittent" />
  return <span className="w-1.5 h-1.5 rounded-full bg-red-500 inline-block" title="offline" />
}

const PER_PAGE = 100

export default function AddressBookPage() {
  const [entries, setEntries] = useState<AddressbookEntry[]>([])
  const [total, setTotal]     = useState(0)
  const [page, setPage]       = useState(1)
  const [draft, setDraft]     = useState('')
  const [q, setQ]             = useState('')
  const [loading, setLoading] = useState(true)
  const [allCopied, setAllCopied] = useState(false)

  const load = useCallback((query: string, pg: number) => {
    setLoading(true)
    getAddressbook(query, pg, PER_PAGE)
      .then(r => { setEntries(r.sites); setTotal(r.total) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => { setQ(draft); setPage(1) }, 300)
    return () => clearTimeout(t)
  }, [draft])

  useEffect(() => { load(q, page) }, [load, q, page])

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE))

  const buildHostsTxt = (sites: AddressbookEntry[]) =>
    sites.filter(s => s.b32).map(s => `${s.hostname}=${fullB32(s.b32)}`).join('\n') + '\n'

  const exportHostsTxt = () =>
    getAddressbook('', 1, 100_000).then(r => {
      const blob = new Blob([buildHostsTxt(r.sites)], { type: 'text/plain' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = 'hosts.txt'
      a.click()
    })

  const copyAllHostsTxt = () =>
    getAddressbook('', 1, 100_000).then(r => {
      navigator.clipboard.writeText(buildHostsTxt(r.sites)).then(() => {
        setAllCopied(true)
        setTimeout(() => setAllCopied(false), 2000)
      })
    })

  return (
    <div className="p-4 max-w-5xl mx-auto space-y-4">

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Address Book</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {total.toLocaleString()} known .i2p sites — public, no login required
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            type="button"
            onClick={copyAllHostsTxt}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-700 text-xs text-gray-400 hover:text-white hover:border-gray-500 transition-colors"
          >
            {allCopied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
            {allCopied ? 'Copied!' : 'Copy hosts.txt'}
          </button>
          <button
            type="button"
            onClick={exportHostsTxt}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-700 text-xs text-gray-400 hover:text-white hover:border-gray-500 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Export hosts.txt
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
        <input
          type="text"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          placeholder="Filter by hostname or b32…"
          className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-cyan-600 transition-colors"
        />
        {loading && (
          <RefreshCw className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-600 animate-spin" />
        )}
      </div>

      {/* Table */}
      <div className="border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 bg-gray-900/60 text-left">
              <th className="px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider w-8"></th>
              <th className="px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Hostname</th>
              <th className="px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">B32 Address</th>
              <th className="px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider w-24">Links</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {entries.length === 0 && !loading && (
              <tr>
                <td colSpan={4} className="text-center py-12 text-gray-600 text-sm">
                  {q ? 'No sites match your search.' : 'No sites indexed yet — run a crawl first.'}
                </td>
              </tr>
            )}
            {entries.map(entry => {
              const b32f  = fullB32(entry.b32)
              const ahUrl = entry.address_helper
                ? `http://${entry.hostname}/?i2paddresshelper=${encodeURIComponent(entry.address_helper)}`
                : ''
              return (
                <tr key={entry.hostname} className="hover:bg-gray-900/40 transition-colors">
                  {/* Status dot */}
                  <td className="px-4 py-3 text-center">
                    <StatusDot entry={entry} />
                  </td>

                  {/* Hostname */}
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-1.5">
                      <a
                        href={`/site/${entry.hostname}`}
                        className="font-medium text-gray-100 hover:text-cyan-400 transition-colors"
                      >
                        {entry.hostname}
                      </a>
                      <CopyBtn text={entry.hostname} />
                    </div>
                    {/* hosts.txt line inline */}
                    {b32f && (
                      <div className="flex items-center gap-1 mt-1">
                        <code className="text-xs text-gray-700 truncate max-w-xs">
                          {entry.hostname}={b32f}
                        </code>
                        <CopyBtn text={`${entry.hostname}=${b32f}`} />
                      </div>
                    )}
                  </td>

                  {/* B32 */}
                  <td className="px-3 py-3">
                    {b32f ? (
                      <div className="flex items-center gap-1.5">
                        <a
                          href={`http://${b32f}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-mono text-xs text-cyan-700 hover:text-cyan-400 transition-colors break-all"
                        >
                          {b32f}
                        </a>
                        <CopyBtn text={b32f} />
                      </div>
                    ) : (
                      <span className="text-xs text-gray-700 italic">not resolved</span>
                    )}
                  </td>

                  {/* Action links */}
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <a
                        href={`http://${entry.hostname}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Open via I2P proxy"
                        className="text-gray-600 hover:text-cyan-400 transition-colors"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                      {ahUrl && (
                        <a
                          href={ahUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          title="Address helper — registers the hostname in your I2P router"
                          className="text-gray-600 hover:text-purple-400 transition-colors"
                        >
                          <LinkIcon className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {((page - 1) * PER_PAGE + 1).toLocaleString()}–
            {Math.min(page * PER_PAGE, total).toLocaleString()} of {total.toLocaleString()}
          </span>
          <div className="flex gap-1">
            <button type="button" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="px-3 py-1 rounded border border-gray-800 hover:border-gray-600 disabled:opacity-30 transition-colors">
              ← Prev
            </button>
            <button type="button" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              className="px-3 py-1 rounded border border-gray-800 hover:border-gray-600 disabled:opacity-30 transition-colors">
              Next →
            </button>
          </div>
        </div>
      )}

      <p className="text-xs text-gray-700 text-center pb-2">
        hosts.txt format: <code className="text-gray-600">hostname=b32address</code> — compatible with I2P addressbook subscriptions
      </p>
    </div>
  )
}
