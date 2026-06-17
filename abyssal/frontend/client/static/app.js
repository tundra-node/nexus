/* Abyssal — I2P-Optimized Search Frontend
 *
 * Design principles for I2P:
 * 1. Show progress, not just spinners — I2P requests take 5-30s
 * 2. Cache aggressively in localStorage — avoid re-fetching
 * 3. Cancel in-flight requests — don't waste bandwidth on stale searches
 * 4. Retry with backoff — I2P connections are flaky
 * 5. Prefetch on hover — hide latency behind user reading time
 * 6. Connection status indicator — always know if proxy is alive
 */

const API = '/api/abyssal';
const PER_PAGE = 20;
const REQUEST_TIMEOUT = 45000;  // 45s — I2P is slow
const CACHE_TTL = 5 * 60 * 1000; // 5 min cache for directory/addressbook
const RETRY_DELAYS = [1000, 3000, 7000]; // exponential-ish backoff

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
        this.el.title = ms > 5000 ? 'Connected (slow)' : 'Connected';
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
      const entry = localStorage.getItem('abyssal_' + key);
      if (!entry) return null;
      const { ts, data } = JSON.parse(entry);
      if (Date.now() - ts > CACHE_TTL) { localStorage.removeItem('abyssal_' + key); return null; }
      return data;
    } catch (_) { return null; }
  },
  set(key, data) {
    try { localStorage.setItem('abyssal_' + key, JSON.stringify({ ts: Date.now(), data })); } catch (_) {}
  },
  invalidate(key) { localStorage.removeItem('abyssal_' + key); }
};

/* ── Router ─────────────────────────────────────────────────────────────── */

function highlightNav(base) {
  document.querySelectorAll('#nav a[data-nav]').forEach(a => {
    a.classList.toggle('active', a.dataset.nav === base);
  });
}

function route() {
  const path = location.pathname.replace(/\/$/, '') || '/';
  const hash = location.hash.slice(1) || '/';
  const page = hash || path;
  const [base, ...rest] = page.split('/').filter(Boolean);
  switch (base) {
    case 'browse':      highlightNav('browse'); renderPage(DirectoryPage); break;
    case 'site':        highlightNav(''); renderPage(SiteDetailPage, rest[0]); break;
    case 'wayback':     highlightNav('wayback'); renderPage(WaybackPage); break;
    case 'addressbook': highlightNav('addressbook'); renderPage(AddressBookPage); break;
    default:            highlightNav(''); renderPage(HomePage); break;
  }
}

function navigate(url) {
  history.pushState(null, '', url);
  route();
}

window.addEventListener('popstate', route);
document.addEventListener('DOMContentLoaded', () => { ConnMonitor.init(); route(); });

/* ── Page Rendering ─────────────────────────────────────────────────────── */

let _currentPage = null; // track for request cancellation

async function renderPage(Page, ...args) {
  const m = document.getElementById('main');
  // Cancel any in-flight requests from the previous page
  if (_currentPage && _currentPage.abort) _currentPage.abort();
  m.innerHTML = spinner('Loading...', 'Connecting through I2P — this may take a moment');
  try {
    const p = new Page(m, ...args);
    _currentPage = p;
    await p.render();
  } catch (e) {
    if (e.name === 'AbortError') return; // page changed, ignore
    m.innerHTML = errorBox(e.message, () => renderPage(Page, ...args));
  }
}

/* ── API Helper with retry + timeout + cancellation ─────────────────────── */

let _activeController = null;

async function api(url, params = {}, opts = {}) {
  const { timeout = REQUEST_TIMEOUT, retries = 2, cacheKey = null, signal } = opts;

  // Check cache first
  if (cacheKey) {
    const cached = Cache.get(cacheKey);
    if (cached) return cached;
  }

  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');
  const full = `${API}${url}${qs ? '?' + qs : ''}`;

  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    if (attempt > 0) {
      const delay = RETRY_DELAYS[Math.min(attempt - 1, RETRY_DELAYS.length - 1)];
      await new Promise(r => setTimeout(r, delay));
    }
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      // If caller provided a signal, link them
      if (signal) signal.addEventListener('abort', () => controller.abort(), { once: true });
      const r = await fetch(full, { signal: controller.signal });
      clearTimeout(timer);
      if (!r.ok) {
        const body = await r.text().catch(() => '');
        throw new Error(`API ${r.status}: ${body.slice(0, 200)}`);
      }
      const data = await r.json();
      if (cacheKey) Cache.set(cacheKey, data);
      return data;
    } catch (e) {
      lastErr = e;
      if (e.name === 'AbortError') throw e; // don't retry aborts
      // Don't retry on 4xx client errors
      if (e.message && e.message.match(/API 4\d\d/)) throw e;
    }
  }
  throw lastErr;
}

/* ── UI Components ──────────────────────────────────────────────────────── */

function spinner(text, hint) {
  return `<div class="loading">
    <div class="spinner"></div>
    <div class="loading-text">${esc(text)}</div>
    ${hint ? `<div class="loading-hint">${esc(hint)}</div>` : ''}
  </div>`;
}

function errorBox(msg, retryFn) {
  const retryBtn = retryFn ? `<button onclick="(${retryFn.toString().replace(/"/g, '&quot;')})()">↻ Retry</button>` : '';
  return `<div class="error-box">
    <div class="error-msg">⚠ ${esc(msg)}</div>
    ${retryBtn}
    <p style="margin-top:1rem;font-size:0.8rem">I2P connections can be slow or intermittent. If this persists, check that i2pd is running and has active peers.</p>
  </div>`;
}

function lastUpdated() {
  return `<div class="last-updated">Last updated: ${new Date().toLocaleTimeString()}</div>`;
}

function esc(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]); }

function safeId(s) { return 'id-' + String(s).replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 100); }

function statusBadge(online) {
  return `<span class="badge ${online ? 'online' : 'offline'}">${online ? 'Online' : 'Offline'}</span>`;
}

function extractHostname(url) {
  try { return new URL(url).hostname; } catch (_) { return url; }
}

function highlight(text, query) {
  if (!query) return esc(text);
  const re = new RegExp(`(${esc(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return esc(text).replace(re, '<mark style="background:#264f78;color:#e6edf3;padding:0 2px">$1</mark>');
}

function pageNav(page, total, cb) {
  const last = Math.ceil(total / PER_PAGE);
  if (last <= 1) return '';
  const d = document.createElement('div');
  d.className = 'pagination';
  d.innerHTML = `
    <button class="prev" ${page <= 1 ? 'disabled' : ''}>← Prev</button>
    <span>Page ${page} of ${last}</span>
    <button class="next" ${page >= last ? 'disabled' : ''}>Next →</button>
  `;
  d.querySelector('.prev').onclick = () => cb(page - 1);
  d.querySelector('.next').onclick = () => cb(page + 1);
  return d.outerHTML;
}

function card(body) { return `<div class="card">${body}</div>`; }

/* ── Prefetch on hover ──────────────────────────────────────────────────── */

document.addEventListener('mouseover', (e) => {
  const a = e.target.closest('a[href^="/site/"], a[href^="/browse"], a[href^="/wayback"], a[href^="/addressbook"]');
  if (!a || a.dataset.prefetched) return;
  const href = a.getAttribute('href');
  if (!href || href === location.pathname) return;
  // Prefetch the page data on hover (low priority)
  a.dataset.prefetched = '1';
  // We can't prefetch the JS page, but we can warm the API cache
  // by fetching the main data endpoint for that page
  if (href.startsWith('/site/')) {
    const hostname = href.replace('/site/', '');
    api(`/sites/${encodeURIComponent(hostname)}`, {}, { cacheKey: 'site_' + hostname, retries: 0 }).catch(() => {});
  }
});

/* ── Home Page ──────────────────────────────────────────────────────────── */

class HomePage {
  constructor(mount) {
    this.m = mount;
    this._searchController = null;
    this._debounceTimer = null;
  }

  abort() {
    if (this._searchController) this._searchController.abort();
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
  }

  async render() {
    // Load stats in background
    let stats = null;
    let statsErr = null;
    const statsPromise = api('/wayback/stats', {}, { cacheKey: 'home_stats', retries: 0, timeout: 10000 })
      .then(d => { stats = d; })
      .catch(e => { statsErr = e; });

    // Also fetch site count
    let siteCount = null;
    const sitesPromise = api('/sites', { page: 1, per_page: 1 }, { cacheKey: 'home_sites', retries: 0, timeout: 10000 })
      .then(d => { siteCount = d.total; })
      .catch(() => {});

    this.m.innerHTML = `
      <div class="home-hero">
        <h1>Search I2P</h1>
        <p class="hero-sub">Explore the invisible web — indexed, archived, and searchable.</p>
        <div class="search-box">
          <input id="sq" type="text" placeholder="Search I2P sites..." autocomplete="off">
          <button id="sb">Search</button>
        </div>
        <div class="filters">
          <select id="flang"><option value="">All languages</option></select>
          <select id="ftype"><option value="">All types</option></select>
        </div>
      </div>
      <div id="home-stats">${spinner('Loading stats...')}</div>
      <div id="results"></div>
    `;

    this.inp = document.getElementById('sq');
    this.btn = document.getElementById('sb');
    this.res = document.getElementById('results');
    this.flang = document.getElementById('flang');
    this.ftype = document.getElementById('ftype');

    // Load facets
    try {
      const f = await api('/facets', {}, { cacheKey: 'facets' });
      const langOpts = (f.languages || []).map(l => `<option value="${esc(l.language)}">${esc(l.language)} (${l.count})</option>`).join('');
      const typeOpts = (f.site_types || []).map(t => `<option value="${esc(t.site_type)}">${esc(t.site_type)} (${t.count})</option>`).join('');
      this.flang.innerHTML += langOpts;
      this.ftype.innerHTML += typeOpts;
    } catch (_) {}

    // Wait for stats
    await Promise.all([statsPromise, sitesPromise]);
    const statsEl = document.getElementById('home-stats');
    if (stats && statsEl) {
      statsEl.innerHTML = `
        <div class="home-stats-grid">
          <div class="stat-card">
            <div class="stat-num">${siteCount || '—'}</div>
            <div class="stat-label">Sites Discovered</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">${stats.total_snapshots || 0}</div>
            <div class="stat-label">Wayback Snapshots</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">${stats.total_urls || 0}</div>
            <div class="stat-label">URLs Tracked</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">${formatBytes(stats.total_size_bytes)}</div>
            <div class="stat-label">Archive Size</div>
          </div>
        </div>
      `;
    } else if (statsEl) {
      statsEl.innerHTML = '';
    }

    // Search handlers
    this.btn.onclick = () => this.search(1);
    this.inp.onkeydown = (e) => { if (e.key === 'Enter') this.search(1); };
    this.inp.oninput = () => {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = setTimeout(() => {
        if (this.inp.value.length >= 3) this.search(1);
      }, 400);
    };
    this.flang.onchange = () => this.search(1);
    this.ftype.onchange = () => this.search(1);

    // Restore from URL
    const p = new URLSearchParams(location.search);
    if (p.get('q')) {
      this.inp.value = p.get('q');
      const page = parseInt(p.get('page')) || 1;
      this.flang.value = p.get('lang') || '';
      this.ftype.value = p.get('site_type') || '';
      this.search(page);
    }
  }

  async search(page) {
    const q = this.inp.value;
    const lang = this.flang.value;
    const type = this.ftype.value;
    if (!q) { this.res.innerHTML = ''; return; }

    if (this._searchController) this._searchController.abort();
    this._searchController = new AbortController();

    const qs = `q=${encodeURIComponent(q)}&page=${page}&per_page=${PER_PAGE}&lang=${encodeURIComponent(lang)}&site_type=${encodeURIComponent(type)}`;
    navigate(`/?${qs}`);
    this.res.innerHTML = spinner('Searching I2P...', 'Querying the search index through the I2P network');
    this.btn.disabled = true;

    try {
      const d = await api(`/search?${qs}`, {}, {
        signal: this._searchController.signal,
        cacheKey: `search_${q}_${page}_${lang}_${type}`,
      });
      this.btn.disabled = false;
      if (!d.results || d.results.length === 0) {
        this.res.innerHTML = '<p>No results found. Try a broader query — the I2P index is still growing.</p>';
        return;
      }
      this.res.innerHTML = d.results.map(r => {
        const hostname = extractHostname(r.url);
        return card(`
          <h3><a href="/site/${esc(hostname)}" data-prefetch>${highlight(r.title || hostname, q)}</a></h3>
          <div class="meta">${esc(hostname)} ${r.language ? '· ' + esc(r.language) : ''} ${r.site_type ? '· ' + esc(r.site_type) : ''}</div>
          ${r.snippet ? `<div class="snippet">${r.snippet}</div>` : ''}
          <div class="tags">${r.status_code ? `<span class="tag">HTTP ${r.status_code}</span>` : ''}</div>
        `);
      }).join('') + pageNav(page, d.total, (p) => this.search(p)) + lastUpdated();
    } catch (e) {
      this.btn.disabled = false;
      if (e.name === 'AbortError') return;
      this.res.innerHTML = errorBox(e.message, () => this.search(page));
    }
  }
}

/* ── Directory Page ─────────────────────────────────────────────────────── */

class DirectoryPage {
  constructor(mount) { this.m = mount; this.page = 1; }

  async render() {
    this.m.innerHTML = `<h1>Site Directory</h1><div id="dir-list">${spinner('Loading directory...', 'Fetching known I2P sites')}</div>`;
    const dl = document.getElementById('dir-list');
    try {
      const cacheKey = `dir_page_${this.page}`;
      const d = await api(`/sites`, { page: this.page, per_page: PER_PAGE }, { cacheKey });
      if (!d.results || d.results.length === 0) { dl.innerHTML = '<p>No sites discovered yet. The crawler is still exploring I2P.</p>'; return; }
      dl.innerHTML = `
        <table><thead><tr><th>Site</th><th>Status</th><th>Language</th><th>Type</th><th>Last Seen</th></tr></thead>
        <tbody>${d.results.map(s => {
          const online = s.checks_online > s.checks_offline && s.checks_online > 0;
          return `<tr>
            <td><a href="/site/${esc(s.hostname)}" data-prefetch>${esc(s.hostname)}</a></td>
            <td>${statusBadge(online)}</td>
            <td>${s.language ? esc(s.language) : '-'}</td>
            <td>${s.site_type ? esc(s.site_type) : '-'}</td>
            <td>${s.last_seen_online ? new Date(s.last_seen_online).toLocaleDateString() : 'never'}</td>
          </tr>`;
        }).join('')}</tbody></table>
      ` + pageNav(this.page, d.total, (p) => { this.page = p; this.render(); }) + lastUpdated();
    } catch (e) { dl.innerHTML = errorBox(e.message, () => this.render()); }
  }
}

/* ── Site Detail Page ───────────────────────────────────────────────────── */

class SiteDetailPage {
  constructor(mount, hostname) { this.m = mount; this.hostname = hostname; }

  async render() {
    this.m.innerHTML = `<a href="javascript:history.back()" style="color:var(--muted);font-size:0.9rem">← Back</a><h1>${esc(this.hostname)}</h1><div id="site-detail">${spinner('Loading site...', 'Fetching site data through I2P')}</div>`;
    const sd = document.getElementById('site-detail');
    try {
      const s = await api(`/sites/${encodeURIComponent(this.hostname)}`, {}, { cacheKey: 'site_' + this.hostname });
      const online = s.checks_online > s.checks_offline && s.checks_online > 0;
      sd.innerHTML = `
        <div class="card">
          <div class="meta">Language: ${s.language || '-'} · Type: ${s.site_type || '-'} · ${statusBadge(online)}</div>
          ${s.b32 ? `<div class="meta" style="word-break:break-all">b32: ${esc(s.b32)}</div>` : ''}
          ${s.address_helper ? `<div class="meta" style="word-break:break-all;font-size:0.75rem">Address helper: ${esc(s.address_helper.slice(0, 80))}…</div>` : ''}
        </div>
        <h2>Pages (${s.pages ? s.pages.length : 0})</h2>
        ${this.renderTree(s.page_tree || [])}
        ${lastUpdated()}
      `;
    } catch (e) { sd.innerHTML = errorBox(e.message, () => this.render()); }
  }

  renderTree(nodes) {
    if (!nodes || nodes.length === 0) return '<p>No pages indexed yet.</p>';
    let html = '<div class="tree">';
    for (const n of nodes) {
      if (n.name === '(index)') continue;
      if (n.type === 'dir') {
        html += `<div class="folder"><div class="folder-toggle" onclick="this.parentElement.classList.toggle('open')">${esc(n.name)}</div><div class="folder-children">${this.renderTree(n.children)}</div></div>`;
      } else if (n.page) {
        const title = n.page.title || n.name;
        html += `<div class="file"><a href="/" onclick="return false">${esc(title)}</a></div>`;
      }
    }
    html += '</div>';
    return html;
  }
}

/* ── Wayback Page ───────────────────────────────────────────────────────── */

class WaybackPage {
  constructor(mount) { this.m = mount; this.page = 1; }

  async render() {
    this.m.innerHTML = `<h1>Wayback Machine</h1><div id="wb">${spinner('Loading archive...', 'Fetching Wayback statistics')}</div>`;
    const wb = document.getElementById('wb');
    try {
      const stats = await api('/wayback/stats', {}, { cacheKey: 'wayback_stats' });
      wb.innerHTML = `
        <div class="card">
          <div class="meta">Total snapshots: ${stats.total_snapshots}</div>
          <div class="meta">Total URLs tracked: ${stats.total_urls}</div>
          <div class="meta">Archive size: ${formatBytes(stats.total_size_bytes)}</div>
        </div>
      `;

      // Paginated URL listing
      const urlsResp = await api('/wayback/urls', { limit: PER_PAGE, offset: (this.page - 1) * PER_PAGE }, { cacheKey: 'wayback_urls_' + this.page });
      const urls = urlsResp.urls || [];
      const total = urlsResp.total || 0;
      if (Array.isArray(urls) && urls.length > 0) {
        wb.innerHTML += `<h2>Recent URLs</h2>` + urls.map(u => `
          <div class="card snapshot">
            <div><a href="${esc(u.url)}" target="_blank">${esc(u.title || u.url)}</a></div>
            <div class="time">Captures: ${u.capture_count || 0} · <a href="#" onclick="showSnapshots('${safeId(u.url)}');return false">View snapshots</a></div>
            <div id="${safeId(u.url)}"></div>
          </div>
        `).join('') + pageNav(this.page, total, (p) => { this.page = p; this.render(); });
      } else {
        wb.innerHTML += '<p>No URLs tracked yet.</p>';
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
    const d = await api(`/wayback/snapshots?url=${encodeURIComponent(url)}`, {}, { cacheKey: 'snapshots_' + id });
    if (!d.snapshots || d.snapshots.length === 0) { el.innerHTML = '<p>No snapshots.</p>'; return; }
    el.innerHTML = d.snapshots.map(s => `
      <div style="padding:0.3rem 0;font-size:0.9rem">
        <span class="time">${esc(s.snapshot_time || s.timestamp || '')}</span>
        <span class="status" style="color:${s.status_code === 200 ? 'var(--green)' : 'var(--orange)'}">HTTP ${s.status_code}</span>
        <span class="time">${s.content_type || ''}</span>
        ${s.size_bytes ? `<span class="time">· ${formatBytes(s.size_bytes)}</span>` : ''}
      </div>
    `).join('');
  } catch (e) { el.innerHTML = errorBox(e.message, () => showSnapshots(id)); }
};

/* ── Address Book Page ──────────────────────────────────────────────────── */

class AddressBookPage {
  constructor(mount) { this.m = mount; this.page = 1; }

  async render() {
    this.m.innerHTML = `<h1>Public Address Book</h1><div id="ab">${spinner('Loading address book...', 'Fetching known I2P hostnames')}</div>`;
    const ab = document.getElementById('ab');
    try {
      const cacheKey = `addressbook_page_${this.page}`;
      const d = await api('/addressbook', { page: this.page, per_page: PER_PAGE }, { cacheKey });
      if (!d.sites || d.sites.length === 0) { ab.innerHTML = '<p>No entries yet. The registry crawler is still gathering addresses.</p>'; return; }
      const lines = d.sites.map(s => {
        const b32 = s.b32 ? (s.b32.endsWith('.b32.i2p') ? s.b32 : s.b32 + '.b32.i2p') : '';
        return `<div><span style="color:${s.likely_online ? 'var(--green)' : 'var(--muted)'}">${esc(s.hostname)}</span>=${b32}</div>`;
      }).join('');
      ab.innerHTML = `
        <p style="margin-bottom:1rem">Hosts gathered from crawling I2P registries. Copy these as <code>hosts.txt</code> for your I2P router. Green = recently online.</p>
        <div class="hosts-list">${lines}</div>
        <div style="margin-top:1rem">
          <a href="/api/abyssal/addressbook/hosts.txt?filter=active" target="_blank">Download active hosts.txt</a> ·
          <a href="/api/abyssal/addressbook/hosts.txt" target="_blank">Download full hosts.txt</a>
        </div>
      ` + pageNav(this.page, d.total, (p) => { this.page = p; this.render(); }) + lastUpdated();
    } catch (e) { ab.innerHTML = errorBox(e.message, () => this.render()); }
  }
}

/* ── Utilities ──────────────────────────────────────────────────────────── */

function formatBytes(n) {
  if (!n) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return n.toFixed(1) + ' ' + units[i];
}

/* ── Bootstrap ──────────────────────────────────────────────────────────── */

route();
