import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getSite, type Site, type PageTreeEntry } from '../hooks/useAbyssalApi'
import { Loader2, ExternalLink, Copy, Check, Link as LinkIcon, Folder, File, ChevronRight, ChevronDown } from 'lucide-react'

// b32 is stored as raw hash; full I2P address is hash.b32.i2p
function fullB32(b32: string) {
  if (!b32) return ''
  return b32.endsWith('.b32.i2p') ? b32 : `${b32}.b32.i2p`
}

// Build an address-helper URL so the user's I2P router learns the mapping.
// Format: http://<hostname>/?i2paddresshelper=<url-encoded base64 destination>
function addressHelperUrl(hostname: string, addressHelper: string) {
  if (!hostname || !addressHelper) return ''
  return `http://${hostname}/?i2paddresshelper=${encodeURIComponent(addressHelper)}`
}

function CopyBtn({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <button
      type="button"
      onClick={copy}
      className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-gray-500 hover:text-gray-200 hover:bg-gray-800 transition-colors"
      title={`Copy ${label ?? text}`}
    >
      {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
      {label && <span>{copied ? 'Copied' : label}</span>}
    </button>
  )
}

function TreeFile({ entry: e }: { entry: PageTreeEntry }) {
  if (!e.page) return null
  return (
    <a
      href={e.page.url}
      target="_blank"
      rel="noreferrer"
      className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-800/50 hover:text-cyan-400 transition-colors group"
    >
      <File className="w-3.5 h-3.5 text-gray-600 shrink-0" />
      <span className="truncate">{e.page.title || e.name}</span>
      <span className="hidden group-hover:inline text-xs text-gray-600 truncate ml-auto">{e.page.url}</span>
      {e.page.language && <span className="text-[10px] text-gray-600 bg-gray-800 px-1 rounded shrink-0">{e.page.language}</span>}
    </a>
  )
}

function PageTree({ nodes, depth }: { nodes: PageTreeEntry[]; depth: number }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const toggle = (key: string) => setCollapsed(prev => {
    const next = new Set(prev)
    if (next.has(key)) next.delete(key); else next.add(key)
    return next
  })
  return (
    <div className={depth > 0 ? 'ml-4 border-l border-gray-800/50' : ''}>
      {nodes.map((e, i) => {
        const key = `${e.name}-${i}`
        if (e.type === 'dir') {
          const open = !collapsed.has(key)
          return (
            <div key={key}>
              <button
                onClick={() => toggle(key)}
                className="flex items-center gap-1.5 w-full px-3 py-1.5 text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-800/50 transition-colors text-left"
              >
                {open ? <ChevronDown className="w-3.5 h-3.5 shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0" />}
                <Folder className="w-3.5 h-3.5 text-cyan-600 shrink-0" />
                <span className="font-medium">{e.name}</span>
                <span className="text-xs text-gray-600 ml-1">({e.children?.length ?? 0})</span>
              </button>
              {open && e.children && <PageTree nodes={e.children} depth={depth + 1} />}
            </div>
          )
        }
        return <TreeFile key={key} entry={e} />
      })}
    </div>
  )
}

export default function SitePage() {
  const { hostname } = useParams<{ hostname: string }>()
  const [site, setSite]     = useState<Site | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!hostname) return
    setLoading(true)
    getSite(hostname).then(setSite).catch(() => {}).finally(() => setLoading(false))
  }, [hostname])

  if (loading) return (
    <div className="p-4 flex items-center gap-2 text-gray-400">
      <Loader2 className="w-4 h-4 animate-spin" /> Loading…
    </div>
  )
  if (!site) return <div className="p-4 text-gray-500">Site not found</div>

  const isOnline   = site.checks_online > site.checks_offline
  const b32Full    = fullB32(site.b32)
  const ahUrl      = addressHelperUrl(site.hostname, site.address_helper)

  return (
    <div className="p-4 max-w-4xl mx-auto space-y-6">

      {/* ── Identity block — hostname + b32 unified ── */}
      <div className="border border-gray-800 rounded-xl p-4 space-y-3">
        <div className="flex items-start gap-3">
          <span className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${isOnline ? 'bg-green-500' : 'bg-red-500'}`} />
          <div className="min-w-0 flex-1">
            {/* Registered hostname (primary) */}
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-bold">{site.title || site.hostname}</h1>
              {site.title && site.title !== site.hostname && (
                <span className="text-sm text-gray-500">{site.hostname}</span>
              )}
              <CopyBtn text={site.hostname} label="hostname" />
              <a
                href={`http://${site.hostname}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-gray-500 hover:text-cyan-400 hover:bg-gray-800 transition-colors"
                title="Open via I2P proxy"
              >
                <ExternalLink className="w-3 h-3" />
                Open
              </a>
            </div>

            {/* B32 address (secondary — cryptographic) */}
            {b32Full && (
              <div className="mt-2 flex items-center gap-2 flex-wrap">
                <code className="text-xs text-cyan-600 break-all">{b32Full}</code>
                <CopyBtn text={b32Full} label="b32" />
                <a
                  href={`http://${b32Full}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-gray-500 hover:text-cyan-400 hover:bg-gray-800 transition-colors"
                  title="Open via b32 address"
                >
                  <ExternalLink className="w-3 h-3" />
                  Open b32
                </a>

                {/* Address helper — teaches the I2P router the hostname→destination mapping */}
                {ahUrl && (
                  <a
                    href={ahUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-gray-500 hover:text-purple-400 hover:bg-gray-800 transition-colors"
                    title="Open via address helper — registers the hostname in your I2P router"
                  >
                    <LinkIcon className="w-3 h-3" />
                    Address helper
                  </a>
                )}
              </div>
            )}
          </div>
        </div>

        {/* hosts.txt line — copy-pasteable */}
        {b32Full && (
          <div className="flex items-center gap-2 bg-gray-900 rounded-lg px-3 py-2">
            <code className="text-xs text-gray-400 flex-1 truncate">
              {site.hostname}={b32Full}
            </code>
            <CopyBtn text={`${site.hostname}=${b32Full}`} label="hosts.txt" />
          </div>
        )}
      </div>

      {/* ── Meta grid ── */}
      <div className="grid grid-cols-2 gap-3">
        <div className="border border-gray-800 rounded-lg p-3">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Status</span>
          <p className="text-sm mt-1">
            <span className={isOnline ? 'text-green-400' : 'text-red-400'}>
              {isOnline ? 'Online' : 'Offline'}
            </span>
            <span className="text-gray-600 ml-2">
              ({site.checks_online}↑ / {site.checks_offline}↓)
            </span>
          </p>
        </div>
        <div className="border border-gray-800 rounded-lg p-3">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Last crawled</span>
          <p className="text-sm mt-1 text-gray-300">
            {site.last_crawled ? new Date(site.last_crawled).toLocaleString() : '—'}
          </p>
        </div>
        {site.language && (
          <div className="border border-gray-800 rounded-lg p-3">
            <span className="text-xs text-gray-500 uppercase tracking-wider">Language</span>
            <p className="text-sm mt-1">{site.language}</p>
          </div>
        )}
        {site.site_type && (
          <div className="border border-gray-800 rounded-lg p-3">
            <span className="text-xs text-gray-500 uppercase tracking-wider">Type</span>
            <p className="text-sm mt-1">{site.site_type}</p>
          </div>
        )}
      </div>

      {/* ── Crawled pages (folder tree) ── */}
      {site.page_tree && site.page_tree.length > 0 && (
        <div>
          <h2 className="text-lg font-medium mb-3">Pages ({site.pages?.length ?? 0})</h2>
          <div className="border border-gray-800 rounded-xl overflow-hidden">
            <PageTree nodes={site.page_tree} depth={0} />
          </div>
        </div>
      )}
    </div>
  )
}
