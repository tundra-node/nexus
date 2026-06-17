/* Abyssal — I2P Search Engine Frontend
 *
 * Design: Dark theme with I2P purple/blue accents. Each page has a distinct
 * visual identity. Built for slow connections — no framework, minimal JS.
 *
 * I2P-specific optimizations:
 * - 45s request timeout, auto-retry with backoff
 * - localStorage caching (5 min TTL)
 * - Request cancellation on navigation
 * - Debounced search, prefetch on hover
 * - Connection status monitor
 */

const API = '/api/abyssal';
const PER_PAGE = 20;
const REQUEST_TIMEOUT = 45000;
const CACHE_TTL = 5 * 60 * 1000;
const RETRY_DELAYS = [1000, 3000, 7000];

/* ── Connection Monitor ─────────────────────────────────────────────────── */

const ConnMonitor = {
  el: null,
  _interval: null,
  init() {
    this.el = document.getElementById('conn-status');
    this.check();
    this._interval = setInterval(() => this.check(), 30000);
  },
  async check() {
    if (!this.el) return;
    const t0 = Date.now();
    try {
      const r = await fetch(`${API}/sites?page=1&per_page=1`, { signal: AbortSignal.timeout(10000) });
      const ms = Date.now() - t0;
      if (r.ok) {
        this.el.className = 'conn-indicator ' + (ms > 5000 ? 'slow' : 'online');
        this.el.title = ms > 5000 ? 'Connected (slow — I2P is routing)' : 'Connected to Abyssal';
      } else {
        this.el.className = 'conn-indicator offline';
        this.el.title = 'API error';
      }
    } catch (_) {
      this.el.className = 'conn-indicator offline';
      this.el.title = 'Disconnected — is i2pd running?';
    }
  }
};

/* ── Cache ──────────────────────────────────────────────────────────────── */

const Cache = {
  get(key) {
    try {
      const e = localStorage.getItem('ab_' + key);
      if (!e) return null;
      const { ts, data } = JSON.parse(e);
      if (Date.now() - ts > CACHE_TTL) { localStorage.removeItem('ab_' + key); return null; }
      return data;
    } catch (_) { return null; }
  },
  set(key, data) {
    try { localStorage.setItem('ab_' + key, JSON.stringify({ ts: Date.now(), data })); } catch (_) {}
  }
};

/* ── Router ─────────────────────────────────────────────────────────────── */

function highlightNav(base) {
  document.querySelectorAll('.nav-links a').forEach(a => {
    a.classList.toggle('active', a.dataset.nav === base);
  });
}

function route() {
  const path = location.pathname.replace(/\/$/, '') || '/';
  const [base, ...rest] = path.split('/').filter(Boolean);
  switch (base) {
    case 'browse':      highlightNav('browse'); renderPage(DirectoryPage); break;
    case 'site':        highlightNav(''); renderPage(SiteDetailPage, rest[0]); break;
    case 'wayback':     highlightNav('wayback'); renderPage(WaybackPage); break;
    case 'addressbook': highlightNav('addressbook'); renderPage(AddressBookPage); break;
    default:            highlightNav(''); renderPage(HomePage); break;
  }
}

function navigate(url) { history.pushState(null, '', url); }
window.addEventListener('popstate', route);
window.onerror = function(msg, src, line, col, err) {
  console.error('JS Error:', msg, 'at', src + ':' + line + ':' + col);
  const m = document.getElementById('main');
  if (m) m.innerHTML = `<div class="error-box"><div class="error-icon">⚠</div><div class="error-msg">JavaScript Error</div><div class="error-hint" style="font-family:monospace;font-size:0.8rem;word-break:break-all">${esc(String(msg))}<br>at ${esc(src||'')}:${line}:${col}</div><button onclick="location.reload()">Reload</button></div>`;
};
document.addEventListener('DOMContentLoaded', () => {
  ConnMonitor.init();
  try { route(); } catch(e) { console.error('Route error:', e); document.getElementById('main').innerHTML = errorBox('Routing error: ' + e.message, () => route()); }
});

/* ── Page Rendering ─────────────────────────────────────────────────────── */

let _currentPage = null;

async function renderPage(Page, ...args) {
  const m = document.getElementById('main');
  if (_currentPage && _currentPage.abort) _currentPage.abort();
  m.innerHTML = spinner('Loading...', 'Routing through I2P — this may take a moment');
  try {
    const p = new Page(m, ...args);
    _currentPage = p;
    await p.render();
  } catch (e) {
    if (e.name === 'AbortError') return;
    m.innerHTML = errorBox(e.message, () => renderPage(Page, ...args));
  }
}

/* ── API Helper ─────────────────────────────────────────────────────────── */

async function api(url, params = {}, opts = {}) {
  const { timeout = REQUEST_TIMEOUT, retries = 2, cacheKey = null, signal } = opts;
  if (cacheKey) { const c = Cache.get(cacheKey); if (c) return c; }
  const qs = Object.entries(params).filter(([, v]) => v != null && v !== '').map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
  const full = `${API}${url}${qs ? '?' + qs : ''}`;
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    if (attempt > 0) await new Promise(r => setTimeout(r, RETRY_DELAYS[Math.min(attempt - 1, RETRY_DELAYS.length - 1)]));
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      if (signal) signal.addEventListener('abort', () => controller.abort(), { once: true });
      const r = await fetch(full, { signal: controller.signal });
      clearTimeout(timer);
      if (!r.ok) { const body = await r.text().catch(() => ''); throw new Error(`API ${r.status}: ${body.slice(0, 200)}`); }
      const data = await r.json();
      if (cacheKey) Cache.set(cacheKey, data);
      return data;
    } catch (e) {
      lastErr = e;
      if (e.name === 'AbortError') throw e;
      if (e.message && e.message.match(/API 4\d\d/)) throw e;
    }
  }
  throw lastErr;
}

/* ── UI Components ──────────────────────────────────────────────────────── */

function spinner(text, hint) {
  return `<div class="loading"><div class="spinner"></div><div class="loading-text">${esc(text)}</div>${hint ? `<div class="loading-hint">${esc(hint)}</div>` : ''}</div>`;
}

function errorBox(msg, retryFn) {
  const btn = retryFn ? `<button id="retry-btn">↻ Retry</button>` : '';
  const html = `<div class="error-box"><div class="error-icon">⚠</div><div class="error-msg">${esc(msg)}</div>${btn}<div class="error-hint">I2P connections can be slow or intermittent. If this persists, check that i2pd is running and has active peers.</div></div>`;
  // Attach retry handler after DOM update
  if (retryFn) setTimeout(() => { const b = document.getElementById('retry-btn'); if (b) b.onclick = retryFn; }, 0);
  return html;
}

function esc(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]); }
function safeId(s) { return 'id-' + String(s).replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 100); }
function statusBadge(online) { return `<span class="badge ${online ? 'online' : 'offline'}">${online ? 'Online' : 'Offline'}</span>`; }
function extractHostname(url) { try { return new URL(url).hostname; } catch (_) { return url; } }
function formatBytes(n) { if (!n) return '0 B'; const u = ['B','KB','MB','GB']; let i = 0; while (n >= 1024 && i < u.length-1) { n /= 1024; i++; } return n.toFixed(1) + ' ' + u[i]; }
function timeAgo(iso) { if (!iso) return 'never'; const d = new Date(iso); const s = Math.floor((Date.now() - d.getTime()) / 1000); if (s < 60) return 'just now'; if (s < 3600) return Math.floor(s/60) + 'm ago'; if (s < 86400) return Math.floor(s/3600) + 'h ago'; return Math.floor(s/86400) + 'd ago'; }

function highlight(text, query) {
  if (!query) return esc(text);
  const re = new RegExp(`(${esc(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return esc(text).replace(re, '<mark style="background:rgba(124,106,239,0.3);color:#fff;padding:0 2px;border-radius:2px">$1</mark>');
}

function pageNav(page, total, cb) {
  const last = Math.ceil(total / PER_PAGE);
  if (last <= 1) return '';
  const d = document.createElement('div');
  d.className = 'pagination';
  d.innerHTML = `<button class="prev" ${page <= 1 ? 'disabled' : ''}>← Prev</button><span>Page ${page} of ${last}</span><button class="next" ${page >= last ? 'disabled' : ''}>Next →</button>`;
  d.querySelector('.prev').onclick = () => cb(page - 1);
  d.querySelector('.next').onclick = () => cb(page + 1);
  return d.outerHTML;
}

function lastUpdated() { return `<div class="last-updated">Updated ${new Date().toLocaleTimeString()}</div>`; }

function outproxyUrl(hostname) {
  return `https://anubis.techaro.lol/${hostname}`;
}

/* ── Prefetch ────────────────────────────────────────────────────────────── */

document.addEventListener('mouseover', (e) => {
  const a = e.target.closest('a[href^="/site/"]');
  if (!a || a.dataset.prefetched) return;
  a.dataset.prefetched = '1';
  const h = a.getAttribute('href').replace('/site/', '');
  api(`/sites/${encodeURIComponent(h)}`, {}, { cacheKey: 'site_' + h, retries: 0 }).catch(() => {});
});

/* ═══════════════════════════════════════════════════════════════════════════
   HOME PAGE
   ═══════════════════════════════════════════════════════════════════════════ */

class HomePage {
  constructor(mount) { this.m = mount; this._ctrl = null; this._debounce = null; }
  abort() { if (this._ctrl) this._ctrl.abort(); if (this._debounce) clearTimeout(this._debounce); }

  async render() {
    // Fetch stats in parallel
    const statsP = api('/wayback/stats', {}, { cacheKey: 'home_stats', retries: 0, timeout: 10000 }).catch(() => null);
    const sitesP = api('/sites', { page: 1, per_page: 1 }, { cacheKey: 'home_sites', retries: 0, timeout: 10000 }).catch(() => null);

    this.m.innerHTML = `
      <div class="home-hero">
        <h1>Search I2P</h1>
        <p class="hero-sub">Explore the invisible web — indexed, archived, and searchable.</p>
        <div class="search-box hero-search">
          <input id="sq" type="text" placeholder="Search I2P sites..." autocomplete="off">
          <button id="sb">Search</button>
        </div>
        <div class="filters">
          <select id="flang"><option value="">All languages</option></select>
          <select id="ftype"><option value="">All types</option></select>
        </div>
      </div>
      <div id="home-stats">${spinner('Loading stats...')}</div>
      <div id="results"></div>`;

    this.inp = document.getElementById('sq');
    this.btn = document.getElementById('sb');
    this.res = document.getElementById('results');
    this.flang = document.getElementById('flang');
    this.ftype = document.getElementById('ftype');

    // Facets
    try {
      const f = await api('/facets', {}, { cacheKey: 'facets' });
      this.flang.innerHTML += (f.languages||[]).map(l => `<option value="${esc(l.language)}">${esc(l.language)} (${l.count})</option>`).join('');
      this.ftype.innerHTML += (f.site_types||[]).map(t => `<option value="${esc(t.site_type)}">${esc(t.site_type)} (${t.count})</option>`).join('');
    } catch (_) {}

    // Stats
    const [stats, sites] = await Promise.all([statsP, sitesP]);
    const el = document.getElementById('home-stats');
    if (stats && el) {
      el.innerHTML = `
        <div class="home-stats-grid">
          <div class="stat-card"><div class="stat-num">${sites ? sites.total : '—'}</div><div class="stat-label">Sites Discovered</div></div>
          <div class="stat-card"><div class="stat-num">${stats.total_snapshots || 0}</div><div class="stat-label">Wayback Snapshots</div></div>
          <div class="stat-card"><div class="stat-num">${stats.total_urls || 0}</div><div class="stat-label">URLs Tracked</div></div>
          <div class="stat-card"><div class="stat-num">${formatBytes(stats.total_size_bytes)}</div><div class="stat-label">Archive Size</div></div>
        </div>`;
    } else if (el) { el.innerHTML = ''; }

    // Update footer
    const fs = document.getElementById('footer-stats');
    if (fs && sites) { fs.textContent = `${sites.total} sites indexed`; }

    // Search handlers
    this.btn.onclick = () => this.search(1);
    this.inp.onkeydown = (e) => { if (e.key === 'Enter') this.search(1); };
    this.inp.oninput = () => { clearTimeout(this._debounce); this._debounce = setTimeout(() => { if (this.inp.value.length >= 3) this.search(1); }, 400); };
    this.flang.onchange = () => this.search(1);
    this.ftype.onchange = () => this.search(1);

    // Restore from URL
    const p = new URLSearchParams(location.search);
    if (p.get('q')) { this.inp.value = p.get('q'); this.flang.value = p.get('lang') || ''; this.ftype.value = p.get('site_type') || ''; this.search(parseInt(p.get('page')) || 1); }
  }

  async search(page) {
    const q = this.inp.value, lang = this.flang.value, type = this.ftype.value;
    if (!q) { this.res.innerHTML = ''; return; }
    if (this._ctrl) this._ctrl.abort();
    this._ctrl = new AbortController();
    const qs = `q=${encodeURIComponent(q)}&page=${page}&per_page=${PER_PAGE}&lang=${encodeURIComponent(lang)}&site_type=${encodeURIComponent(type)}`;
    navigate(`/?${qs}`);
    this.res.innerHTML = spinner('Searching I2P...', 'Querying the search index through the I2P network');
    this.btn.disabled = true;
    try {
      const d = await api(`/search?${qs}`, {}, { signal: this._ctrl.signal, cacheKey: `search_${q}_${page}_${lang}_${type}` });
      this.btn.disabled = false;
      if (!d.results || !d.results.length) { this.res.innerHTML = '<p>No results found. Try a broader query — the I2P index is still growing.</p>'; return; }
      this.res.innerHTML = d.results.map(r => {
        const h = r.hostname || extractHostname(r.url);
        const b32 = r.b32 ? `<span style="color:var(--dim);font-size:0.75rem">${esc(r.b32.slice(0,20))}…</span>` : '';
        return `<div class="card site-card">
          <div class="site-info" style="width:100%">
            <h3><a href="/site/${esc(h)}" data-prefetch>${esc(h)}</a></h3>
            <div class="site-meta">
              ${r.language ? `<span class="badge type">${esc(r.language)}</span>` : ''}
              ${r.site_type ? `<span class="badge type">${esc(r.site_type)}</span>` : ''}
              ${b32}
              <a href="${outproxyUrl(h)}" target="_blank" rel="noopener" style="color:var(--accent2);margin-left:auto" title="Visit via outproxy">◉ Live</a>
            </div>
            ${r.snippet ? `<div class="snippet" style="max-height:3.6em;overflow:hidden">${esc(r.snippet.replace(/<[^>]+>/g, '').slice(0, 200))}</div>` : ''}
          </div>
        </div>`;
      }).join('') + pageNav(page, d.total, (p) => this.search(p)) + lastUpdated();
    } catch (e) {
      this.btn.disabled = false;
      if (e.name === 'AbortError') return;
      this.res.innerHTML = errorBox(e.message, () => this.search(page));
    }
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   DIRECTORY PAGE
   ═══════════════════════════════════════════════════════════════════════════ */

class DirectoryPage {
  constructor(mount) { this.m = mount; this.page = 1; }

  async render() {
    this.m.innerHTML = `
      <div class="section-header">
        <h1>Site Directory</h1>
        <span style="color:var(--dim);font-size:0.85rem">Known I2P sites discovered by the crawler</span>
      </div>
      <div id="dir-list">${spinner('Loading directory...', 'Fetching known I2P sites')}</div>`;
    const dl = document.getElementById('dir-list');
    try {
      const d = await api(`/sites`, { page: this.page, per_page: PER_PAGE }, { cacheKey: `dir_${this.page}` });
      if (!d.results || !d.results.length) { dl.innerHTML = '<p>No sites discovered yet. The crawler is still exploring I2P.</p>'; return; }
      dl.innerHTML = d.results.map(s => {
        const online = s.checks_online > s.checks_offline && s.checks_online > 0;
        const initial = s.hostname.charAt(0).toUpperCase();
        return `<div class="card site-card">
          <div class="site-icon">${initial}</div>
          <div class="site-info">
            <h3><a href="/site/${esc(s.hostname)}" data-prefetch>${esc(s.hostname)}</a></h3>
            <div class="site-meta">
              ${statusBadge(online)}
              ${s.language ? `<span class="badge type">${esc(s.language)}</span>` : ''}
              ${s.site_type && s.site_type !== 'website' ? `<span class="badge type">${esc(s.site_type)}</span>` : ''}
              <span style="color:var(--dim)">${s.last_seen_online ? timeAgo(s.last_seen_online) : 'never seen'}</span>
              <a href="${outproxyUrl(s.hostname)}" target="_blank" rel="noopener" style="color:var(--accent2)" title="Visit via outproxy">◉</a>
            </div>
          </div>
        </div>`;
      }).join('') + pageNav(this.page, d.total, (p) => { this.page = p; this.render(); }) + lastUpdated();
    } catch (e) { dl.innerHTML = errorBox(e.message, () => this.render()); }
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   SITE DETAIL PAGE
   ═══════════════════════════════════════════════════════════════════════════ */

class SiteDetailPage {
  constructor(mount, hostname) { this.m = mount; this.hostname = hostname; }

  async render() {
    this.m.innerHTML = `<a href="/browse" style="color:var(--muted);font-size:0.85rem;text-decoration:none">← Directory</a><h1 style="margin-top:0.5rem">${esc(this.hostname)}</h1><div id="site-detail">${spinner('Loading site...', 'Fetching site data through I2P')}</div>`;
    const sd = document.getElementById('site-detail');
    try {
      const s = await api(`/sites/${encodeURIComponent(this.hostname)}`, {}, { cacheKey: 'site_' + this.hostname });
      const online = s.checks_online > s.checks_offline && s.checks_online > 0;
      const totalChecks = (s.checks_online || 0) + (s.checks_offline || 0) + (s.checks_limited || 0);
      const uptime = totalChecks > 0 ? Math.round((s.checks_online / totalChecks) * 100) : 0;
      sd.innerHTML = `
        <div class="card">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
            <div>
              <div style="font-size:1.1rem;font-weight:600;margin-bottom:0.25rem">${esc(this.hostname)}</div>
              <div class="meta">
                ${statusBadge(online)}
                ${s.language ? `<span class="badge type">${esc(s.language)}</span>` : ''}
                ${s.site_type ? `<span class="badge type">${esc(s.site_type)}</span>` : ''}
              </div>
            </div>
            <a href="${outproxyUrl(this.hostname)}" target="_blank" rel="noopener" style="padding:0.5rem 1rem;background:linear-gradient(135deg,var(--accent),#6a58d9);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;white-space:nowrap">◉ Visit Site</a>
          </div>
          ${s.b32 ? `<div style="font-family:monospace;font-size:0.8rem;color:var(--dim);word-break:break-all;margin-bottom:1rem;padding:0.5rem;background:var(--bg3);border-radius:var(--radius)">${esc(s.b32)}</div>` : ''}
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;text-align:center">
            <div style="padding:0.75rem;background:rgba(63,185,80,0.08);border-radius:var(--radius)">
              <div style="font-size:1.5rem;font-weight:700;color:var(--green)">${s.checks_online || 0}</div>
              <div style="font-size:0.75rem;color:var(--muted)">Times Up</div>
            </div>
            <div style="padding:0.75rem;background:rgba(248,81,73,0.08);border-radius:var(--radius)">
              <div style="font-size:1.5rem;font-weight:700;color:var(--red)">${s.checks_offline || 0}</div>
              <div style="font-size:0.75rem;color:var(--muted)">Times Down</div>
            </div>
            <div style="padding:0.75rem;background:rgba(210,153,34,0.08);border-radius:var(--radius)">
              <div style="font-size:1.5rem;font-weight:700;color:var(--orange)">${s.checks_limited || 0}</div>
              <div style="font-size:0.75rem;color:var(--muted)">Questionable</div>
            </div>
          </div>
          <div style="margin-top:1rem;font-size:0.85rem;color:var(--muted)">
            Uptime: <strong style="color:${uptime > 80 ? 'var(--green)' : uptime > 50 ? 'var(--orange)' : 'var(--red)'}">${uptime}%</strong>
            ${s.last_seen_online ? ` · Last seen ${timeAgo(s.last_seen_online)}` : ''}
            ${s.last_crawled ? ` · Last crawled ${timeAgo(s.last_crawled)}` : ''}
          </div>
        </div>
        ${lastUpdated()}`;
    } catch (e) { sd.innerHTML = errorBox(e.message, () => this.render()); }
  }

  renderTree(nodes) {
    if (!nodes || !nodes.length) return '<p>No pages indexed yet.</p>';
    let html = '<div class="tree">';
    for (const n of nodes) {
      if (n.name === '(index)') continue;
      if (n.type === 'dir') {
        html += `<div class="folder"><div class="folder-toggle" onclick="this.parentElement.classList.toggle('open')">${esc(n.name)}</div><div class="folder-children">${this.renderTree(n.children)}</div></div>`;
      } else if (n.page) {
        html += `<div class="file"><a href="/" onclick="return false">${esc(n.page.title || n.name)}</a></div>`;
      }
    }
    return html + '</div>';
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   WAYBACK PAGE
   ═══════════════════════════════════════════════════════════════════════════ */

class WaybackPage {
  constructor(mount) { this.m = mount; this.page = 1; }

  async render() {
    this.m.innerHTML = `
      <div class="section-header">
        <h1>Wayback Machine</h1>
        <span style="color:var(--dim);font-size:0.85rem">Archived snapshots of I2P pages</span>
      </div>
      <div id="wb">${spinner('Loading archive...', 'Fetching Wayback statistics')}</div>`;
    const wb = document.getElementById('wb');
    try {
      const stats = await api('/wayback/stats', {}, { cacheKey: 'wayback_stats' });
      wb.innerHTML = `
        <div class="wb-stats">
          <div class="stat-card"><div class="stat-num">${stats.total_snapshots || 0}</div><div class="stat-label">Total Snapshots</div></div>
          <div class="stat-card"><div class="stat-num">${stats.total_urls || 0}</div><div class="stat-label">URLs Tracked</div></div>
          <div class="stat-card"><div class="stat-num">${formatBytes(stats.total_size_bytes)}</div><div class="stat-label">Archive Size</div></div>
        </div>`;

      const urlsResp = await api('/wayback/urls', { limit: PER_PAGE, offset: (this.page - 1) * PER_PAGE }, { cacheKey: 'wayback_urls_' + this.page });
      const urls = urlsResp.urls || [];
      const total = urlsResp.total || 0;
      if (urls.length > 0) {
        wb.innerHTML += `<h2>Recent URLs</h2>` + urls.map(u => `
          <div class="card wb-url-card">
            <h3><a href="${esc(u.url)}" target="_blank">${esc(u.title || u.url)}</a></h3>
            <div class="meta">
              <span>${u.capture_count || 0} capture${u.capture_count !== 1 ? 's' : ''}</span>
              <span style="color:var(--dim)">${u.last_captured ? timeAgo(u.last_captured) : ''}</span>
              <a href="#" onclick="showSnapshots('${safeId(u.url)}');return false">View snapshots</a>
            </div>
            <div id="${safeId(u.url)}" style="margin-top:0.5rem"></div>
          </div>`).join('') + pageNav(this.page, total, (p) => { this.page = p; this.render(); });
      } else {
        wb.innerHTML += '<p>No URLs tracked yet. Snapshots are created as the crawler discovers new pages.</p>';
      }
      wb.innerHTML += lastUpdated();
      this._urlMap = {};
      urls.forEach(u => { this._urlMap[safeId(u.url)] = u.url; });
      window._wbUrlMap = this._urlMap;
    } catch (e) { wb.innerHTML = errorBox(e.message, () => this.render()); }
  }
}

window.showSnapshots = async function(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const url = (window._wbUrlMap || {})[id];
  if (!url) { el.innerHTML = '<p>No URL data.</p>'; return; }
  el.innerHTML = spinner('Loading snapshots...');
  try {
    const d = await api(`/wayback/snapshots?url=${encodeURIComponent(url)}`, {}, { cacheKey: 'snap_' + id });
    if (!d.snapshots || !d.snapshots.length) { el.innerHTML = '<p>No snapshots.</p>'; return; }
    el.innerHTML = d.snapshots.map(s => `
      <div style="padding:0.4rem 0;font-size:0.85rem;display:flex;gap:0.75rem;align-items:center;border-bottom:1px solid var(--border)">
        <span style="color:${s.status_code === 200 ? 'var(--green)' : 'var(--orange)'}">HTTP ${s.status_code}</span>
        <span style="color:var(--dim)">${s.snapshot_time || ''}</span>
        ${s.size_bytes ? `<span style="color:var(--dim)">${formatBytes(s.size_bytes)}</span>` : ''}
        <a href="#" onclick="viewSnapshot('${s.id}','${esc(url)}');return false" style="margin-left:auto;color:var(--accent2)">View</a>
      </div>`).join('');
  } catch (e) { el.innerHTML = errorBox(e.message, () => showSnapshots(id)); }
};

window.viewSnapshot = function(snapshotId, url) {
  const viewerUrl = `/viewer.html?id=${snapshotId}&url=${encodeURIComponent(url)}`;
  window.open(viewerUrl, '_blank', 'width=1024,height=768,scrollbars=yes');
};

/* ═══════════════════════════════════════════════════════════════════════════
   ADDRESS BOOK PAGE
   ═══════════════════════════════════════════════════════════════════════════ */

class AddressBookPage {
  constructor(mount) { this.m = mount; this.page = 1; }

  async render() {
    this.m.innerHTML = `
      <div class="section-header">
        <h1>Address Book</h1>
        <span style="color:var(--dim);font-size:0.85rem">Known I2P hostnames and b32 addresses</span>
      </div>
      <div id="ab">${spinner('Loading address book...', 'Fetching known I2P hostnames')}</div>`;
    const ab = document.getElementById('ab');
    try {
      const d = await api('/addressbook', { page: this.page, per_page: PER_PAGE }, { cacheKey: `ab_${this.page}` });
      if (!d.sites || !d.sites.length) { ab.innerHTML = '<p>No entries yet. The registry crawler is still gathering addresses.</p>'; return; }
      const lines = d.sites.map(s => {
        const b32 = s.b32 ? (s.b32.endsWith('.b32.i2p') ? s.b32 : s.b32 + '.b32.i2p') : '';
        return `<div class="host-line"><span class="hostname ${s.likely_online ? 'online' : ''}">${esc(s.hostname)}</span><span class="equals">=</span><span class="b32">${esc(b32)}</span></div>`;
      }).join('');
      ab.innerHTML = `
        <p style="margin-bottom:1rem;color:var(--muted)">Hosts gathered from crawling I2P registries. Green = recently online. Copy as <code>hosts.txt</code> for your I2P router.</p>
        <div class="hosts-controls">
          <input type="text" id="ab-filter" placeholder="Filter hostnames..." style="flex:1">
          <a href="/api/abyssal/addressbook/hosts.txt?filter=active" target="_blank">↓ Active hosts.txt</a>
          <a href="/api/abyssal/addressbook/hosts.txt" target="_blank">↓ Full hosts.txt</a>
        </div>
        <div class="hosts-list" id="hosts-list">${lines}</div>
      ` + pageNav(this.page, d.total, (p) => { this.page = p; this.render(); }) + lastUpdated();

      // Client-side filter
      document.getElementById('ab-filter').addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase();
        document.querySelectorAll('#hosts-list .host-line').forEach(el => {
          el.style.display = el.textContent.toLowerCase().includes(q) ? '' : 'none';
        });
      });
    } catch (e) { ab.innerHTML = errorBox(e.message, () => this.render()); }
  }
}
